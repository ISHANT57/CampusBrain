"""P1-CHANGE-2 and P1-CHANGE-3: GET /documents and GET /documents/{id}/text.

These run against the REAL database, because both endpoints are essentially
queries — stubbing the database would test the mocks. Both are read-only, so
pointing them at the live corpus is safe.

Skipped when DATABASE_URL is absent, so the suite still passes on a machine
with no credentials rather than failing for the wrong reason.
"""

import os

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.config import settings

pytestmark = pytest.mark.skipif(
    not os.getenv("DATABASE_URL"),
    reason="needs a real database; these endpoints are queries",
)

KEY = "test-doc-read-key"


@pytest.fixture(scope="module")
def client():
    settings.service_api_key = KEY
    settings.service_api_key_org_id = 1

    # Mount only the documents router. The full app additionally pulls in the
    # chat and search routers and their embedding clients, none of which these
    # endpoints touch.
    from app.api.v1.documents import router

    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    return TestClient(app)


def _auth() -> dict:
    return {"X-API-Key": KEY}


# --- auth -------------------------------------------------------------------

def test_list_requires_a_credential(client):
    assert client.get("/api/v1/documents").status_code == 401


def test_text_requires_a_credential(client):
    assert client.get("/api/v1/documents/1/text").status_code == 401


def test_wrong_key_is_rejected(client):
    assert client.get("/api/v1/documents", headers={"X-API-Key": "nope"}).status_code == 401


# --- P1-CHANGE-2: list ------------------------------------------------------

def test_list_returns_documents_and_a_total(client):
    body = client.get("/api/v1/documents", headers=_auth()).json()
    assert isinstance(body["documents"], list)
    assert isinstance(body["total"], int)
    assert body["total"] >= len(body["documents"])


def test_list_is_paginated(client):
    first = client.get("/api/v1/documents?limit=1", headers=_auth()).json()
    if first["total"] < 2:
        pytest.skip("corpus too small to exercise pagination")
    second = client.get("/api/v1/documents?limit=1&offset=1", headers=_auth()).json()
    assert len(first["documents"]) == 1
    # `total` is the unpaginated count, so a caller can tell "that's everything"
    # from "there's another page".
    assert first["total"] == second["total"]
    assert first["documents"][0]["id"] != second["documents"][0]["id"]


def test_list_rejects_an_unbounded_limit(client):
    # An unpaginated list endpoint on a 512Mi instance is a latent OOM.
    assert client.get("/api/v1/documents?limit=99999", headers=_auth()).status_code == 422


def test_status_filter_narrows_results(client):
    all_docs = client.get("/api/v1/documents", headers=_auth()).json()
    processed = client.get("/api/v1/documents?status=processed", headers=_auth()).json()
    assert processed["total"] <= all_docs["total"]
    assert all(d["status"] == "processed" for d in processed["documents"])


# --- P1-CHANGE-3: full text -------------------------------------------------

def test_text_returns_ordered_pages(client):
    docs = client.get("/api/v1/documents?status=processed&limit=1", headers=_auth()).json()
    if not docs["documents"]:
        pytest.skip("no processed documents in the corpus")

    doc_id = docs["documents"][0]["id"]
    body = client.get(f"/api/v1/documents/{doc_id}/text", headers=_auth()).json()

    assert body["document_id"] == doc_id
    assert body["filename"]
    pages = body["pages"]
    assert pages, "a processed document should have text"
    assert [p["page_number"] for p in pages] == sorted(p["page_number"] for p in pages)
    assert any(p["text"].strip() for p in pages)


def test_text_respects_a_page_range(client):
    docs = client.get("/api/v1/documents?status=processed&limit=1", headers=_auth()).json()
    if not docs["documents"]:
        pytest.skip("no processed documents in the corpus")

    doc_id = docs["documents"][0]["id"]
    body = client.get(f"/api/v1/documents/{doc_id}/text?page_from=1&page_to=1", headers=_auth()).json()
    assert all(p["page_number"] == 1 for p in body["pages"])


def test_text_404s_for_a_missing_document(client):
    assert client.get("/api/v1/documents/99999999/text", headers=_auth()).status_code == 404


def test_text_is_whole_document_not_fragments(client):
    """The point of P1-CHANGE-3.

    Retrieval returns top-k chunks ranked against a query; a summary built from
    those is a summary of the parts matching the query, not of the document.
    This endpoint must return everything.
    """
    docs = client.get("/api/v1/documents?status=processed&limit=1", headers=_auth()).json()
    if not docs["documents"]:
        pytest.skip("no processed documents in the corpus")

    doc_id = docs["documents"][0]["id"]
    body = client.get(f"/api/v1/documents/{doc_id}/text", headers=_auth()).json()
    total_chars = sum(len(p["text"]) for p in body["pages"])
    # Comfortably more than the ~1k characters five retrieved chunks would give.
    assert total_chars > 1000
