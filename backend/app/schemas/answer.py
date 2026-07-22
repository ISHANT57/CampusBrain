from pydantic import BaseModel


# FROZEN for v1 (M43): the frontend builds against this exact shape. Add fields
# additively if needed; do not rename or remove existing ones.
class Citation(BaseModel):
    index: int  # matches the [n] marker in the answer text
    document_id: int
    filename: str
    page_number: int
    excerpt: str


