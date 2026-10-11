"""Content guardrails for uploaded claim documents.

Screens untrusted document text at the ingestion boundary for prompt-injection
phrasing and embedded code/scripts. A cheap first-line defence — not a guarantee
against obfuscated attacks. Once a document is persisted it is treated as clean.
"""

import logging
import re
import unicodedata
from io import BytesIO
from typing import Final

import pdfplumber
from pdfminer.psexceptions import PSException
from pdfplumber.utils.exceptions import MalformedPDFException, PdfminerException

from app.constants.enums import ViolationCategory
from app.exceptions import BadRequestError
from app.schemas.guardrails import Violation

logger = logging.getLogger(__name__)

# Deterministic "this is not a readable PDF" faults; anything else is a server fault (500).
PARSER_FAULTS: Final = (PSException, MalformedPDFException, PdfminerException, ValueError)

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
    r"<\s*script\b",  # <script> tags
    r"<\?php\b",  # PHP open tag
    r"```",  # markdown code fence
    r"#!/",  # shebang
    r"(?m)^\s*(?:import\s+\w+|from\s+\w+\s+import)\b",  # python import (line-anchored)
    r"\bdef\s+\w+\s*\(",  # python def
    r"\b(?:exec|eval)\s*\(",  # exec/eval calls
    r"\b(?:os\.system|subprocess|__import__)\b",
    r"\brm\s+-rf\b",  # destructive shell
    r"\bcurl\b[^\n]*\|\s*(?:ba)?sh\b",  # curl ... | sh
]

_INJECTION_RE = [re.compile(p, re.IGNORECASE) for p in _INJECTION_PATTERNS]
_CODE_RE = [re.compile(p, re.IGNORECASE) for p in _CODE_PATTERNS]

# Zero-width / invisible characters used to break up trigger phrases.
_ZERO_WIDTH = dict.fromkeys(map(ord, "​‌‍⁠﻿"), None)


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
            violations.append(Violation(category=ViolationCategory.prompt_injection, snippet=m.group(0).strip()))
    for rx in _CODE_RE:
        m = rx.search(text)
        if m:
            violations.append(Violation(category=ViolationCategory.code, snippet=m.group(0).strip()))
    return violations


def wrapped_cause(exc: BaseException) -> BaseException:
    # pdfplumber wraps EVERY error raised while opening or interpreting a page as PdfminerException(original).
    if isinstance(exc, PdfminerException) and exc.args and isinstance(exc.args[0], BaseException):
        return exc.args[0]
    return exc


def extract_screenable_text(content: bytes) -> str:
    """Return the page text + table-cell text a PDF would expose downstream.

    Mirrors what raw_extraction feeds the LLM phases (text and tables) so the
    screen covers the same surface. Raises if the PDF cannot be read.
    """
    parts: list[str] = []
    with pdfplumber.open(BytesIO(content)) as pdf:
        if len(pdf.pages) == 0:
            raise ValueError("PDF has zero pages")
        for page in pdf.pages:
            parts.append(page.extract_text() or "")
            for table in page.extract_tables() or []:
                for row in table:
                    parts.extend(cell for cell in row if cell)
    return "\n".join(parts)


def screen_pdf(content: bytes) -> None:
    """Reject the upload unless it can be read AND is free of disallowed content.

    This is the ingestion trust boundary: a document only reaches the DB if it was
    successfully screened and found clean, so downstream code can treat stored
    documents as trusted. We fail CLOSED — an unreadable PDF is rejected rather
    than stored unscreened, because the screen and a downstream reader are not
    guaranteed to fail on the same inputs.
    """
    try:
        text = extract_screenable_text(content)
    except PARSER_FAULTS as e:
        cause = wrapped_cause(e)
        if not isinstance(cause, PARSER_FAULTS):
            raise cause from e
        logger.warning("Rejected upload: PDF could not be read for screening", exc_info=True)
        raise BadRequestError("Could not read the PDF to screen it") from e

    if not text.strip():
        # Parsed, but yielded no text/tables to screen (e.g. an image-only scan).
        # Fail closed: we can't vouch for content we couldn't extract.
        logger.warning("Rejected upload: PDF has no extractable text to screen")
        raise BadRequestError("PDF has no extractable text to screen")

    violations = screen_text(text)
    if violations:
        categories = sorted({v.category for v in violations})
        # Snippets are attacker-controlled: log them (repr guards against log
        # injection) but never reflect them to the client.
        snippets = "; ".join(f"{v.category}:{v.snippet!r}" for v in violations)
        logger.warning("Rejected upload: disallowed content [%s] — %s", ", ".join(categories), snippets)
        raise BadRequestError(f"Document rejected: it contains disallowed content ({', '.join(categories)})")
