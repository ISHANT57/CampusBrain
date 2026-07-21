from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.document import DocumentStatus


class DocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    org_id: int
    collection_id: int | None
    filename: str
    mime_type: str
    size_bytes: int
    status: DocumentStatus
    storage_key: str | None
    created_at: datetime
