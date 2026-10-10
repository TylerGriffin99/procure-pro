import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.claim_line_item import ClaimLineItem


async def get_by_id(db: AsyncSession, item_id: uuid.UUID) -> ClaimLineItem | None:
    result = await db.execute(select(ClaimLineItem).where(ClaimLineItem.id == item_id))
    return result.scalar_one_or_none()
