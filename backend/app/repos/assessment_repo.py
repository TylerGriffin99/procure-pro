import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.constants.enums import AssessmentStatus
from app.models.assessment import Assessment
from app.models.assessment_line_item import AssessmentLineItem
from app.models.assessment_provisional_sum import AssessmentProvisionalSum
from app.models.assessment_variation import AssessmentVariation
from app.schemas.assessment_aggregate import AssessmentRows, AssessmentRowValues

VPS_ROW_EXCLUDE = {"master_id", "description", "sort_order"}


def _eager_options() -> list:
    return [
        selectinload(Assessment.line_items),
        selectinload(Assessment.variation_items).selectinload(AssessmentVariation.variation),
        selectinload(Assessment.provisional_sum_items).selectinload(AssessmentProvisionalSum.provisional_sum),
    ]


def line_item_row(values: AssessmentRowValues) -> AssessmentLineItem:
    return AssessmentLineItem(**values.model_dump(exclude={"master_id"}), wbs_code_id=values.master_id)


def variation_row(values: AssessmentRowValues) -> AssessmentVariation:
    return AssessmentVariation(**values.model_dump(exclude=VPS_ROW_EXCLUDE), variation_id=values.master_id)


def provisional_sum_row(values: AssessmentRowValues) -> AssessmentProvisionalSum:
    return AssessmentProvisionalSum(**values.model_dump(exclude=VPS_ROW_EXCLUDE), provisional_sum_id=values.master_id)


async def create(db: AsyncSession, *, rows: AssessmentRows, **fields: Any) -> Assessment:
    assessment = Assessment(
        **fields,
        line_items=[line_item_row(r) for r in rows.line_items],
        variation_items=[variation_row(r) for r in rows.variation_items],
        provisional_sum_items=[provisional_sum_row(r) for r in rows.provisional_sum_items],
    )
    db.add(assessment)
    await db.flush()
    return assessment


async def update(db: AsyncSession, assessment: Assessment, **fields: Any) -> Assessment:
    for field, value in fields.items():
        setattr(assessment, field, value)
    await db.flush()
    return assessment


async def add(db: AsyncSession, assessment: Assessment) -> Assessment:
    """Persist a fully-constructed Assessment object (with nested children)."""
    db.add(assessment)
    await db.flush()
    return assessment


async def get_by_id(
    db: AsyncSession, assessment_id: uuid.UUID, project_id: uuid.UUID | None = None
) -> Assessment | None:
    stmt = select(Assessment).options(*_eager_options()).where(Assessment.id == assessment_id)
    if project_id is not None:
        stmt = stmt.where(Assessment.project_id == project_id)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def get_latest_by_claim(
    db: AsyncSession, claim_id: uuid.UUID, project_id: uuid.UUID | None = None
) -> Assessment | None:
    stmt = (
        select(Assessment)
        .options(*_eager_options())
        .where(Assessment.claim_id == claim_id)
        .order_by(Assessment.version.desc())
    )
    if project_id is not None:
        stmt = stmt.where(Assessment.project_id == project_id)
    result = await db.execute(stmt)
    return result.scalars().first()


async def next_version_number(db: AsyncSession, claim_id: uuid.UUID) -> int:
    result = await db.execute(
        select(func.coalesce(func.max(Assessment.version), 0) + 1).where(Assessment.claim_id == claim_id)
    )
    return result.scalar_one()


async def get_latest_finalised(db: AsyncSession, project_id: uuid.UUID) -> Assessment | None:
    result = await db.execute(
        select(Assessment)
        .options(*_eager_options())
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
