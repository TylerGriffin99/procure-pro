import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.project import (
    ProjectCreate, ProjectResponse, ProjectUpdate,
    WBSCodeCreate, WBSCodeResponse, WBSCodeUpdate,
)
from app.services import project_service

router = APIRouter(prefix="/api/projects", tags=["projects"])


@router.post("", response_model=ProjectResponse, status_code=201)
async def create_project(
    project_in: ProjectCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await project_service.create_project(db, project_in, user)


@router.get("", response_model=list[ProjectResponse])
async def list_projects(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await project_service.list_projects(db)


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await project_service.get_project(db, project_id)


@router.patch("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: uuid.UUID,
    body: ProjectUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await project_service.update_project(db, project_id, body, user)


@router.delete("/{project_id}", status_code=204)
async def delete_project(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    await project_service.delete_project(db, project_id)


@router.post("/{project_id}/wbs", response_model=WBSCodeResponse, status_code=201)
async def create_wbs_code(
    project_id: uuid.UUID,
    body: WBSCodeCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await project_service.create_wbs_code(db, project_id, body, user)


@router.patch("/{project_id}/wbs/{wbs_code_id}", response_model=WBSCodeResponse)
async def update_wbs_code(
    project_id: uuid.UUID,
    wbs_code_id: uuid.UUID,
    body: WBSCodeUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await project_service.update_wbs_code(db, project_id, wbs_code_id, body, user)
