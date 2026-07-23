NO_EVIDENCE_RESPONSE = "I don't have information on that in the available documents."


def build_rag_prompt(question: str, hits: list[dict], history: list[dict] | None = None) -> str:
    """Injects retrieved chunks as numbered context and instructs the model to
    answer only from them, citing sources inline as [n]. Optional history is
    prior conversation turns, so follow-up questions resolve correctly."""
    context_blocks = []
    for i, hit in enumerate(hits, start=1):
        context_blocks.append(
            f"[{i}] (document {hit['document_id']}, page {hit['page_number']})\n{hit['text']}"
        )
    context = "\n\n".join(context_blocks)

    history_block = ""
    if history:
        turns = "\n".join(f"{m['role']}: {m['content']}" for m in history)
        history_block = f"Conversation so far:\n{turns}\n\n"

    return (
        "You are a helpful assistant for an educational institution. Answer the "
        "question using ONLY the numbered context below. Cite the sources you use "
        "inline with their number in square brackets, e.g. [1]. If the context does "
        "not contain the answer, say exactly: "
        f'"{NO_EVIDENCE_RESPONSE}"\n\n'
        # Without this, "how many students went to KlearNow" was refused while
        # "which students went to KlearNow" listed eight of them from the same
        # chunk: the model read "ONLY the context" as forbidding any answer
        # whose literal words aren't present, and the count isn't written down
        # anywhere — it has to be counted off a table. Counting what the
        # context states is reading it, not inferring beyond it.
        "Counting, totalling or listing entries that the context states is part "
        "of answering from the context, not going beyond it. If the context "
        "lists the things asked about, count them and say how many were listed "
        "rather than refusing.\n\n"
        f"{history_block}"
        f"Context:\n{context}\n\n"
        f"Question: {question}\n\n"
        "Answer:"
    )
