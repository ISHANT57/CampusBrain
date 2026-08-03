NO_EVIDENCE_RESPONSE = "I don't have information on that in the available documents."

# Bumped whenever build_rag_prompt's wording changes, and logged on every
# answer (rag_service.answer_question) — so a quality regression can be
# correlated to the prompt revision that caused it instead of guessed at.
#
# v2 adds the formatting block only. Every v1 instruction — the citation
# contract, the refusal string, the counting rules — is byte-identical and
# deliberately untouched: those were each tuned against a specific observed
# failure (see the comments inline below), and rewording them to make room for
# formatting guidance would risk regressing behaviour that took real debugging
# to get right.
PROMPT_VERSION = "v2"


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
        "rather than refusing.\n"
        # The corpus repeats the same facts across documents — a student can
        # appear in a placements table, a success-stories paragraph and an
        # interns list. Without this the same person gets counted once per
        # document they appear in, and the total is inflated.
        "The same person or item often appears in several of the numbered "
        "documents; count each one ONCE, no matter how many documents mention "
        "it.\n"
        # Observed: "there are 6 students: 1. …8. … Wait, counting the names
        # again … that makes a total of 8." Correct final number, arrived at in
        # front of the user. Counting across a dozen chunks is exactly where
        # the model wants to think aloud, so the answer has to be the
        # conclusion only.
        "Work out any count before you begin writing. Give only the final "
        "answer — never narrate your counting, and never correct yourself "
        "mid-answer.\n\n"
        # Formatting. The renderer supports GitHub-flavoured markdown, so
        # structure the model emits is structure the reader actually sees —
        # before this block it emitted flat prose and the UI had nothing to
        # render. Deliberately framed as "match the shape of the content"
        # rather than "use headings": told to use structure unconditionally,
        # models wrap a one-line answer in a heading and a two-row table,
        # which is harder to read than the sentence it replaced.
        "Format the answer in markdown, matching the structure to the content:\n"
        "- Short factual answers stay as one or two plain sentences. Do not "
        "add headings or tables to an answer that does not need them.\n"
        "- Use `-` bullets for unordered points, and `1.` for sequences or "
        "ranked items.\n"
        "- Use a markdown table when comparing several items across the same "
        "fields (fees per programme, eligibility per category). Never use a "
        "table for a single item.\n"
        "- Use `## ` headings only when the answer genuinely covers several "
        "distinct topics.\n"
        "- Use `> [!NOTE]` for a deadline or condition the reader could "
        "easily miss, `> [!WARNING]` for a consequence of getting it wrong, "
        "and `> [!TIP]` for optional advice. At most one per answer, and only "
        "when the context actually states it.\n"
        "- Put exact figures, dates and identifiers in the sentence itself, "
        "not in a code block. Code fences are for code only.\n\n"
        f"{history_block}"
        f"Context:\n{context}\n\n"
        f"Question: {question}\n\n"
        "Answer:"
    )
