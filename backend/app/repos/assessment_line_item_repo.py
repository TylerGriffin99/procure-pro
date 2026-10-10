import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.assessment_line_item import AssessmentLineItem


async def get_by_id(
    db: AsyncSession, line_item_id: uuid.UUID, assessment_id: uuid.UUID
) -> AssessmentLineItem | None:
    result = await db.execute(
        select(AssessmentLineItem).where(
            AssessmentLineItem.id == line_item_id,
            AssessmentLineItem.assessment_id == assessment_id,
        )
    )
    return result.scalar_one_or_none()


async def create(db: AsyncSession, **kwargs) -> AssessmentLineItem:
    item = AssessmentLineItem(**kwargs)
    db.add(item)
    await db.flush()
    return item


async def update(db: AsyncSession, item: AssessmentLineItem, **kwargs) -> AssessmentLineItem:
    for key, value in kwargs.items():
        setattr(item, key, value)
    await db.flush()
    return item


async def delete(db: AsyncSession, item: AssessmentLineItem) -> None:
    await db.delete(item)
    await db.flush()
