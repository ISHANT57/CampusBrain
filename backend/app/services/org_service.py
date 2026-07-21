from sqlalchemy.orm import Session

from app.infrastructure import vector_store
from app.models.organization import Organization


def create_organization(db: Session, *, name: str, slug: str) -> Organization:
    org = Organization(name=name, slug=slug)
    db.add(org)
    db.commit()
    db.refresh(org)
    # Every org gets its own isolated Qdrant collection on creation.
    vector_store.ensure_collection(org.id)
    return org


def delete_organization(db: Session, org: Organization) -> None:
    vector_store.delete_collection(org.id)
    db.delete(org)
    db.commit()
