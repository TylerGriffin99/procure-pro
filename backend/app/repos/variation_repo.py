import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.variation import Variation


async def create(db: AsyncSession, **kwargs) -> Variation:
    variation = Variation(**kwargs)
    db.add(variation)
    await db.flush()
    return variation


async def get_by_project(db: AsyncSession, project_id: uuid.UUID) -> list[Variation]:
    result = await db.execute(select(Variation).where(Variation.project_id == project_id))
    return list(result.scalars().all())


async def get_max_ci_number(db: AsyncSession, project_id: uuid.UUID) -> int:
    result = await db.execute(
        select(func.coalesce(func.max(Variation.ci_number), 0)).where(Variation.project_id == project_id)
    )
    return result.scalar_one()


async def delete_by_project(db: AsyncSession, project_id: uuid.UUID) -> None:
    result = await db.execute(select(Variation).where(Variation.project_id == project_id))
    for variation in result.scalars().all():
        await db.delete(variation)
    await db.flush()
