from typing import Generic, TypeVar

from sqlalchemy.orm import Session

ModelType = TypeVar("ModelType")


class OrgScopedRepository(Generic[ModelType]):
    """Every query is filtered by org_id — the single control point that makes
    cross-tenant data leakage structurally impossible rather than something
    every future repository method has to remember to do itself."""

    model: type[ModelType]

    def __init__(self, db: Session, org_id: int):
        self.db = db
        self.org_id = org_id

    def get(self, id: int) -> ModelType | None:
        return (
            self.db.query(self.model)
            .filter(self.model.id == id, self.model.org_id == self.org_id)
            .first()
        )

    def list(self) -> list[ModelType]:
        return self.db.query(self.model).filter(self.model.org_id == self.org_id).all()
