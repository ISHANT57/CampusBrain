# pyrefly: ignore [missing-import]
from qdrant_client.models import FieldCondition, Filter, FilterSelector, MatchValue, PointStruct
# pyrefly: ignore [missing-import]
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


def delete_document_points(org_id: int, document_id: int) -> None:
    """Drop every vector belonging to one document, by payload filter rather
    than by id — the caller is re-indexing and is about to delete the chunk
    rows whose ids those points use, so it can't enumerate them afterwards."""
    if not vector_store.get_client().collection_exists(vector_store.collection_name(org_id)):
        return
    vector_store.get_client().delete(
        collection_name=vector_store.collection_name(org_id),
        points_selector=FilterSelector(
            filter=Filter(
                must=[FieldCondition(key="document_id", match=MatchValue(value=document_id))]
            )
        ),
    )
