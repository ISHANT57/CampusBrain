from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.document import DocumentStatus


class DocumentPage(BaseModel):
    page_number: int
    text: str


class DocumentText(BaseModel):
    """Full text of one document, page by page.

    Assembled from `chunks`, which already hold the extracted text — so this
    costs one ordered query, not a re-extraction or an object-storage read.
    """

    document_id: int
    filename: str
    page_count: int | None
    pages: list[DocumentPage]


class DocumentListResponse(BaseModel):
    # `total` is the unpaginated count, so a caller can tell "that is
    # everything" from "there is a second page".
    documents: list["DocumentRead"]
    total: int


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
    page_count: int | None
    extraction_method: str | None
    created_at: datetime


# DocumentListResponse references DocumentRead before it is defined (the list
# schema reads better above the item schema). Pydantic v2 needs the forward
# reference resolved once the name exists.
DocumentListResponse.model_rebuild()
