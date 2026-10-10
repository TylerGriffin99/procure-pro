"""Claim parse flags: list and resolve/unresolve."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import NotFoundError
from app.models.claim_parse_flag import ClaimParseFlag
from app.repos import harness_repo


async def list_flags(db: AsyncSession, claim_id: uuid.UUID) -> list[ClaimParseFlag]:
    return await harness_repo.list_flags_by_claim(db, claim_id)


async def set_resolved(
    db: AsyncSession, flag_id: uuid.UUID, *, resolved: bool, user_id: uuid.UUID
) -> ClaimParseFlag:
    flag = (
        await harness_repo.resolve_flag(db, flag_id, user_id)
        if resolved
        else await harness_repo.unresolve_flag(db, flag_id)
    )
    if flag is None:
        raise NotFoundError("Flag not found")
    await db.commit()
    await db.refresh(flag)
    return flag
