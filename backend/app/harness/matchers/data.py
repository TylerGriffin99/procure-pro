"""Typed data providers for matchers (records, not prompt strings).

Mirrors the queries in ``app.harness.context_loaders``.
"""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.constants.enums import ClaimItemType, WBSLevel, WorkspaceFile
from app.harness.phase_context import load_workspace
from app.harness.schemas import ParsedClaim, ParsedClaimItem, Subcat, VpsRecord
from app.repos import provisional_sum_repo, variation_repo, wbs_code_repo


def _num(v) -> float | None:
    return float(v) if v is not None else None


async def wbs_subcategories(*, db, project_id) -> list[Subcat]:
    rows = await wbs_code_repo.get_by_project(db, project_id)
    parent_map = {w.id: w.code for w in rows if w.level == WBSLevel.category}
    return [
        Subcat(
            id=str(w.id),
            code=w.code,
            description=w.description or "",
            parent_code=parent_map.get(w.parent_id, "") if w.parent_id else "",
            contract_sum=_num(w.contract_sum),
        )
        for w in rows
        if w.level == WBSLevel.subcategory
    ]


async def vps_records(*, db, project_id) -> list[VpsRecord]:
    variations = await variation_repo.get_by_project(db, project_id)
    sums = await provisional_sum_repo.get_by_project(db, project_id)
    out = [
        VpsRecord(
            id=str(v.id),
            description=v.description or "",
            value=_num(v.contractor_submission),
            item_type=ClaimItemType.variation.value,
        )
        for v in variations
    ]
    out += [
        VpsRecord(
            id=str(p.id),
            description=p.description or "",
            value=_num(p.contract_sum),
            item_type=ClaimItemType.provisional_sum.value,
        )
        for p in sums
    ]
    return out


async def read_parsed_items(db: AsyncSession, session_id: uuid.UUID) -> list[ParsedClaimItem]:
    parsed = await load_workspace(db, session_id, WorkspaceFile.parsed_claim, ParsedClaim.model_validate_json)
    return parsed.line_items
