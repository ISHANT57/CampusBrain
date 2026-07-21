# pyrefly: ignore [missing-import]
from qdrant_client import QdrantClient
# pyrefly: ignore [missing-import]
from qdrant_client.models import Distance, VectorParams

from app.core.config import settings

_client = QdrantClient(host=settings.qdrant_host, port=settings.qdrant_internal_port)


def collection_name(org_id: int) -> str:
    # Per-organization collection = vector-level tenant isolation. One org's
    # search can never reach another's vectors because they live in separate
    # collections, not just behind a payload filter.
    return f"org_{org_id}"


def ensure_collection(org_id: int) -> None:
    name = collection_name(org_id)
    if not _client.collection_exists(name):
        _client.create_collection(
            collection_name=name,
            vectors_config=VectorParams(size=settings.embedding_dim, distance=Distance.COSINE),
        )


def delete_collection(org_id: int) -> None:
    name = collection_name(org_id)
    if _client.collection_exists(name):
        _client.delete_collection(name)


def get_client() -> QdrantClient:
    return _client
