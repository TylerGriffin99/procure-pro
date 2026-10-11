import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.assessment_provisional_sum import AssessmentProvisionalSum


async def get_by_id(db: AsyncSession, item_id: uuid.UUID, assessment_id: uuid.UUID) -> AssessmentProvisionalSum | None:
    result = await db.execute(
        select(AssessmentProvisionalSum)
        .options(selectinload(AssessmentProvisionalSum.provisional_sum))
        .where(AssessmentProvisionalSum.id == item_id, AssessmentProvisionalSum.assessment_id == assessment_id)
    )
    return result.scalar_one_or_none()


async def create(db: AsyncSession, **kwargs) -> AssessmentProvisionalSum:
    item = AssessmentProvisionalSum(**kwargs)
    db.add(item)
    await db.flush()
    return item


async def update(db: AsyncSession, item: AssessmentProvisionalSum, **kwargs) -> AssessmentProvisionalSum:
    for key, value in kwargs.items():
        setattr(item, key, value)
    await db.flush()
    return item


async def delete(db: AsyncSession, item: AssessmentProvisionalSum) -> None:
    await db.delete(item)
    await db.flush()
