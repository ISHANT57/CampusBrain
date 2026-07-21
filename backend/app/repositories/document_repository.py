from app.models.document import Document
from app.repositories.base import OrgScopedRepository


class DocumentRepository(OrgScopedRepository[Document]):
    model = Document
