from app.core.database import SessionLocal
from app.infrastructure import storage
from app.models.document import Document, DocumentStatus
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
            pages = extract(document.mime_type, content)
            cleaned_pages = [clean_text(page["text"]) for page in pages]

            document.page_count = len(cleaned_pages)
            document.extraction_method = _infer_extraction_method(document.mime_type)
            document.status = DocumentStatus.PROCESSED
            db.commit()
        except Exception as e:
            # Never let an extraction failure crash the worker process itself —
            # isolate it to this document and record it as failed.
            document.status = DocumentStatus.FAILED
            db.commit()
            print(f"[process_document] document {document_id} failed: {e}")
    finally:
        db.close()
