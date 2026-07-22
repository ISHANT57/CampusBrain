#!/usr/bin/env python3
"""Bulk-load a local folder of documents into the same Postgres + Qdrant the
running app uses, without going through the HTTP upload endpoint.

This is a local operator tool, not part of the deployed app. It reuses the
app's own services rather than reimplementing them, so ingested documents are
byte-for-byte indistinguishable from uploaded ones downstream:

  - same MIME/extension policy   app.core.upload_policy
  - same extraction + cleaning   app.services.extraction
  - same chunking                app.services.chunking.recursive_chunker
  - same Gemini embeddings       app.infrastructure.embeddings.provider
  - same Qdrant collection       app.repositories.vector_repository
  - same Neon/Postgres tables    app.models

The one deliberate difference: uploads store the original blob in Supabase and
index from there, while ingest reads local bytes directly and does NOT upload
them to object storage. Rationale — this is for preloading a corpus that
already lives on disk, and pushing hundreds of files into Supabase's free 1GB
tier would burn it for no benefit; nothing in retrieval or chat reads the
blob back (only chunk text, which is in Postgres). Consequence, so it isn't a
surprise: ingested documents have storage_key = NULL, so any future feature
that offers "download the original file" won't work for them. Pass
--upload-blobs if you want the blobs in object storage too.

Usage (from the repo root, with backend/.env populated):

    python tools/ingest.py ./docs                 # incremental (default)
    python tools/ingest.py ./docs --reindex       # force re-index everything
    python tools/ingest.py ./docs --org-id 1
    python tools/ingest.py ./docs --dry-run       # scan + report, change nothing
"""

import argparse
import hashlib
import os
import sys
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

# Make the app package importable as `app.*`, from either place this runs:
# the repo checkout (backend/ is a sibling of tools/), or inside the backend
# container (the app is at /app and tools/ is mounted separately).
_repo_backend = Path(__file__).resolve().parent.parent / "backend"
BACKEND = _repo_backend if (_repo_backend / "app").is_dir() else Path("/app")
sys.path.insert(0, str(BACKEND))

# Load backend/.env so this talks to the same Neon/Qdrant/Gemini as the app.
# Silently skipped when there's no .env — in the container, docker-compose's
# env_file has already put these in the real environment, and on Render they
# come from the dashboard, so a missing file is normal, not an error.
_env_path = BACKEND / ".env"
if _env_path.exists():
    try:
        from dotenv import load_dotenv

        load_dotenv(_env_path)
    except ImportError:
        # python-dotenv isn't a backend dependency (the app gets its env from
        # Docker/Render). Minimal fallback parser rather than adding a
        # dependency just for this tool.
        for line in _env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip())

import magic  # noqa: E402

from app.core.database import SessionLocal  # noqa: E402
from app.core.upload_policy import MAX_UPLOAD_SIZE_BYTES, SUPPORTED_TYPES, is_supported  # noqa: E402
from app.infrastructure import storage as object_storage  # noqa: E402
from app.models.chunk import Chunk  # noqa: E402
from app.models.document import Document, DocumentStatus  # noqa: E402
from app.models.organization import Organization  # noqa: E402
from app.repositories.vector_repository import delete_points  # noqa: E402
from app.services.document_processing_service import index_document  # noqa: E402


@dataclass
class Report:
    total: int = 0
    indexed: int = 0
    skipped: int = 0
    failed: int = 0
    chunks: int = 0
    failures: list[tuple[str, str]] = field(default_factory=list)

    @property
    def vectors(self) -> int:
        # One vector per chunk, by construction (index_document embeds each
        # chunk exactly once). Tracked as its own line in the report because
        # that's what was asked for, not because it can diverge.
        return self.chunks


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def discover(root: Path) -> list[Path]:
    """Every file under root whose extension is in the shared upload policy.
    Extension filtering only — the real (extension, MIME) pair check happens
    per-file later, against sniffed bytes."""
    return sorted(
        p
        for p in root.rglob("*")
        if p.is_file() and p.suffix.lower() in SUPPORTED_TYPES and not p.name.startswith(".")
    )


def progress(done: int, total: int, label: str, width: int = 28) -> None:
    filled = int(width * done / total) if total else width
    bar = "#" * filled + "-" * (width - filled)
    label = label if len(label) <= 40 else label[:37] + "..."
    sys.stdout.write(f"\r  [{bar}] {done}/{total}  {label:<40}")
    sys.stdout.flush()


