import os
import re
import uuid

import magic
from sqlalchemy.orm import Session

from app.core.upload_policy import MAX_UPLOAD_SIZE_BYTES, is_supported
from app.infrastructure import storage
from app.models.document import Document, DocumentStatus
from app.repositories.collection_repository import CollectionRepository


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

    _, ext = os.path.splitext(filename)

    # Sniff the actual bytes rather than trust the client's Content-Type
    # header or filename extension — either is trivially spoofable. Checking
    # the (extension, mime) *pair* against upload_policy — not each
    # independently — also rejects a mismatched pairing, e.g. a file named
    # "report.pdf" whose sniffed bytes are actually a spreadsheet.
    mime_type = magic.from_buffer(content, mime=True)
    if not is_supported(ext, mime_type):
        raise DocumentValidationError(f"Unsupported file: extension {ext!r}, detected type {mime_type!r}")

    if collection_id is not None:
        collection = CollectionRepository(db, org_id).get(collection_id)
        if collection is None:
            raise DocumentValidationError("Collection not found in this organization")

    # Never build the storage key from the client-supplied filename directly —
    # it's attacker-controlled and could contain "/" or ".." sequences. Keep
    # only a sanitized extension; the real filename lives solely in the DB
    # `filename` column, used for display, never for addressing storage.
    safe_ext = re.sub(r"[^A-Za-z0-9.]", "", ext)[:10]
    storage_key = f"{org_id}/{uuid.uuid4()}{safe_ext}"
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
