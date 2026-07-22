from app.core.database import SessionLocal
from app.infrastructure import storage
from app.infrastructure.embeddings.provider import get_embedding_provider
from app.models.chunk import Chunk
from app.models.document import Document, DocumentStatus
from app.repositories.vector_repository import delete_document_points, upsert_chunks
from app.services.chunking.recursive_chunker import chunk_pages
from app.services.extraction.cleaner import clean_text
from app.services.extraction.router import extract


def _infer_extraction_method(mime_type: str) -> str:
    if mime_type == "application/pdf":
        return "pdf"  # per-page may mix real text and OCR fallback
    if mime_type in {"image/png", "image/jpeg"}:
        return "ocr"
    return "unstructured"


def index_document(db, document: Document, content: bytes) -> int:
    """Extract -> clean -> chunk -> embed -> index, for one document whose raw
    bytes the caller already has. Returns the number of chunks indexed.

    Split out from process_document so tools/ingest.py can run the exact same
    pipeline against a local file without going through object storage — the
    only difference between an API upload and a local ingest is where the
    bytes come from, and that difference now lives entirely in the callers.

    Does not commit or set document.status; the caller owns the transaction
    and the status transitions, because the two callers want different
    behaviour there (the API path marks FAILED and swallows, the ingest path
    reports the failure per-file and keeps going).
    """
    raw_pages = extract(document.mime_type, content)
    cleaned_pages = [
        {"page_number": page["page_number"], "text": clean_text(page["text"])} for page in raw_pages
    ]

    document.page_count = len(cleaned_pages)
    document.extraction_method = _infer_extraction_method(document.mime_type)

    # Re-indexing an existing document: drop the old rows and their vectors
    # first. Postgres hands out new chunk ids on re-insert, and chunk id IS
    # the Qdrant point id, so without this the old points are orphaned —
    # they'd never be overwritten by the upsert and would keep showing up in
    # search results forever, pointing at chunk rows that no longer exist.
    existing = db.query(Chunk).filter(Chunk.document_id == document.id).all()
    if existing:
        delete_document_points(document.org_id, document.id)
        for chunk in existing:
            db.delete(chunk)
        db.flush()

    # Persist chunks and flush so each gets a DB id — that id becomes
    # the Qdrant point id, tying every vector back to a real chunk row.
    chunk_rows = [
        Chunk(
            document_id=document.id,
            org_id=document.org_id,
            page_number=c["page_number"],
            chunk_index=c["chunk_index"],
            text=c["text"],
        )
        for c in chunk_pages(cleaned_pages)
    ]
    db.add_all(chunk_rows)
    db.flush()

    provider = get_embedding_provider()
    points = []
    for chunk in chunk_rows:
        vector = provider.embed(chunk.text)
        points.append(
            {
                "chunk_id": chunk.id,
                "vector": vector,
                "payload": {
                    "org_id": document.org_id,
                    "document_id": document.id,
                    "chunk_id": chunk.id,
                    "page_number": chunk.page_number,
                    "text": chunk.text,
                },
            }
        )

    if points:
        upsert_chunks(document.org_id, points)

    return len(points)


def process_document(document_id: int) -> None:
    """Fetch one uploaded document from object storage and index it. Runs via
    FastAPI BackgroundTasks (see api/v1/documents.py) — previously an arq task
    on a Redis queue; nothing here depended on that transport, so removing the
    queue only removed indirection, not capability.

    Plain sync def, not async: nothing in this function awaits (embedding and
    storage calls are all sync httpx/SDK calls), and BackgroundTasks runs sync
    callables in a worker thread automatically, so it doesn't block the event
    loop despite running after the response for /documents is returned.
    """
    db = SessionLocal()
    try:
        document = db.get(Document, document_id)
        if document is None:
            return

        document.status = DocumentStatus.PROCESSING
        db.commit()

        try:
            content = storage.get_object(document.storage_key)
            index_document(db, document, content)
            document.status = DocumentStatus.PROCESSED
            db.commit()
        except Exception as e:
            db.rollback()
            document.status = DocumentStatus.FAILED
            db.commit()
            print(f"[process_document] document {document_id} failed: {e}")
    finally:
        db.close()
