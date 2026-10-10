import uuid

from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.claim import ClaimCreate, ClaimResponse, ClaimUpdate, ClaimUploadResponse
from app.services import claim_service

router = APIRouter(prefix="/projects/{project_id}/claims", tags=["claims"])


@router.post("", response_model=ClaimResponse, status_code=201)
async def create_claim_manual(
    project_id: uuid.UUID,
    body: ClaimCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await claim_service.create_claim(db, project_id, body, user)


@router.post("/upload", response_model=ClaimUploadResponse, status_code=201)
async def upload_claim(
    project_id: uuid.UUID,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await claim_service.upload_claim(db, project_id, file, user)


@router.get("", response_model=list[ClaimResponse])
async def list_claims(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await claim_service.list_claims(db, project_id)


@router.get("/{claim_id}", response_model=ClaimResponse)
async def get_claim(
    project_id: uuid.UUID,
    claim_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await claim_service.get_claim(db, project_id, claim_id)


@router.patch("/{claim_id}", response_model=ClaimResponse)
async def update_claim(
    project_id: uuid.UUID,
    claim_id: uuid.UUID,
    body: ClaimUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await claim_service.update_claim(db, project_id, claim_id, body)


@router.delete("/{claim_id}", status_code=204)
async def delete_claim(
    project_id: uuid.UUID,
    claim_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    await claim_service.delete_claim(db, project_id, claim_id)
