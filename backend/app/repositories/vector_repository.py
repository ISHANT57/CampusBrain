from qdrant_client.models import PointStruct

from app.infrastructure import vector_store


def upsert_chunks(org_id: int, points: list[dict]) -> None:
    """points: [{"chunk_id": int, "vector": list[float], "payload": dict}, ...].
    Uses chunk_id as the Qdrant point id, so re-processing a document updates
    existing points rather than duplicating them."""
    vector_store.ensure_collection(org_id)
    qdrant_points = [
        PointStruct(id=p["chunk_id"], vector=p["vector"], payload=p["payload"]) for p in points
    ]
    vector_store.get_client().upsert(
        collection_name=vector_store.collection_name(org_id), points=qdrant_points
    )
