"""Unit tests for citation filtering.

Pure function, no DB/LLM/network — runs standalone:
    docker compose exec backend pytest tests/test_rag_citations.py

Guards the rule that sources shown to a user must be evidence for what the
answer said, not a log of everything retrieval looked at.
"""

import pytest

from app.services.rag_service import keep_cited_sources


def hit(n: int) -> dict:
    return {"document_id": n, "page_number": n, "chunk_id": n, "text": f"text {n}"}


HITS = [hit(1), hit(2), hit(3), hit(4), hit(5)]


def test_uncited_sources_are_dropped():
    """The core case: retrieval returns 5, the answer uses 1 — show 1."""
    answer, citations = keep_cited_sources("Fees are covered [3].", HITS)
    assert len(citations) == 1
    assert citations[0]["document_id"] == 3
    # Renumbered to [1] so the marker matches the single source shown.
    assert answer == "Fees are covered [1]."


def test_refusal_shows_no_sources():
    """A declined answer cites nothing, so it must carry no sources — this is
    the case that previously showed a full source list under 'I don't know'."""
    answer, citations = keep_cited_sources(
        "I don't have information on that in the available documents.", HITS
    )
    assert citations == []
    assert answer == "I don't have information on that in the available documents."


def test_markers_are_renumbered_contiguously():
    """Citing [2] and [4] must present as sources 1 and 2, not 2 and 4 —
    gaps read as missing items."""
    answer, citations = keep_cited_sources("First [2]. Second [4].", HITS)
    assert [c["index"] for c in citations] == [1, 2]
    assert [c["document_id"] for c in citations] == [2, 4]
    assert answer == "First [1]. Second [2]."


def test_repeated_marker_yields_one_source():
    answer, citations = keep_cited_sources("A [2]. B [2]. C [3].", HITS)
    assert [c["document_id"] for c in citations] == [2, 3]
    assert answer == "A [1]. B [1]. C [2]."


def test_out_of_range_marker_is_removed():
    """A hallucinated [9] must not survive as a reference to nothing."""
    answer, citations = keep_cited_sources("Real [1]. Invented [9].", HITS)
    assert [c["document_id"] for c in citations] == [1]
    assert "[9]" not in answer
    assert answer == "Real [1]. Invented ."


def test_all_markers_invalid_leaves_no_sources():
    answer, citations = keep_cited_sources("Nonsense [7] and [8].", HITS)
    assert citations == []
    assert "[7]" not in answer and "[8]" not in answer


def test_zero_index_is_not_a_valid_source():
    """Sources are 1-indexed; [0] would map to hits[-1], silently citing the
    last chunk instead of failing."""
    _, citations = keep_cited_sources("Bad [0].", HITS)
    assert citations == []


@pytest.mark.parametrize("answer", ["", "No markers at all."])
def test_answers_without_markers_have_no_sources(answer):
    assert keep_cited_sources(answer, HITS)[1] == []
