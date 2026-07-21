from app.models.collection import Collection
from app.repositories.base import OrgScopedRepository


class CollectionRepository(OrgScopedRepository[Collection]):
    model = Collection
