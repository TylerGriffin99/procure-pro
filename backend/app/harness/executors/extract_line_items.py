"""Phase 2: Extract line items — routes to format-specific parser or LLM fallback."""

import logging
import uuid
from typing import Any, assert_never

from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.llm_client import LlmClient
from app.constants.enums import ClaimFormat, WorkspaceFile
from app.harness.executors.extract_generic import parse_generic
from app.harness.executors.extract_wbpro import parse_wbpro
from app.harness.schemas import FormatDetection, ParsedClaim, RawExtraction
from app.repos import harness_repo

logger = logging.getLogger(__name__)


async def execute_extract_line_items(
    *,
    db: AsyncSession,
    session_id: uuid.UUID,
    user_id: uuid.UUID,
    project_id: uuid.UUID,
    config: dict[str, Any],
    llm: LlmClient,
) -> ParsedClaim:
    fmt_raw = await harness_repo.read_workspace_file(db, session_id, WorkspaceFile.format_detection)
    if not fmt_raw:
        raise ValueError("format_detection.json not found — Phase 1 must run first")
    detection = FormatDetection.model_validate_json(fmt_raw)

    raw_text = await harness_repo.read_workspace_file(db, session_id, WorkspaceFile.raw_extraction)
    if not raw_text:
        raise ValueError("raw_extraction.json not found — Phase 0 must run first")
    raw_extraction = RawExtraction.model_validate_json(raw_text)

    match detection.format:
        case ClaimFormat.wbpro:
            logger.info("Phase 2: Using deterministic WBPRO parser")
            return parse_wbpro(raw_extraction)
        case ClaimFormat.generic:
            logger.info("Phase 2: Using generic LLM extractor for format '%s'", detection.format)
            return await parse_generic(raw_extraction, llm=llm)
        case _:
            assert_never(detection.format)
