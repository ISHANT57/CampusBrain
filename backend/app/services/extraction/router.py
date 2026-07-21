from app.services.extraction.pdf_extractor import extract_pdf
from app.services.extraction.unstructured_extractor import extract_unstructured

UNSTRUCTURED_MIME_TYPES = {
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",  # .docx
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",  # .pptx
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",  # .xlsx
    "text/csv",
    "text/markdown",
    "text/plain",
}


class ExtractionError(Exception):
    pass


def extract(mime_type: str, content: bytes) -> list[dict]:
    if mime_type == "application/pdf":
        return extract_pdf(content)
    if mime_type in UNSTRUCTURED_MIME_TYPES:
        return extract_unstructured(content, mime_type)
    # image/png, image/jpeg routed to OCR once ocr_extractor exists (M22).
    raise ExtractionError(f"No extractor available for mime type: {mime_type}")
