import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.assessment_variation import AssessmentVariation


async def get_by_id(
    db: AsyncSession,
    item_id: uuid.UUID,
    assessment_id: uuid.UUID,
) -> AssessmentVariation | None:
    result = await db.execute(
        select(AssessmentVariation)
        .options(selectinload(AssessmentVariation.variation))
        .where(
            AssessmentVariation.id == item_id,
            AssessmentVariation.assessment_id == assessment_id,
        )
    )
    return result.scalar_one_or_none()


async def create(db: AsyncSession, **kwargs) -> AssessmentVariation:
    item = AssessmentVariation(**kwargs)
    db.add(item)
    await db.flush()
    return item


async def update(db: AsyncSession, item: AssessmentVariation, **kwargs) -> AssessmentVariation:
    for key, value in kwargs.items():
        setattr(item, key, value)
    await db.flush()
    return item


async def delete(db: AsyncSession, item: AssessmentVariation) -> None:
    await db.delete(item)
    await db.flush()
