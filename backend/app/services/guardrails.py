"""Content guardrails for uploaded claim documents.

Screens untrusted document text at the ingestion boundary for prompt-injection
phrasing and embedded code/scripts. A cheap first-line defence — not a guarantee
against obfuscated attacks. Once a document is persisted it is treated as clean.
"""
import re
import unicodedata
from dataclasses import dataclass

# Phrases that attempt to override or hijack an LLM's instructions. Kept specific
# enough that ordinary construction-claim prose does not trip them.
_INJECTION_PATTERNS = [
    r"ignore\s+(?:all\s+|any\s+)?(?:previous|prior|above|earlier)\s+instructions",
    r"disregard\s+(?:the\s+)?(?:previous|above|system)\b",
    r"forget\s+(?:everything|all\s+(?:previous|prior))\b",
    r"you\s+are\s+now\s+(?:a|an)\b",
    r"new\s+instructions\s*:",
    r"system\s+prompt\b",
    r"act\s+as\s+(?:an?\s+)?(?:ai|assistant|language\s+model|chatbot|llm)\b",
    r"pretend\s+(?:to\s+be|you\s+are)\b",
    r"jailbreak\b",
    r"\bdeveloper\s+mode\b",
]

# Markers of executable code — should never appear in a contractor claim PDF.
# `(?m)` + anchors keep the python patterns from matching prose like "import duty".
_CODE_PATTERNS = [
    r"<\s*script\b",                              # <script> tags
    r"<\?php\b",                                  # PHP open tag
    r"```",                                       # markdown code fence
    r"#!/",                                       # shebang
    r"(?m)^\s*(?:import\s+\w+|from\s+\w+\s+import)\b",  # python import (line-anchored)
    r"\bdef\s+\w+\s*\(",                          # python def
    r"\b(?:exec|eval)\s*\(",                      # exec/eval calls
    r"\b(?:os\.system|subprocess|__import__)\b",
    r"\brm\s+-rf\b",                              # destructive shell
    r"\bcurl\b[^\n]*\|\s*(?:ba)?sh\b",            # curl ... | sh
]

_INJECTION_RE = [re.compile(p, re.IGNORECASE) for p in _INJECTION_PATTERNS]
_CODE_RE = [re.compile(p, re.IGNORECASE) for p in _CODE_PATTERNS]

# Zero-width / invisible characters used to break up trigger phrases.
_ZERO_WIDTH = dict.fromkeys(map(ord, "​‌‍⁠﻿"), None)


@dataclass(frozen=True)
class Violation:
    category: str  # "prompt_injection" | "code"
    snippet: str   # the matched text, for the server-side log


def screen_text(text: str) -> list[Violation]:
    """Return violations found in `text`; an empty list means the text is clean.

    Normalises unicode (NFKC + strips zero-width chars) first so simple homoglyph
    and invisible-character evasions don't slip past. This is a first-line filter,
    not a guarantee against determined obfuscation.
    """
    text = unicodedata.normalize("NFKC", text).translate(_ZERO_WIDTH)
    violations: list[Violation] = []
    for rx in _INJECTION_RE:
        m = rx.search(text)
        if m:
            violations.append(Violation("prompt_injection", m.group(0).strip()))
    for rx in _CODE_RE:
        m = rx.search(text)
        if m:
            violations.append(Violation("code", m.group(0).strip()))
    return violations
