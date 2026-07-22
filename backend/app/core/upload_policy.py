"""Single source of truth for which document types the app accepts —
document_service.py validates against this, and it's where to add a new
format instead of touching validation logic directly.

Each extension maps to the MIME type(s) `python-magic` (libmagic) actually
reports for real files of that kind — not just "the canonical MIME type" —
because validation checks that the *pairing* is one this map lists, not that
the extension and the MIME type are independently on some allowlist. That
distinction matters: independently-allowed lists would accept a file named
`report.pdf` whose sniffed bytes say `application/vnd.ms-excel`, since both
values individually appear somewhere in the map. Requiring the specific pair
rejects that.
"""

MAX_UPLOAD_SIZE_BYTES = 100 * 1024 * 1024  # 100 MB

SUPPORTED_TYPES: dict[str, set[str]] = {
    ".pdf": {"application/pdf"},
    ".txt": {"text/plain"},
    ".md": {"text/markdown", "text/plain"},
    ".csv": {"text/csv", "text/plain"},
    ".xlsx": {"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"},
    ".xls": {"application/vnd.ms-excel"},
    ".docx": {"application/vnd.openxmlformats-officedocument.wordprocessingml.document"},
    ".doc": {"application/msword"},
    ".pptx": {"application/vnd.openxmlformats-officedocument.presentationml.presentation"},
    ".ppt": {"application/vnd.ms-powerpoint"},
    ".json": {"application/json", "text/plain"},
    ".html": {"text/html"},
    ".xml": {"application/xml", "text/xml"},
}

ALLOWED_EXTENSIONS = frozenset(SUPPORTED_TYPES)
ALLOWED_MIME_TYPES = frozenset(mime for mimes in SUPPORTED_TYPES.values() for mime in mimes)


def is_supported(extension: str, mime_type: str) -> bool:
    """extension should include the leading dot, e.g. ".pdf" — matches
    os.path.splitext's output, which is what document_service.py passes in."""
    return mime_type in SUPPORTED_TYPES.get(extension.lower(), frozenset())
