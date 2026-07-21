NO_EVIDENCE_RESPONSE = "I don't have information on that in the available documents."


def build_rag_prompt(question: str, hits: list[dict]) -> str:
    """Injects retrieved chunks as numbered context and instructs the model to
    answer only from them, citing sources inline as [n]."""
    context_blocks = []
    for i, hit in enumerate(hits, start=1):
        context_blocks.append(
            f"[{i}] (document {hit['document_id']}, page {hit['page_number']})\n{hit['text']}"
        )
    context = "\n\n".join(context_blocks)

    return (
        "You are a helpful assistant for an educational institution. Answer the "
        "question using ONLY the numbered context below. Cite the sources you use "
        "inline with their number in square brackets, e.g. [1]. If the context does "
        "not contain the answer, say exactly: "
        f'"{NO_EVIDENCE_RESPONSE}"\n\n'
        f"Context:\n{context}\n\n"
        f"Question: {question}\n\n"
        "Answer:"
    )
