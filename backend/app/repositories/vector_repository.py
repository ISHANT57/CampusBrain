# pyrefly: ignore [missing-import]
from qdrant_client.models import PointIdsList, PointStruct
# pyrefly: ignore [missing-import]
from app.infrastructure import vector_store

# Qdrant caps how much it will accept in one request; a long document can
# produce thousands of chunks, so deletes go out in batches.
_DELETE_BATCH = 1000


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


def delete_points(org_id: int, point_ids: list[int]) -> None:
    """Drop specific vectors by id. Callers pass chunk ids, which ARE the point
    ids (see upsert_chunks).

    Deliberately by id rather than by a payload filter on document_id: Qdrant
    rejects filtering on a payload key that has no index
    ("Index required but not found for \"document_id\"") — self-hosted is
    lenient about this, Qdrant Cloud is not. Deleting by id needs no index, and
    the caller always has the chunk rows in hand anyway, so this avoids both
    the failure and having to maintain a payload index just to delete.
    """
    if not point_ids:
        return
    name = vector_store.collection_name(org_id)
    client = vector_store.get_client()
    if not client.collection_exists(name):
        return
    for i in range(0, len(point_ids), _DELETE_BATCH):
        client.delete(
            collection_name=name,
            points_selector=PointIdsList(points=point_ids[i : i + _DELETE_BATCH]),
        )
