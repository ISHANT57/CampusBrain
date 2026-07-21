from langchain_text_splitters import RecursiveCharacterTextSplitter

# Sensible defaults, not tuned (M26's tuning pass is deferred). Revisit if
# retrieval quality looks poor once the full pipeline is running.
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200

_splitter = RecursiveCharacterTextSplitter(
    chunk_size=CHUNK_SIZE,
    chunk_overlap=CHUNK_OVERLAP,
    separators=["\n\n", "\n", ". ", " ", ""],
)


def chunk_pages(pages: list[dict]) -> list[dict]:
    """pages: [{"page_number": int, "text": str}, ...] (already cleaned).
    Returns [{"page_number": int, "chunk_index": int, "text": str}, ...],
    chunk_index is a stable global order across the whole document."""
    chunks = []
    global_index = 0
    for page in pages:
        for chunk_text in _splitter.split_text(page["text"]):
            chunks.append(
                {"page_number": page["page_number"], "chunk_index": global_index, "text": chunk_text}
            )
            global_index += 1
    return chunks
