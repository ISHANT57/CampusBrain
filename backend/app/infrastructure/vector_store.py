# pyrefly: ignore [missing-import]
from qdrant_client import QdrantClient
# pyrefly: ignore [missing-import]
from qdrant_client.models import Distance, VectorParams

from app.core.config import settings
from app.infrastructure.embeddings.provider import get_embedding_provider

# qdrant_url set (Qdrant Cloud) takes priority over host/port (self-hosted,
# dev or the VPS path) — verified against qdrant-client's own docs: Cloud
# connections are `QdrantClient(url=..., api_key=...)`, not host/port, and
# Cloud rejects requests with no api_key.
if settings.qdrant_url:
    _client = QdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key or None)
else:
    _client = QdrantClient(host=settings.qdrant_host, port=settings.qdrant_internal_port)


def collection_name(org_id: int) -> str:
    # Per-organization collection = vector-level tenant isolation. One org's
    # search can never reach another's vectors because they live in separate
    # collections, not just behind a payload filter.
    return f"org_{org_id}"


def _create(name: str, dim: int) -> None:
    _client.create_collection(
        collection_name=name,
        vectors_config=VectorParams(size=dim, distance=Distance.COSINE),
    )


def ensure_collection(org_id: int) -> None:
    """Create the collection if missing. If it exists but was sized for a
    different embedding provider/dimension than the one active now, recreate
    it — Qdrant rejects upserting a vector whose length doesn't match the
    collection's configured size, so silently leaving a stale collection in
    place would turn every upload into a hard failure, not a slow one.

    Recreating drops any vectors already stored for this org: switching
    providers/dimensions means every document in that org needs
    re-embedding. This function only fixes Qdrant's side of that — the
    caller (or an operator) still needs to re-trigger processing for the
    affected documents so their chunks get re-embedded and re-upserted.
    """
    name = collection_name(org_id)
    dim = get_embedding_provider().dimension

    if not _client.collection_exists(name):
        _create(name, dim)
        return

    existing_dim = _client.get_collection(name).config.params.vectors.size
    if existing_dim != dim:
        _client.delete_collection(name)
        _create(name, dim)


def delete_collection(org_id: int) -> None:
    name = collection_name(org_id)
    if _client.collection_exists(name):
        _client.delete_collection(name)


def get_client() -> QdrantClient:
    return _client
