import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.assessment import Assessment, AssessmentStatus
from app.models.assessment_provisional_sum import AssessmentProvisionalSum
from app.models.assessment_variation import AssessmentVariation


def _eager_options(
    *, with_line_items: bool = True, with_variations: bool = True, with_provisional_sums: bool = True
) -> list:
    """Build a list of selectinload options for Assessment queries."""
    opts: list = []
    if with_line_items:
        opts.append(selectinload(Assessment.line_items))
    if with_variations:
        opts.append(selectinload(Assessment.variation_items).selectinload(AssessmentVariation.variation))
    if with_provisional_sums:
        opts.append(
            selectinload(Assessment.provisional_sum_items).selectinload(AssessmentProvisionalSum.provisional_sum)
        )
    return opts


async def create(db: AsyncSession, **kwargs) -> Assessment:
    assessment = Assessment(**kwargs)
    db.add(assessment)
    await db.flush()
    return assessment


async def add(db: AsyncSession, assessment: Assessment) -> Assessment:
    """Persist a fully-constructed Assessment object (with nested children)."""
    db.add(assessment)
    await db.flush()
    return assessment


async def get_by_id(
    db: AsyncSession,
    assessment_id: uuid.UUID,
    project_id: uuid.UUID | None = None,
    *,
    with_line_items: bool = True,
    with_variations: bool = True,
    with_provisional_sums: bool = True,
) -> Assessment | None:
    stmt = (
        select(Assessment)
        .options(
            *_eager_options(
                with_line_items=with_line_items,
                with_variations=with_variations,
                with_provisional_sums=with_provisional_sums,
            )
        )
        .where(Assessment.id == assessment_id)
    )
    if project_id is not None:
        stmt = stmt.where(Assessment.project_id == project_id)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def get_latest_by_claim(
    db: AsyncSession,
    claim_id: uuid.UUID,
    project_id: uuid.UUID | None = None,
    *,
    with_line_items: bool = True,
    with_variations: bool = True,
    with_provisional_sums: bool = True,
) -> Assessment | None:
    stmt = (
        select(Assessment)
        .options(
            *_eager_options(
                with_line_items=with_line_items,
                with_variations=with_variations,
                with_provisional_sums=with_provisional_sums,
            )
        )
        .where(Assessment.claim_id == claim_id)
        .order_by(Assessment.version.desc())
    )
    if project_id is not None:
        stmt = stmt.where(Assessment.project_id == project_id)
    result = await db.execute(stmt)
    return result.scalars().first()


async def get_latest_version_number(db: AsyncSession, claim_id: uuid.UUID) -> int:
    result = await db.execute(
        select(Assessment).where(Assessment.claim_id == claim_id).order_by(Assessment.version.desc())
    )
    latest = result.scalar_one_or_none()
    return latest.version if latest else 0


async def get_latest_finalised(
    db: AsyncSession,
    project_id: uuid.UUID,
    *,
    with_line_items: bool = True,
    with_variations: bool = True,
    with_provisional_sums: bool = True,
) -> Assessment | None:
    result = await db.execute(
        select(Assessment)
        .options(
            *_eager_options(
                with_line_items=with_line_items,
                with_variations=with_variations,
                with_provisional_sums=with_provisional_sums,
            )
        )
        .where(Assessment.project_id == project_id, Assessment.status == AssessmentStatus.finalised)
        .order_by(Assessment.created_at.desc())
    )
    return result.scalars().first()


async def delete_by_claim(db: AsyncSession, claim_id: uuid.UUID) -> None:
    result = await db.execute(select(Assessment).where(Assessment.claim_id == claim_id))
    for assessment in result.scalars().all():
        await db.delete(assessment)


async def delete_by_project(db: AsyncSession, project_id: uuid.UUID) -> None:
    """Delete all assessments for a project and flush."""
    result = await db.execute(select(Assessment).where(Assessment.project_id == project_id))
    for assessment in result.scalars().all():
        await db.delete(assessment)
    await db.flush()
