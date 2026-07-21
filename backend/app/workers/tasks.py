from app.core.database import SessionLocal
from app.infrastructure import storage
from app.models.chunk import Chunk
from app.models.document import Document, DocumentStatus
from app.services.chunking.recursive_chunker import chunk_pages
from app.services.extraction.cleaner import clean_text
from app.services.extraction.router import extract


def _infer_extraction_method(mime_type: str) -> str:
    if mime_type == "application/pdf":
        return "pdf"  # per-page may mix real text and OCR fallback
    if mime_type in {"image/png", "image/jpeg"}:
        return "ocr"
    return "unstructured"


async def process_document(_ctx, document_id: int) -> None:
    db = SessionLocal()
    try:
        document = db.get(Document, document_id)
        if document is None:
            return

        document.status = DocumentStatus.PROCESSING
        db.commit()

        try:
            content = storage.get_object(document.storage_key)
            raw_pages = extract(document.mime_type, content)
            cleaned_pages = [
                {"page_number": page["page_number"], "text": clean_text(page["text"])} for page in raw_pages
            ]

            document.page_count = len(cleaned_pages)
            document.extraction_method = _infer_extraction_method(document.mime_type)

            for chunk in chunk_pages(cleaned_pages):
                db.add(
                    Chunk(
                        document_id=document.id,
                        org_id=document.org_id,
                        page_number=chunk["page_number"],
                        chunk_index=chunk["chunk_index"],
                        text=chunk["text"],
                    )
                )

            document.status = DocumentStatus.PROCESSED
            db.commit()
        except Exception as e:
            # Never let an extraction/chunking failure crash the worker
            # process itself — isolate it to this document.
            db.rollback()
            document.status = DocumentStatus.FAILED
            db.commit()
            print(f"[process_document] document {document_id} failed: {e}")
    finally:
        db.close()
