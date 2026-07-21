from app.infrastructure import vector_store
from app.infrastructure.embeddings import embed_text


def semantic_search(org_id: int, query: str, top_k: int = 5) -> list[dict]:
    """Embed the query and return the top-k nearest chunks from this org's
    collection only. Cross-org isolation is structural: we only ever query
    org_{org_id}'s collection, never another's."""
    vector_store.ensure_collection(org_id)  # no-op if it exists; empty search if org never uploaded
    query_vector = embed_text(query)

    hits = vector_store.get_client().search(
        collection_name=vector_store.collection_name(org_id),
        query_vector=query_vector,
        limit=top_k,
        with_payload=True,
    )
    return [
        {
            "score": hit.score,
            "chunk_id": hit.payload["chunk_id"],
            "document_id": hit.payload["document_id"],
            "page_number": hit.payload["page_number"],
            "text": hit.payload["text"],
        }
        for hit in hits
    ]
