from app.infrastructure.embeddings.provider import get_embedding_provider
from app.models.chunk import Chunk
from app.models.document import Document
from app.repositories.vector_repository import delete_points, upsert_chunks
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

    Used by both the API upload path (via ingestion_queue's worker) and
    tools/ingest.py directly — the only difference between an API upload and
    a local ingest is where the bytes come from, and that lives entirely in
    the callers.

    Does not commit or set document.status; the caller owns the transaction
    and the status transitions, because the two callers want different
    behaviour there (the API path marks FAILED and retries via the job
    queue, the local-ingest path reports the failure per-file and keeps
    going).

    Idempotent by construction, upsert-then-prune: new chunks are inserted
    and their vectors upserted to Qdrant BEFORE anything old is deleted. A
    re-index used to delete old chunks/vectors first — Qdrant's delete has no
    transaction, so it took effect immediately, and a crash during the
    embedding step that followed left the document with a live Postgres row
    and NO vectors: silently unsearchable, nothing to roll back to. With new
    content in place first, that same crash instead leaves the OLD content
    fully intact (nothing was ever removed), and a retry converges normally
    since re-inserting is idempotent and re-deleting an already-deleted
    point/row is a no-op.
    """
    raw_pages = extract(document.mime_type, content)
    cleaned_pages = [
        {"page_number": page["page_number"], "text": clean_text(page["text"])} for page in raw_pages
    ]

    document.page_count = len(cleaned_pages)
    document.extraction_method = _infer_extraction_method(document.mime_type)

    # Chunk ids from a PRIOR successful index -- deleted only after the new
    # ones are confirmed in place, below.
    stale = db.query(Chunk).filter(Chunk.document_id == document.id).all()

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
    # Flush, not commit: assigns each row a DB id (which becomes its Qdrant
    # point id) without ending the transaction -- if embedding fails next,
    # the caller's rollback removes these uncommitted rows and the stale
    # ones above are never touched.
    db.flush()

    provider = get_embedding_provider()
    points = [
        {
            "chunk_id": chunk.id,
            "vector": provider.embed(chunk.text),
            "payload": {
                "org_id": document.org_id,
                "document_id": document.id,
                "chunk_id": chunk.id,
                "page_number": chunk.page_number,
                "text": chunk.text,
            },
        }
        for chunk in chunk_rows
    ]

    if points:
        upsert_chunks(document.org_id, points)

    # Only now -- new content is live in both Postgres and Qdrant -- remove
    # what it superseded. A crash past this point is the narrow remaining
    # risk (a partially-completed delete batch); the retry it triggers
    # re-runs this same idempotent sequence and finishes the cleanup.
    if stale:
        delete_points(document.org_id, [chunk.id for chunk in stale])
        for chunk in stale:
            db.delete(chunk)
        db.flush()

    return len(points)
