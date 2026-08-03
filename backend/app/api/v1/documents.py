# pyrefly: ignore [missing-import]
from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    UploadFile,
    status,
)
# pyrefly: ignore [missing-import]
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import SearchPrincipal, require_role, require_search_access
from app.core.rate_limit import limiter
from app.models.chunk import Chunk
from app.models.document import Document, DocumentStatus
from app.models.user import User, UserRole
from app.repositories.document_repository import DocumentRepository
from app.schemas.document import DocumentListResponse, DocumentPage, DocumentRead, DocumentText
from app.services.document_service import DocumentValidationError, upload_document

router = APIRouter(prefix="/documents", tags=["documents"])

# Ceiling on a single /text response. Roughly 250k characters is ~60k tokens —
# already more than most consumers can use in one prompt, and enough to hurt a
# 512Mi instance if several land at once.
MAX_DOCUMENT_TEXT_CHARS = 250_000


# No rate limit here previously (P0-2's aggravating factor): an authenticated
# admin could fire unlimited concurrent uploads, each one a full read into a
# 512Mi box. This doesn't fix the memory issue itself (that's the streaming-
# upload fix, still open) — it bounds how many of them a leaked admin token
# or a buggy client script can trigger per minute.
#
# 202 Accepted, not 201: upload_document() already persists the Document AND
# a durable ingestion_jobs row (app/services/ingestion_queue.py) in one
# transaction, so the resource exists, but processing genuinely hasn't
# started -- 202 is the correct code for "accepted, not yet complete",
# rather than 201's "created and done." The response body is unchanged; only
# the status code reflects what's actually true now.
@router.post("", response_model=DocumentRead, status_code=status.HTTP_202_ACCEPTED)
@limiter.limit("10/minute")
async def upload(
    request: Request,
    file: UploadFile = File(...),
    collection_id: int | None = Form(None),
    current_user: User = Depends(require_role(UserRole.ADMIN, UserRole.SUPER_ADMIN)),
    db: Session = Depends(get_db),
):
    content = await file.read()
    try:
        document = upload_document(
            db,
            org_id=current_user.org_id,
            user_id=current_user.id,
            collection_id=collection_id,
            filename=file.filename,
            content=content,
        )
    except DocumentValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    # No BackgroundTasks: the ingestion_jobs row upload_document() just
    # committed IS the handoff. The in-process worker loop (started from
    # main.py's lifespan) picks it up on its next poll -- durable across a
    # restart, unlike a BackgroundTasks callback that dies with the process
    # that scheduled it. Client still gets the document back immediately at
    # PENDING and polls GET /documents/{id} for status, exactly as before.
    return document


@router.get("", response_model=DocumentListResponse)
def list_documents(
    status_filter: DocumentStatus | None = Query(default=None, alias="status"),
    collection_id: int | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    principal: SearchPrincipal = Depends(require_search_access),
    db: Session = Depends(get_db),
):
    """List the documents in this organization's knowledge base.

    Read-only, so it shares /search's credential: an admin JWT or a service
    API key. A machine consumer cannot plan against knowledge it cannot
    enumerate — without this it can only fire a semantic search and hope the
    fragments came from the right file.

    Paginated because a corpus grows without bound and an unpaginated list
    endpoint is a latent OOM on a 512Mi instance.
    """
    org_id = principal.org_id
    query = db.query(Document).filter(Document.org_id == org_id)
    if status_filter is not None:
        query = query.filter(Document.status == status_filter)
    if collection_id is not None:
        query = query.filter(Document.collection_id == collection_id)

    total = query.count()
    documents = query.order_by(Document.id).offset(offset).limit(limit).all()
    return DocumentListResponse(documents=documents, total=total)


@router.get("/{document_id}", response_model=DocumentRead)
def get_document(
    document_id: int,
    principal: SearchPrincipal = Depends(require_search_access),
    db: Session = Depends(get_db),
):
    document = DocumentRepository(db, principal.org_id).get(document_id)
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    return document


@router.get("/{document_id}/text", response_model=DocumentText)
def get_document_text(
    document_id: int,
    page_from: int | None = Query(default=None, ge=1),
    page_to: int | None = Query(default=None, ge=1),
    principal: SearchPrincipal = Depends(require_search_access),
    db: Session = Depends(get_db),
):
    """Return a document's full text, page by page.

    Retrieval returns at most `top_k` chunks ranked by similarity to a query.
    That is the wrong shape for summarisation: a summary built from the five
    fragments most similar to "hostel rules" is a summary of the parts that
    repeat that phrase, not of the rules. Sections a correct summary must
    include may never rank at all.

    No re-extraction and no object-storage read — chunks already carry
    document_id, page_number, chunk_index and text, so this is one ordered
    query plus a group-by.
    """
    org_id = principal.org_id
    document = DocumentRepository(db, org_id).get(document_id)
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    query = db.query(Chunk).filter(Chunk.document_id == document_id, Chunk.org_id == org_id)
    if page_from is not None:
        query = query.filter(Chunk.page_number >= page_from)
    if page_to is not None:
        query = query.filter(Chunk.page_number <= page_to)

    chunks = query.order_by(Chunk.page_number, Chunk.chunk_index).all()

    # Bounded. An unbounded full-text response on a 512Mi instance is an OOM
    # waiting to happen, and this deploy already learned that lesson once with
    # uvicorn workers (see DEPLOYMENT_JOURNAL.md). The error names the fix
    # rather than just refusing.
    total_chars = sum(len(c.text) for c in chunks)
    if total_chars > MAX_DOCUMENT_TEXT_CHARS:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=(
                f"Document text is {total_chars} characters, above the "
                f"{MAX_DOCUMENT_TEXT_CHARS} limit. Request a page range with "
                f"page_from/page_to (document has {document.page_count or '?'} pages)."
            ),
        )

    pages: dict[int, list[str]] = {}
    for chunk in chunks:
        pages.setdefault(chunk.page_number, []).append(chunk.text)

    return DocumentText(
        document_id=document.id,
        filename=document.filename,
        page_count=document.page_count,
        pages=[DocumentPage(page_number=n, text="\n".join(t)) for n, t in sorted(pages.items())],
    )
