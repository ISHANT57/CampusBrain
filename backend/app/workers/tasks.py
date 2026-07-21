import asyncio

from app.core.database import SessionLocal
from app.models.document import Document, DocumentStatus


async def process_document(_ctx, document_id: int) -> None:
    """Stub: real extraction/chunking/embedding land in Phases 5-8. For now
    this only proves pending -> processing -> processed happens automatically
    after upload, with zero manual steps."""
    db = SessionLocal()
    try:
        document = db.get(Document, document_id)
        if document is None:
            return

        document.status = DocumentStatus.PROCESSING
        db.commit()

        await asyncio.sleep(2)  # stand-in for real extraction/chunking/embedding

        document.status = DocumentStatus.PROCESSED
        db.commit()
    finally:
        db.close()
