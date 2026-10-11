import uuid

from fastapi import APIRouter

from app.dependencies import CurrentUser, DbSession
from app.schemas.claim_flag import ClaimParseFlagResponse, ResolveFlagRequest
from app.services import claim_flag_service

router = APIRouter(prefix="/projects/{project_id}/claims/{claim_id}/flags", tags=["claim_flags"])


@router.get("", response_model=list[ClaimParseFlagResponse])
async def list_flags(project_id: uuid.UUID, claim_id: uuid.UUID, db: DbSession, user: CurrentUser):
    return await claim_flag_service.list_flags(db, claim_id)


@router.patch("/{flag_id}", response_model=ClaimParseFlagResponse)
async def resolve_flag(
    project_id: uuid.UUID,
    claim_id: uuid.UUID,
    flag_id: uuid.UUID,
    body: ResolveFlagRequest,
    db: DbSession,
    user: CurrentUser,
):
    return await claim_flag_service.set_resolved(db, flag_id, resolved=body.resolved, user_id=user.id)
