import fitz  # PyMuPDF


def extract_pdf(content: bytes) -> list[dict]:
    """Returns [{"page_number": int, "text": str}, ...], 1-indexed pages.
    A page with no text layer (e.g. a scanned image) returns text == ""."""
    pages = []
    with fitz.open(stream=content, filetype="pdf") as doc:
        for i, page in enumerate(doc, start=1):
            pages.append({"page_number": i, "text": page.get_text()})
    return pages
