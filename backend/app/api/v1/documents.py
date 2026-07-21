from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import require_role
from app.models.user import User, UserRole
from app.schemas.document import DocumentRead
from app.services.document_service import DocumentValidationError, upload_document

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
    return document
