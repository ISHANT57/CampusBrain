import uuid

import magic
from sqlalchemy.orm import Session

from app.infrastructure import storage
from app.models.document import Document, DocumentStatus
from app.repositories.collection_repository import CollectionRepository

ALLOWED_MIME_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",  # .docx
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",  # .pptx
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",  # .xlsx
    "text/csv",
    "text/markdown",
    "text/plain",
    "image/png",
    "image/jpeg",
}

MAX_UPLOAD_SIZE_BYTES = 50 * 1024 * 1024  # 50 MB


class DocumentValidationError(Exception):
    pass


def upload_document(
    db: Session,
    *,
    org_id: int,
    collection_id: int | None,
    filename: str,
    content: bytes,
) -> Document:
    if len(content) > MAX_UPLOAD_SIZE_BYTES:
        raise DocumentValidationError(f"File exceeds max size of {MAX_UPLOAD_SIZE_BYTES} bytes")

    # Sniff the actual bytes rather than trust the client's Content-Type
    # header or filename extension — either is trivially spoofable.
    mime_type = magic.from_buffer(content, mime=True)
    if mime_type not in ALLOWED_MIME_TYPES:
        raise DocumentValidationError(f"Unsupported file type: {mime_type}")

    if collection_id is not None:
        collection = CollectionRepository(db, org_id).get(collection_id)
        if collection is None:
            raise DocumentValidationError("Collection not found in this organization")

    storage_key = f"{org_id}/{uuid.uuid4()}_{filename}"
    storage.put_object(storage_key, content, content_type=mime_type)

    document = Document(
        org_id=org_id,
        collection_id=collection_id,
        filename=filename,
        mime_type=mime_type,
        size_bytes=len(content),
        status=DocumentStatus.PENDING,
        storage_key=storage_key,
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    return document
