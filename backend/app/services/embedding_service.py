from app.infrastructure.embeddings import embed_text


def embed_chunks(chunks: list[dict]) -> list[dict]:
    """chunks: [{"chunk_index": int, "text": str, ...}, ...].
    Returns the same dicts with an added "embedding" key. Per-chunk (not a
    single batch call) so one failing chunk is logged and skipped, never
    silently dropping the whole document."""
    embedded = []
    for chunk in chunks:
        try:
            vector = embed_text(chunk["text"])
        except Exception as e:
            print(f"[embed_chunks] chunk_index={chunk.get('chunk_index')} failed: {e}")
            continue
        embedded.append({**chunk, "embedding": vector})
    return embedded
