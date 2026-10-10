import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.claim_line_item import ClaimLineItem


async def get_by_id(db: AsyncSession, item_id: uuid.UUID) -> ClaimLineItem | None:
    result = await db.execute(select(ClaimLineItem).where(ClaimLineItem.id == item_id))
    return result.scalar_one_or_none()


async def get_by_wbs_code_id(db: AsyncSession, wbs_code_id: uuid.UUID) -> uuid.UUID | None:
    """Check if any claim line item references the given WBS code."""
    result = await db.execute(
        select(ClaimLineItem.id).where(ClaimLineItem.suggested_wbs_code_id == wbs_code_id).limit(1)
    )
    return result.scalar_one_or_none()
