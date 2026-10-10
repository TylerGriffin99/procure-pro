import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.provisional_sum import ProvisionalSum


async def create(db: AsyncSession, **kwargs) -> ProvisionalSum:
    ps = ProvisionalSum(**kwargs)
    db.add(ps)
    await db.flush()
    return ps


async def get_by_id(db: AsyncSession, ps_id: uuid.UUID) -> ProvisionalSum | None:
    return await db.get(ProvisionalSum, ps_id)


async def get_by_project(db: AsyncSession, project_id: uuid.UUID) -> list[ProvisionalSum]:
    result = await db.execute(select(ProvisionalSum).where(ProvisionalSum.project_id == project_id))
    return list(result.scalars().all())


async def get_max_ps_number(db: AsyncSession, project_id: uuid.UUID) -> int:
    result = await db.execute(
        select(func.coalesce(func.max(ProvisionalSum.ps_number), 0)).where(
            ProvisionalSum.project_id == project_id
        )
    )
    return result.scalar_one()


async def update(db: AsyncSession, ps: ProvisionalSum, **kwargs) -> ProvisionalSum:
    for field, value in kwargs.items():
        setattr(ps, field, value)
    await db.flush()
    return ps


async def delete(db: AsyncSession, ps: ProvisionalSum) -> None:
    await db.delete(ps)
    await db.flush()


async def delete_by_project(db: AsyncSession, project_id: uuid.UUID) -> None:
    result = await db.execute(select(ProvisionalSum).where(ProvisionalSum.project_id == project_id))
    for ps in result.scalars().all():
        await db.delete(ps)
    await db.flush()
