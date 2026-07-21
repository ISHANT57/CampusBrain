import io

# pyrefly: ignore [missing-import]
from unstructured.partition.auto import partition


def extract_unstructured(content: bytes, mime_type: str) -> list[dict]:
    """Returns [{"page_number": int, "text": str}, ...]. Formats without a
    real page concept (CSV/Markdown/TXT) collapse to a single page_number=1."""
    elements = partition(file=io.BytesIO(content), content_type=mime_type)

    pages: dict[int, list[str]] = {}
    for element in elements:
        page_number = getattr(element.metadata, "page_number", None) or 1
        pages.setdefault(page_number, []).append(str(element))

    return [
        {"page_number": page_number, "text": "\n".join(texts)}
        for page_number, texts in sorted(pages.items())
    ]
