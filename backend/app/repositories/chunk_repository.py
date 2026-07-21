from app.models.chunk import Chunk
from app.repositories.base import OrgScopedRepository


class ChunkRepository(OrgScopedRepository[Chunk]):
    model = Chunk
