"""Context loaders for harness LLM phases.

These provide project-level data (WBS codes, variations, provisional sums) and
format-specific playbook content that LLM phases need.
"""

import json
import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.harness.prompts import load_playbook
from app.models.wbs_code import WBSLevel
from app.repos import harness_repo, provisional_sum_repo, variation_repo, wbs_code_repo

logger = logging.getLogger(__name__)

FALLBACK_PLAYBOOK = (
    "(No format-specific playbook available. "
    "Use the document's column headers and structure to determine field mapping.)"
)


async def load_wbs_context(
    db: AsyncSession,
    project_id: uuid.UUID,
    session_id: uuid.UUID,
) -> dict[str, str]:
    """Load project WBS categories and subcategories for the categorisation prompt."""
    all_wbs = await wbs_code_repo.get_by_project(db, project_id)

    parent_categories = [w for w in all_wbs if w.level == WBSLevel.category]
    subcategories = [w for w in all_wbs if w.level == WBSLevel.subcategory]

    categories_text = "\n".join(
        f"- id={w.id} | code={w.code}: {w.description}" for w in parent_categories
    )

    if subcategories:
        parent_map = {w.id: w.code for w in parent_categories}
        subcategories_text = "\n".join(
            f"- id={w.id} | code={w.code}: {w.description} "
            f"(parent: {parent_map.get(w.parent_id, '?')}) | contract_sum={w.contract_sum or 'N/A'}"
            for w in subcategories
        )
    else:
        subcategories_text = "(none yet — you must create new subcategories for all items)"

    return {
        "wbs_categories": categories_text,
        "wbs_subcategories": subcategories_text,
    }


async def load_variations_context(
    db: AsyncSession,
    project_id: uuid.UUID,
    session_id: uuid.UUID,
) -> dict[str, str]:
    """Load existing variations and provisional sums for the matching prompt."""
    variations = await variation_repo.get_by_project(db, project_id)
    provisional_sums = await provisional_sum_repo.get_by_project(db, project_id)

    if variations:
        variations_text = "\n".join(
            f'- id={v.id} | ci_number={v.ci_number} | contractor_ref="{v.contractor_ref or ""}" '
            f'| description="{v.description}" | submission={v.contractor_submission} '
            f"| approved={v.approved_amount or 'N/A'} | status={v.status.value}"
            for v in variations
        )
    else:
        variations_text = "(no existing variations — all items will be new)"

    if provisional_sums:
        ps_text = "\n".join(
            f'- id={ps.id} | ps_number={ps.ps_number} | description="{ps.description}" '
            f"| contract_sum={ps.contract_sum} | approved={ps.approved_amount or 'N/A'}"
            for ps in provisional_sums
        )
    else:
        ps_text = "(no existing provisional sums — all items will be new)"

    return {
        "existing_variations": variations_text,
        "existing_provisional_sums": ps_text,
    }


async def load_format_playbook(
    db: AsyncSession,
    project_id: uuid.UUID,
    session_id: uuid.UUID,
) -> dict[str, str]:
    """Load format-specific playbook based on format_detection.json."""
    raw = await harness_repo.read_workspace_file(db, session_id, "format_detection.json")
    if not raw:
        logger.warning("format_detection.json not found — using fallback playbook")
        return {"playbook_content": FALLBACK_PLAYBOOK}

    try:
        detection = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("format_detection.json is invalid JSON — using fallback playbook")
        return {"playbook_content": FALLBACK_PLAYBOOK}

    fmt = detection.get("format", "generic")
    try:
        playbook_text = load_playbook(fmt)
    except FileNotFoundError:
        logger.warning("No playbook found for format '%s' — using fallback", fmt)
        return {"playbook_content": FALLBACK_PLAYBOOK}
    logger.info("Loaded playbook for format '%s' (%d chars)", fmt, len(playbook_text))
    return {"playbook_content": playbook_text}
