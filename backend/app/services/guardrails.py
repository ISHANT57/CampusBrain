import re

# Basic indirect-prompt-injection mitigation (M40). This is mitigation, not a
# full solve — it strips the most common instruction-hijacking phrases that a
# malicious uploaded document might contain before that text reaches the LLM.
_INJECTION_PATTERNS = [
    r"ignore (all |any |the )?(previous|prior|above) (instructions|prompts?)",
    r"disregard (all |any |the )?(previous|prior|above) (instructions|prompts?)",
    r"you are now\b",
    r"system prompt\b",
    r"forget (everything|all previous)",
]

_compiled = [re.compile(p, re.IGNORECASE) for p in _INJECTION_PATTERNS]


def sanitize_context(text: str) -> str:
    for pattern in _compiled:
        text = pattern.sub("[removed]", text)
    return text
