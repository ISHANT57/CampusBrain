import re

from sqlalchemy import text as sql_text
from sqlalchemy.orm import Session

from app.infrastructure import vector_store
from app.infrastructure.embeddings.provider import get_embedding_provider

# Reciprocal Rank Fusion constant. 60 is the value from the original RRF paper
# and the de-facto default; it damps the influence of any single ranking.
RRF_K = 60


def semantic_search(org_id: int, query: str, top_k: int = 5) -> list[dict]:
    """Embed the query and return the top-k nearest chunks from this org's
    collection only. Cross-org isolation is structural: we only ever query
    org_{org_id}'s collection, never another's."""
    vector_store.ensure_collection(org_id)  # no-op if it exists; empty search if org never uploaded
    query_vector = get_embedding_provider().embed(query)

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


# A term in more than this share of the corpus is treated as noise and left
# out of the tsquery. Postgres's english dictionary already drops true
# stopwords ("how", "or", "at"), but not the words that are merely ubiquitous
# in *this* corpus — "student" is in 66% of chunks of a college prospectus.
#
# Calibrated, not guessed, and worth re-measuring against a different corpus:
# the thing this has to separate is a company name from the boilerplate around
# it. Measured on the current 273 chunks — "klearnow" 5%, "job" 10%, "ai" 15%,
# "currently" 23%, "internship" 27%, "students" 66%. 0.10 sits above every
# proper noun and below every filler word, and moved the two chunks that
# actually answer "how many students at klearnow" from unranked to 1st and
# 7th. Too low is the dangerous direction: at 0.02 the company name itself
# gets dropped and the arm returns nothing useful.
COMMON_TERM_RATIO = 0.10


def _to_or_tsquery(query: str) -> str:
    """Build an OR tsquery from free text.

    plainto_tsquery ANDs every term, so a natural-language question
    ("what programming languages are taught in year 1?") matches nothing
    unless a chunk contains all of those words. OR-ing the terms and letting
    ts_rank order the results is what actually gives BM25-like behaviour.
    """
    terms = [t for t in re.split(r"\W+", query) if t]
    return " | ".join(terms)


def _discriminating_terms(db: Session, org_id: int, terms: list[str]) -> list[str]:
    """Drop the query terms that are too common in this corpus to rank on.

    ts_rank has no IDF — it scores on how often a lexeme occurs *within* a
    chunk and knows nothing about how many other chunks contain it. So in
    "how many students are pursuing an internship at klearnow", `student`
    (66% of chunks) and `klearnow` (4%) counted the same, and chunks stuffed
    with the boilerplate words outranked the three that actually name the
    company. Catching rare proper nouns is the entire reason this arm exists
    alongside semantic search, so the common words have to go.

    Falls back to every term when they're all common — for a question like
    "what do students study", dropping them all would leave no query at all,
    and the old behaviour is the right answer there.
    """
    rows = db.execute(
        sql_text(
            """
            SELECT t.term,
                   (SELECT count(*) FROM chunks c
                     WHERE c.org_id = :org_id
                       AND c.search_vector @@ plainto_tsquery('english', t.term)) AS ndoc,
                   (SELECT count(*) FROM chunks c WHERE c.org_id = :org_id) AS total
            FROM unnest(CAST(:terms AS text[])) AS t(term)
            """
        ),
        {"terms": terms, "org_id": org_id},
    ).mappings().all()

    # plainto_tsquery stems each term the same way the indexed vector was
    # stemmed, so "pursuing"/"students" are counted as "pursu"/"student"
    # without this needing its own stemmer.
    rare = [r["term"] for r in rows if r["ndoc"] <= r["total"] * COMMON_TERM_RATIO]
    return rare or terms


def keyword_search(db: Session, org_id: int, query: str, top_k: int = 5) -> list[dict]:
    """Postgres full-text search. Catches exact terms (course codes, acronyms,
    proper nouns) that embeddings blur together."""
    terms = [t for t in re.split(r"\W+", query) if t]
    if not terms:
        return []
    tsquery = _to_or_tsquery(" ".join(_discriminating_terms(db, org_id, terms)))
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
