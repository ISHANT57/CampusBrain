import re

from sqlalchemy import text as sql_text
from sqlalchemy.orm import Session

from app.infrastructure import vector_store
from app.infrastructure.embeddings import embed_text

# Reciprocal Rank Fusion constant. 60 is the value from the original RRF paper
# and the de-facto default; it damps the influence of any single ranking.
RRF_K = 60


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


def _to_or_tsquery(query: str) -> str:
    """Build an OR tsquery from free text.

    plainto_tsquery ANDs every term, so a natural-language question
    ("what programming languages are taught in year 1?") matches nothing
    unless a chunk contains all of those words. OR-ing the terms and letting
    ts_rank order the results is what actually gives BM25-like behaviour.
    """
    terms = [t for t in re.split(r"\W+", query) if t]
    return " | ".join(terms)


def keyword_search(db: Session, org_id: int, query: str, top_k: int = 5) -> list[dict]:
    """Postgres full-text search. Catches exact terms (course codes, acronyms,
    proper nouns) that embeddings blur together."""
    tsquery = _to_or_tsquery(query)
    if not tsquery:
        return []

    rows = db.execute(
        sql_text(
            """
            SELECT id, document_id, page_number, text,
                   ts_rank(search_vector, to_tsquery('english', :q)) AS rank
            FROM chunks
            WHERE org_id = :org_id
              AND search_vector @@ to_tsquery('english', :q)
            ORDER BY rank DESC
            LIMIT :top_k
            """
        ),
        {"q": tsquery, "org_id": org_id, "top_k": top_k},
    ).mappings().all()

    return [
        {
            "score": float(r["rank"]),
            "chunk_id": r["id"],
            "document_id": r["document_id"],
            "page_number": r["page_number"],
            "text": r["text"],
        }
        for r in rows
    ]


def hybrid_search(db: Session, org_id: int, query: str, top_k: int = 5) -> list[dict]:
    """Reciprocal Rank Fusion of semantic + keyword results.

    RRF fuses on *rank position*, not raw score — deliberate, because cosine
    similarity (0-1) and ts_rank (unbounded) aren't comparable numbers. Each
    list contributes 1/(K + rank) per chunk, so agreeing on a chunk beats
    ranking it first in only one list.
    """
    # Over-fetch from each source so fusion has candidates to work with.
    fetch = max(top_k * 4, 20)
    semantic = semantic_search(org_id, query, fetch)
    keyword = keyword_search(db, org_id, query, fetch)

    fused: dict[int, dict] = {}
    for source, ranked_list in (("semantic", semantic), ("keyword", keyword)):
        for rank, hit in enumerate(ranked_list, start=1):
            entry = fused.setdefault(hit["chunk_id"], {**hit, "score": 0.0, "semantic_score": 0.0})
            entry["score"] += 1.0 / (RRF_K + rank)
            if source == "semantic":
                # Preserved because the no-evidence guardrail is calibrated on
                # cosine similarity (0-1). RRF scores are ~0.03 and not
                # comparable — thresholding on them would refuse everything.
                entry["semantic_score"] = hit["score"]

    return sorted(fused.values(), key=lambda h: h["score"], reverse=True)[:top_k]