def ingest_file(
    db, path: Path, root: Path, org_id: int, reindex: bool, upload_blobs: bool
) -> tuple[str, int]:
    """Returns (outcome, chunk_count) where outcome is indexed/skipped/failed.
    Raises nothing — failures come back as ('failed', 0) with the caller
    logging the message, so one bad file never aborts a 500-file run."""
    content = path.read_bytes()

    if len(content) > MAX_UPLOAD_SIZE_BYTES:
        raise ValueError(f"exceeds max size ({len(content)} > {MAX_UPLOAD_SIZE_BYTES} bytes)")

    # Same validation the upload endpoint applies: sniff real bytes and
    # require the (extension, mime) pair to be one upload_policy allows.
    mime_type = magic.from_buffer(content, mime=True)
    if not is_supported(path.suffix, mime_type):
        raise ValueError(f"unsupported: extension {path.suffix!r}, detected {mime_type!r}")

    digest = sha256(content)
    existing = (
        db.query(Document)
        .filter(Document.org_id == org_id, Document.content_hash == digest)
        .first()
    )

    # Content-addressed, not path-addressed: a file that moved or was renamed
    # but whose bytes are unchanged is correctly recognised as already
    # indexed, and an edited file (new bytes -> new hash) is correctly treated
    # as new rather than silently skipped.
    if existing and not reindex:
        if existing.status == DocumentStatus.PROCESSED:
            return "skipped", 0
        # Previously failed or was interrupted mid-processing — retry it
        # rather than skipping forever on a hash that was recorded before the
        # work actually succeeded.

    document = existing
    if document is None:
        storage_key = None
        if upload_blobs:
            storage_key = f"{org_id}/{uuid.uuid4()}{path.suffix.lower()}"
            object_storage.put_object(storage_key, content, content_type=mime_type)

        # Relative path, not just the bare name: this is what the citation
        # renderer shows (schemas.answer.Citation.filename), so storing
        # "handbook/admissions/fees.pdf" rather than "fees.pdf" means an
        # answer's citation carries the folder structure the document came
        # from. Done here rather than by adding a source_path column so the
        # Citation/DocumentRead schemas — i.e. the public API shape — stay
        # exactly as they are. Forward slashes always, so citations read the
        # same regardless of which OS ran the ingest.
        relative = path.relative_to(root).as_posix()

        document = Document(
            org_id=org_id,
            collection_id=None,
            filename=relative,
            mime_type=mime_type,
            size_bytes=len(content),
            status=DocumentStatus.PENDING,
            storage_key=storage_key,
            content_hash=digest,
        )
        db.add(document)
        db.flush()

    document.status = DocumentStatus.PROCESSING
    db.flush()

    chunk_count = index_document(db, document, content)

    document.status = DocumentStatus.PROCESSED
    document.content_hash = digest
    db.commit()
    return "indexed", chunk_count


