"""Harness SSE streaming + lifecycle endpoints."""

import uuid

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.harness import (
    HarnessCancelResponse,
    HarnessRerunResponse,
    HarnessSessionResponse,
    WorkspaceFileContentResponse,
    WorkspaceFileResponse,
)
from app.services import harness_service

router = APIRouter(prefix="/harness", tags=["harness"])

SSE_HEADERS = {"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"}


@router.get("/sessions/{session_id}", response_model=HarnessSessionResponse)
async def get_harness_session(
    session_id: uuid.UUID, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)
):
    return await harness_service.get_session(db, session_id, user)


@router.get("/sessions/{session_id}/stream")
async def stream_harness_session(
    session_id: uuid.UUID, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)
) -> StreamingResponse:
    session, definition = await harness_service.prepare_stream(db, session_id, user)
    events = harness_service.stream_events(
        definition=definition, session_id=session.id, user_id=user.id, project_id=session.project_id
    )
    return StreamingResponse(events, media_type="text/event-stream", headers=SSE_HEADERS)


@router.post("/sessions/{session_id}/cancel", response_model=HarnessCancelResponse)
async def cancel_harness_session(
    session_id: uuid.UUID, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)
):
    return await harness_service.cancel_session(db, session_id, user)


@router.post("/sessions/{session_id}/rerun", status_code=201, response_model=HarnessRerunResponse)
async def rerun_harness_session(
    session_id: uuid.UUID, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)
):
    return await harness_service.rerun_session(db, session_id, user)


@router.get("/sessions/{session_id}/workspace", response_model=list[WorkspaceFileResponse])
async def list_workspace_files(
    session_id: uuid.UUID, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)
):
    return await harness_service.list_workspace_files(db, session_id, user)


@router.get("/sessions/{session_id}/workspace/{file_path:path}", response_model=WorkspaceFileContentResponse)
async def read_workspace_file(
    session_id: uuid.UUID, file_path: str, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)
):
    return await harness_service.read_workspace_file(db, session_id, user, file_path)
