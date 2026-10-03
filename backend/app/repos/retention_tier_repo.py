from sqlalchemy.ext.asyncio import AsyncSession

from app.models.retention_tier import RetentionTier


async def create(db: AsyncSession, **kwargs) -> RetentionTier:
    tier = RetentionTier(**kwargs)
    db.add(tier)
    await db.flush()
    return tier
