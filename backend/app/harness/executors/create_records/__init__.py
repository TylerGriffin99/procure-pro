import logging
import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.llm_client import LlmClient
from app.harness.executors.create_records.claim import build_claim, record_format_warnings
from app.harness.executors.create_records.history import build_assessment
from app.harness.executors.create_records.inputs import load_inputs, reclassify_provisional_sums, validate_counts
from app.harness.executors.create_records.totals import apply_totals
from app.harness.executors.create_records.vps import resolve_vps
from app.harness.executors.create_records.wbs import resolve_wbs
from app.harness.schemas import ClaimLinks, CreateRecordsInputs, CreationSummary
from app.repos import harness_repo, project_repo

__all__ = ["create_records", "execute_create_records"]

logger = logging.getLogger(__name__)


def match_confidence(inputs: CreateRecordsInputs) -> dict[int, Decimal]:
    # Confidence lives on the WBS/VPS match, keyed by the same global item_index as the line items.
    matches = [*inputs.wbs_matches, *(inputs.vps_matches or [])]
    return {m.item_index: Decimal(str(m.confidence or 0)) for m in matches}


async def create_records(
    *, inputs: CreateRecordsInputs, db: AsyncSession, project_id: uuid.UUID, user_id: uuid.UUID, session_id: uuid.UUID
) -> CreationSummary:
    project = await project_repo.get_by_id(db, project_id)
    if not project:
        raise ValueError(f"Project {project_id} not found")

    wbs = await resolve_wbs(db, project_id=project_id, user_id=user_id, matches=inputs.wbs_matches)
    parsed = reclassify_provisional_sums(inputs.parsed)
    vps = await resolve_vps(
        db, project_id=project_id, user_id=user_id, items=parsed.line_items, matches=inputs.vps_matches or []
    )
    links = ClaimLinks(wbs=wbs, vps=vps, confidence=match_confidence(inputs))
    claim = await build_claim(db, project_id=project_id, user_id=user_id, parsed=parsed, links=links)
    assessment = await build_assessment(db, project_id=project_id, user_id=user_id, claim=claim)
    assessment = await apply_totals(db, assessment=assessment, project=project)

    await record_format_warnings(db, session_id, parsed)
    await harness_repo.link_flags_to_claim(db, session_id, claim.id)
    await harness_repo.set_claim_id(db, session_id, claim.id)

    logger.info(
        "Created claim %s with %d items, assessment %s (retention: %s)",
        claim.id,
        len(claim.line_items),
        assessment.id,
        assessment.total_retention,
    )
    return CreationSummary(claim_id=claim.id, assessment_id=assessment.id, line_items_created=len(claim.line_items))


async def execute_create_records(
    *,
    db: AsyncSession,
    session_id: uuid.UUID,
    user_id: uuid.UUID,
    project_id: uuid.UUID,
    config: dict[str, Any],
    llm: LlmClient,
) -> CreationSummary:
    inputs = validate_counts(await load_inputs(db, session_id))
    return await create_records(inputs=inputs, db=db, project_id=project_id, user_id=user_id, session_id=session_id)
