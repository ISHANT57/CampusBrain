from app.services.extraction.ocr_extractor import ocr_image_bytes, ocr_pdf_page
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

IMAGE_MIME_TYPES = {"image/png", "image/jpeg"}

# Below this many characters, a PDF page is treated as textless (scanned) and
# re-rendered to an image for OCR instead of trusting the near-empty text layer.
OCR_TEXT_LENGTH_THRESHOLD = 20


class ExtractionError(Exception):
    pass


def extract(mime_type: str, content: bytes) -> list[dict]:
    if mime_type == "application/pdf":
        pages = extract_pdf(content)
        for page in pages:
            if len(page["text"].strip()) < OCR_TEXT_LENGTH_THRESHOLD:
                page["text"] = ocr_pdf_page(content, page["page_number"])
        return pages
    if mime_type in UNSTRUCTURED_MIME_TYPES:
        return extract_unstructured(content, mime_type)
    if mime_type in IMAGE_MIME_TYPES:
        return [{"page_number": 1, "text": ocr_image_bytes(content)}]
    raise ExtractionError(f"No extractor available for mime type: {mime_type}")
