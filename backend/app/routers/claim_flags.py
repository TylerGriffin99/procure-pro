"""Claim parse flags API."""

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.claim_flag import ClaimParseFlagResponse, ResolveFlagRequest
from app.services import claim_flag_service

router = APIRouter(prefix="/projects/{project_id}/claims/{claim_id}/flags", tags=["claim_flags"])


@router.get("", response_model=list[ClaimParseFlagResponse])
async def list_flags(
    project_id: uuid.UUID,
    claim_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await claim_flag_service.list_flags(db, claim_id)


@router.patch("/{flag_id}", response_model=ClaimParseFlagResponse)
async def resolve_flag(
    project_id: uuid.UUID,
    claim_id: uuid.UUID,
    flag_id: uuid.UUID,
    body: ResolveFlagRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await claim_flag_service.set_resolved(
        db, flag_id, resolved=body.resolved, user_id=user.id
    )
