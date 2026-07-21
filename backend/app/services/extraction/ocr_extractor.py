import cv2
import fitz
import numpy as np
from paddleocr import PaddleOCR

_ocr_instance: PaddleOCR | None = None


def _get_ocr() -> PaddleOCR:
    # Lazy singleton: PaddleOCR loads its models on construction, which is
    # slow (and downloads them on first use) — do it once, not per call.
    global _ocr_instance
    if _ocr_instance is None:
        _ocr_instance = PaddleOCR(use_angle_cls=True, lang="en")
    return _ocr_instance


def ocr_image_bytes(image_bytes: bytes) -> str:
    arr = np.frombuffer(image_bytes, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        return ""

    result = _get_ocr().ocr(img, cls=True)
    lines: list[str] = []
    for page_result in result or []:
        for line in page_result or []:
            lines.append(line[1][0])
    return "\n".join(lines)


def ocr_pdf_page(pdf_content: bytes, page_number: int) -> str:
    """page_number is 1-indexed to match pdf_extractor's convention."""
    with fitz.open(stream=pdf_content, filetype="pdf") as doc:
        page = doc[page_number - 1]
        png_bytes = page.get_pixmap().tobytes("png")
    return ocr_image_bytes(png_bytes)
