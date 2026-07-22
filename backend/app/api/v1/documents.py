# pyrefly: ignore [missing-import]
from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile, status
# pyrefly: ignore [missing-import]
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import require_role
from app.models.user import User, UserRole
from app.repositories.document_repository import DocumentRepository
from app.schemas.document import DocumentRead
from app.services.document_processing_service import process_document
from app.services.document_service import DocumentValidationError, upload_document

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("", response_model=DocumentRead, status_code=status.HTTP_201_CREATED)
async def upload(
    background_tasks: BackgroundTasks,
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
            collection_id=collection_id,
            filename=file.filename,
            content=content,
        )
    except DocumentValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    # Runs after the response is sent, in the same process — no queue, no
    # separate worker. Was arq enqueuing onto Redis; process_document itself
    # never depended on that transport (see its docstring), so this is a pure
    # infrastructure simplification, not a behavior change to the API: the
    # client still gets the document back immediately at PENDING/PROCESSING
    # and polls GET /documents/{id} for status, exactly as before.
    background_tasks.add_task(process_document, document.id)

    return document


@router.get("/{document_id}", response_model=DocumentRead)
def get_document(
    document_id: int,
    current_user: User = Depends(require_role(UserRole.ADMIN, UserRole.SUPER_ADMIN)),
    db: Session = Depends(get_db),
):
    document = DocumentRepository(db, current_user.org_id).get(document_id)
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    return document
