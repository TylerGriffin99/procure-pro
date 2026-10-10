"""Phase 1: Detect document format from raw extracted text."""

import json
import logging
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.repos import harness_repo

logger = logging.getLogger(__name__)

# Markers and their labels for each known format.
# Checked against ALL pages (not just the first) because section headers
# like VARIATION WORKS / PROVISIONAL SUMS often appear on page 2+.
_WBPRO_MARKERS = [
    ("Claim No.", "Claim No."),
    ("Claim Number", "Claim No."),
    ("Period From:", "Period From:"),
    ("Period To:", "Period To:"),
    ("Payment Due:", "Payment Due:"),
    ("CONTRACT WORKS", "CONTRACT WORKS"),
    ("VARIATION WORKS", "VARIATION WORKS"),
    ("PROVISIONAL SUMS", "PROVISIONAL SUMS"),
    ("CONTRACTOR PROGRESS CLAIM", "CONTRACTOR PROGRESS CLAIM"),
    ("WBPRO", "WBPRO"),
]

_WBPRO_THRESHOLD = 3  # need at least 3 markers


def detect_format(all_pages_text: str) -> dict:
    """Detect document format from full document text.

    Returns dict with 'format', 'confidence', and 'markers_found'.
    """
    markers_found = []
    for marker_text, label in _WBPRO_MARKERS:
        if marker_text in all_pages_text and label not in markers_found:
            markers_found.append(label)

    if len(markers_found) >= _WBPRO_THRESHOLD:
        confidence = min(0.7 + len(markers_found) * 0.05, 0.99)
        return {
            "format": "wbpro",
            "confidence": round(confidence, 2),
            "markers_found": markers_found,
        }

    return {
        "format": "generic",
        "confidence": 0.5,
        "markers_found": markers_found,
    }


async def execute_detect_format(
    db: AsyncSession,
    session_id: uuid.UUID,
    user_id: uuid.UUID,
    project_id: uuid.UUID,
    config: dict[str, Any],
) -> dict:
    """Read raw_extraction.json and detect the document format."""
    raw = await harness_repo.read_workspace_file(db, session_id, "raw_extraction.json")
    if not raw:
        raise ValueError("raw_extraction.json not found")

    data = json.loads(raw)
    pages = data.get("pages", [])
    all_text = "\n".join(p.get("text", "") for p in pages)

    result = detect_format(all_text)
    logger.info("Format detection: %s (confidence: %s)", result["format"], result["confidence"])
    return result
