from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_role
from app.models.user import User, UserRole
from app.repositories.document_repository import DocumentRepository
from app.schemas.document import DocumentRead
from app.services.document_service import DocumentValidationError, upload_document
from app.workers.pool import get_arq_pool

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("", response_model=DocumentRead, status_code=status.HTTP_201_CREATED)
async def upload(
    file: UploadFile = File(...),
    collection_id: int | None = Form(None),
    current_user: User = Depends(require_role(UserRole.FACULTY, UserRole.ADMIN, UserRole.SUPER_ADMIN)),
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

    pool = await get_arq_pool()
    await pool.enqueue_job("process_document", document.id)

    return document


@router.get("/{document_id}", response_model=DocumentRead)
def get_document(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    document = DocumentRepository(db, current_user.org_id).get(document_id)
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    return document
