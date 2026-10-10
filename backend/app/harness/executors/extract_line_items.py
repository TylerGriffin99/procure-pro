"""Phase 2: Extract line items — routes to format-specific parser or LLM fallback."""

import json
import logging
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.harness.executors.extract_generic import parse_generic
from app.harness.executors.extract_wbpro import parse_wbpro
from app.repos import harness_repo

logger = logging.getLogger(__name__)


async def execute_extract_line_items(
    db: AsyncSession,
    session_id: uuid.UUID,
    user_id: uuid.UUID,
    project_id: uuid.UUID,
    config: dict[str, Any],
) -> dict:
    """Route extraction based on detected format.

    Reads format_detection.json and raw_extraction.json from workspace,
    then dispatches to the appropriate parser.
    """
    # Read format detection result
    fmt_raw = await harness_repo.read_workspace_file(db, session_id, "format_detection.json")
    if not fmt_raw:
        raise ValueError("format_detection.json not found — Phase 1 must run first")
    fmt = json.loads(fmt_raw)
    detected_format = fmt.get("format", "generic")

    # Read raw extraction
    raw_text = await harness_repo.read_workspace_file(db, session_id, "raw_extraction.json")
    if not raw_text:
        raise ValueError("raw_extraction.json not found — Phase 0 must run first")
    raw_extraction = json.loads(raw_text)

    if detected_format == "wbpro":
        logger.info("Phase 2: Using deterministic WBPRO parser")
        return parse_wbpro(raw_extraction)
    else:
        logger.info("Phase 2: Using generic LLM extractor for format '%s'", detected_format)
        return await parse_generic(raw_extraction)
