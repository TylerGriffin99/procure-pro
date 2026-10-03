import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.claim import Claim


async def create(db: AsyncSession, **kwargs) -> Claim:
    claim = Claim(**kwargs)
    db.add(claim)
    await db.flush()
    return claim


async def get_by_project(db: AsyncSession, project_id: uuid.UUID) -> list[Claim]:
    result = await db.execute(
        select(Claim)
        .options(selectinload(Claim.line_items))
        .where(Claim.project_id == project_id)
        .order_by(Claim.claim_number)
    )
    return list(result.scalars().all())


async def get_by_id(db: AsyncSession, claim_id: uuid.UUID, project_id: uuid.UUID | None = None) -> Claim | None:
    stmt = select(Claim).options(selectinload(Claim.line_items)).where(Claim.id == claim_id)
    if project_id is not None:
        stmt = stmt.where(Claim.project_id == project_id)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def delete(db: AsyncSession, claim: Claim) -> None:
    await db.delete(claim)
    await db.flush()


async def delete_by_project(db: AsyncSession, project_id: uuid.UUID) -> None:
    result = await db.execute(
        select(Claim).where(Claim.project_id == project_id)
    )
    for claim in result.scalars().all():
        await db.delete(claim)
    await db.flush()
