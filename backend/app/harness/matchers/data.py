"""Typed data providers for matchers (records, not prompt strings).

Mirrors the queries in ``app.harness.context_loaders``.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.models.wbs_code import WBSLevel
from app.repos import provisional_sum_repo, variation_repo, wbs_code_repo


@dataclass(eq=True)
class Subcat:
    id: str
    code: str
    description: str
    parent_code: str
    contract_sum: float | None


@dataclass(eq=True)
class VpsRecord:
    id: str
    description: str
    value: float | None
    item_type: Literal["variation", "provisional_sum"]


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
        VpsRecord(id=str(v.id), description=v.description or "",
                  value=_num(v.contractor_submission), item_type="variation")
        for v in variations
    ]
    out += [
        VpsRecord(id=str(p.id), description=p.description or "",
                  value=_num(p.contract_sum), item_type="provisional_sum")
        for p in sums
    ]
    return out