def forget(db, pattern: str, org_id: int, apply: bool) -> list[str]:
    """Remove documents whose filename matches `pattern` from the knowledge
    base entirely: Qdrant vectors, chunk rows, the document row, and the
    stored blob if there is one.

    Deleting the source file from disk is NOT enough — the extracted text
    lives in Postgres chunks and the vectors in Qdrant, so a document stays
    fully answerable long after the file is gone. This is the only way to
    actually make the chatbot stop citing it.

    Ordering matters: the chunk ids have to be read before the chunk rows are
    deleted, because those ids are the Qdrant point ids. Drop the rows first
    and the vectors become unreachable — still being served, with nothing left
    pointing at them. If this run dies midway a re-run is safe; every step is
    a no-op once already done.
    """
    matches = (
        db.query(Document)
        .filter(Document.org_id == org_id, Document.filename.ilike(f"%{pattern}%"))
        .all()
    )
    if not matches:
        return []

    removed = []
    for document in matches:
        # Chunk ids ARE the Qdrant point ids, so this one query serves both the
        # preview count and the vector deletion.
        chunk_ids = [
            row[0] for row in db.query(Chunk.id).filter(Chunk.document_id == document.id).all()
        ]
        removed.append(f"{document.filename}  (id={document.id}, {len(chunk_ids)} chunks)")
        if not apply:
            continue

        delete_points(org_id, chunk_ids)
        db.query(Chunk).filter(Chunk.document_id == document.id).delete(synchronize_session=False)
        if document.storage_key:
            try:
                object_storage.delete_object(document.storage_key)
            except Exception as e:  # noqa: BLE001
                # The DB/vector cleanup is what stops the chatbot answering
                # from this document; an orphaned blob is untidy, not a leak
                # of the same kind. Report and continue rather than abort
                # halfway and leave the vectors live.
                print(f"  ! could not delete blob {document.storage_key}: {e}")
        db.delete(document)

    if apply:
        db.commit()
    return removed


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Preload a folder of documents into the app's Postgres + Qdrant.",
    )
    parser.add_argument(
        "folder", type=Path, nargs="?", help="folder to scan recursively (omit with --forget)"
    )
    parser.add_argument(
        "--forget",
        metavar="PATTERN",
        help="remove indexed documents whose filename contains PATTERN — deletes their "
        "vectors, chunks and metadata. Lists matches and changes nothing unless --yes.",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="actually perform --forget's deletion (it previews by default)",
    )
    parser.add_argument(
        "--org-id",
        type=int,
        default=1,
        help="organization to ingest into (default: 1). Must already exist.",
    )
    parser.add_argument(
        "--reindex",
        action="store_true",
        help="re-process files even if their hash is already indexed (replaces their chunks/vectors)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="report what would happen; touch nothing",
    )
    parser.add_argument(
        "--upload-blobs",
        action="store_true",
        help="also store original files in object storage (off by default; see module docstring)",
    )
    args = parser.parse_args()

    if args.forget:
        db = SessionLocal()
        try:
            removed = forget(db, args.forget, args.org_id, apply=args.yes)
        finally:
            db.close()

        if not removed:
            print(f"\nNo indexed document matches {args.forget!r} in org {args.org_id}.\n")
            return 0

        verb = "Removed" if args.yes else "Would remove"
        print(f"\n{verb} {len(removed)} document(s) matching {args.forget!r}:")
        for line in removed:
            print(f"    {line}")
        if args.yes:
            print("\nVectors, chunks and metadata deleted. The chatbot can no longer cite these.")
            print("Delete the source file too, or the next ingest run will re-index it.\n")
        else:
            print("\nPreview only — nothing was deleted. Re-run with --yes to apply.\n")
        return 0

    if args.folder is None:
        print("error: a folder is required unless --forget is used", file=sys.stderr)
        return 2

    if not args.folder.is_dir():
        print(f"error: {args.folder} is not a directory", file=sys.stderr)
        return 2

    files = discover(args.folder)
    report = Report(total=len(files))

    print(f"\nScanning {args.folder.resolve()}")
    print(f"  {len(files)} supported file(s) found")
    print(f"  mode: {'re-index (forced)' if args.reindex else 'incremental'}")
    if args.dry_run:
        print("  DRY RUN — nothing will be written\n")
        for p in files:
            print(f"    would consider  {p.relative_to(args.folder)}")
        print(f"\n  {len(files)} file(s) would be considered.\n")
        return 0
    print()

    db = SessionLocal()
    started = time.time()
    try:
        org = db.get(Organization, args.org_id)
        if org is None:
            # Fail loudly instead of inserting documents against a
            # non-existent org — the FK would reject it anyway, but per-file
            # and 500 times over.
            print(
                f"error: organization id={args.org_id} does not exist. "
                f"Create it first (see DEPLOYMENT.md), or pass --org-id.",
                file=sys.stderr,
            )
            return 2

        for i, path in enumerate(files, start=1):
            progress(i - 1, len(files), path.name)
            try:
                outcome, chunks = ingest_file(
                    db, path, args.folder, args.org_id, args.reindex, args.upload_blobs
                )
            except Exception as e:  # noqa: BLE001 — one bad file must not end the run
                db.rollback()
                report.failed += 1
                report.failures.append((str(path.relative_to(args.folder)), str(e)))
                continue

            if outcome == "indexed":
                report.indexed += 1
                report.chunks += chunks
            else:
                report.skipped += 1

        progress(len(files), len(files), "done")
        print()
    finally:
        db.close()

    elapsed = time.time() - started
    print("\n" + "=" * 52)
    print("  INGESTION REPORT")
    print("=" * 52)
    print(f"  Total documents : {report.total}")
    print(f"  Indexed         : {report.indexed}")
    print(f"  Skipped         : {report.skipped}  (already indexed)")
    print(f"  Failed          : {report.failed}")
    print(f"  Total chunks    : {report.chunks}")
    print(f"  Total vectors   : {report.vectors}")
    print(f"  Elapsed         : {elapsed:.1f}s")
    print("=" * 52)

    if report.failures:
        print("\n  Failures:")
        for name, err in report.failures:
            print(f"    {name}\n      -> {err}")
        print()

    # Non-zero exit when anything failed, so this is usable from a script.
    return 1 if report.failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
