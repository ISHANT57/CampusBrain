"""index_document's upsert-then-prune ordering (Phase 1 idempotency fix).

Everything here is stubbed (extraction, embedding, Qdrant, the DB session) --
this is a pure call-order/logic test, not an integration test. The property
under test: new content must be fully in place (Postgres flush + Qdrant
upsert) BEFORE any old content is touched, so a crash mid-embed leaves the
old, still-searchable version intact instead of the delete-first bug this
replaces (old vectors gone from Qdrant, nothing to roll back to).
"""

from app.models.chunk import Chunk
from app.models.document import Document
from app.services import document_processing_service as dps


class StubDB:
    """Just enough of a Session for index_document: one query for the
    pre-existing (stale) chunks, add_all/flush for the new ones, delete for
    the old ones once superseded."""

    def __init__(self, stale):
        self._stale = stale
        self.added = []
        self.deleted = []

    def query(self, _model):
        return self

    def filter(self, *_a, **_k):
        return self

    def all(self):
        return self._stale

    def add_all(self, rows):
        self.added.extend(rows)

    def flush(self):
        for i, row in enumerate(self.added):
            if getattr(row, "id", None) is None:
                row.id = 9000 + i

    def delete(self, row):
        self.deleted.append(row)


class FakeEmbeddingProvider:
    def __init__(self, fail_after: int | None = None):
        self._calls = 0
        self._fail_after = fail_after

    def embed(self, _text):
        self._calls += 1
        if self._fail_after is not None and self._calls > self._fail_after:
            raise RuntimeError("embedding API down")
        return [0.1, 0.2, 0.3]


def _patch_pipeline(monkeypatch, call_order, provider, n_pages=2):
    monkeypatch.setattr(dps, "extract", lambda mime, content: [
        {"page_number": i + 1, "text": f"page {i + 1}"} for i in range(n_pages)
    ])
    monkeypatch.setattr(dps, "clean_text", lambda text: text)
    monkeypatch.setattr(dps, "chunk_pages", lambda pages: [
        {"page_number": p["page_number"], "chunk_index": 0, "text": p["text"]} for p in pages
    ])
    monkeypatch.setattr(dps, "get_embedding_provider", lambda: provider)
    monkeypatch.setattr(dps, "upsert_chunks", lambda org_id, points: call_order.append(("upsert", len(points))))
    monkeypatch.setattr(dps, "delete_points", lambda org_id, ids: call_order.append(("delete", list(ids))))


def _document():
    return Document(id=1, org_id=1, filename="x.pdf", mime_type="application/pdf", size_bytes=10)


def test_new_content_is_upserted_before_old_content_is_removed(monkeypatch):
    call_order = []
    _patch_pipeline(monkeypatch, call_order, FakeEmbeddingProvider())
    stale = [Chunk(id=1, document_id=1, org_id=1, page_number=1, chunk_index=0, text="old")]
    db = StubDB(stale)

    dps.index_document(db, _document(), b"bytes")

    assert call_order[0][0] == "upsert"
    assert call_order[1] == ("delete", [1])
    assert db.deleted == stale  # old rows only removed after the upsert above


def test_a_crash_during_embedding_leaves_old_chunks_untouched(monkeypatch):
    """The bug this replaces: delete-first meant a failure here left the
    document with zero vectors. Upsert-first means old content survives."""
    call_order = []
    _patch_pipeline(monkeypatch, call_order, FakeEmbeddingProvider(fail_after=0))
    stale = [Chunk(id=1, document_id=1, org_id=1, page_number=1, chunk_index=0, text="old")]
    db = StubDB(stale)

    try:
        dps.index_document(db, _document(), b"bytes")
    except RuntimeError:
        pass

    assert call_order == []  # never reached upsert or delete
    assert db.deleted == []  # old rows never touched
    assert stale[0].id == 1  # stale chunk untouched, still addressable


def test_no_stale_chunks_skips_delete_entirely(monkeypatch):
    call_order = []
    _patch_pipeline(monkeypatch, call_order, FakeEmbeddingProvider())
    db = StubDB(stale=[])

    dps.index_document(db, _document(), b"bytes")

    assert [c[0] for c in call_order] == ["upsert"]
    assert db.deleted == []
