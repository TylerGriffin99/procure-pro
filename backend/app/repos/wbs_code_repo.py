import uuid

from sqlalchemy import exists, select, union_all
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.assessment_line_item import AssessmentLineItem
from app.models.claim_line_item import ClaimLineItem
from app.models.provisional_sum import ProvisionalSum
from app.models.variation import Variation
from app.models.wbs_code import WBSCode


async def create(db: AsyncSession, **kwargs) -> WBSCode:
    wbs = WBSCode(**kwargs)
    db.add(wbs)
    await db.flush()
    return wbs


async def get_by_project(db: AsyncSession, project_id: uuid.UUID) -> list[WBSCode]:
    result = await db.execute(select(WBSCode).where(WBSCode.project_id == project_id))
    return list(result.scalars().all())


async def get_by_id(db: AsyncSession, wbs_code_id: uuid.UUID) -> WBSCode | None:
    return await db.get(WBSCode, wbs_code_id)


async def get_by_id_with_children(db: AsyncSession, wbs_code_id: uuid.UUID) -> WBSCode | None:
    result = await db.execute(
        select(WBSCode).where(WBSCode.id == wbs_code_id).options(selectinload(WBSCode.children))
    )
    return result.scalar_one_or_none()


async def delete(db: AsyncSession, wbs: WBSCode) -> None:
    await db.delete(wbs)


async def update(db: AsyncSession, wbs: WBSCode, **kwargs) -> WBSCode:
    for field, value in kwargs.items():
        setattr(wbs, field, value)
    await db.flush()
    return wbs


async def is_in_use(db: AsyncSession, wbs_code_id: uuid.UUID) -> bool:
    """Check if a WBS code is referenced by any claim or assessment line items."""
    assessment_ref = await db.execute(
        select(exists().where(AssessmentLineItem.wbs_code_id == wbs_code_id))
    )
    if assessment_ref.scalar():
        return True

    claim_ref = await db.execute(
        select(exists().where(ClaimLineItem.suggested_wbs_code_id == wbs_code_id))
    )
    if claim_ref.scalar():
        return True

    for col in [Variation.wbs_code_id, ProvisionalSum.wbs_code_id]:
        ref = await db.execute(select(exists().where(col == wbs_code_id)))
        if ref.scalar():
            return True

    return False


async def get_in_use_ids(db: AsyncSession, wbs_code_ids: list[uuid.UUID]) -> set[uuid.UUID]:
    """Return the subset of wbs_code_ids that are referenced by any record (batch query)."""
    if not wbs_code_ids:
        return set()

    # A compound (UNION ALL) select must be wrapped in a subquery before its
    # columns can be selected from; the column name comes from the first leg.
    subq = union_all(
        select(AssessmentLineItem.wbs_code_id.label("wbs_code_id")).where(
            AssessmentLineItem.wbs_code_id.in_(wbs_code_ids)
        ),
        select(ClaimLineItem.suggested_wbs_code_id.label("wbs_code_id")).where(
            ClaimLineItem.suggested_wbs_code_id.in_(wbs_code_ids)
        ),
        select(Variation.wbs_code_id.label("wbs_code_id")).where(
            Variation.wbs_code_id.in_(wbs_code_ids)
        ),
        select(ProvisionalSum.wbs_code_id.label("wbs_code_id")).where(
            ProvisionalSum.wbs_code_id.in_(wbs_code_ids)
        ),
    ).subquery()
    result = await db.execute(select(subq.c.wbs_code_id).distinct())
    return set(result.scalars().all())
