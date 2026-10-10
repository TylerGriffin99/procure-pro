"""Harness SSE streaming + lifecycle endpoints."""

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

import app.harness.definitions  # noqa: F401 — triggers registration
from app.database import async_session, get_db
from app.dependencies import get_current_user
from app.harness.engine import HarnessEngine
from app.harness.models import HarnessErrorEvent, HarnessEvent, HarnessType
from app.harness.registry import harness_registry
from app.models.harness_session import HarnessSessionStatus
from app.models.user import User
from app.repos import harness_repo
from app.schemas.harness import (
    HarnessPhaseInfo,
    HarnessSessionResponse,
    WorkspaceFileContentResponse,
    WorkspaceFileResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/harness", tags=["harness"])


def _sse(event: HarnessEvent) -> str:
    return f"data: {event.model_dump_json()}\n\n"


def _coerce_harness_type(value: str) -> HarnessType | None:
    """Parse a stored harness_type string into the enum, or None if it is not a
    known type (e.g. a legacy/removed value). Lets callers degrade gracefully
    instead of raising ValueError on the boundary conversion."""
    try:
        return HarnessType(value)
    except ValueError:
        return None


def _build_phases(
    harness_type: HarnessType, current_phase: int, phase_results: dict, status: str
) -> list[HarnessPhaseInfo]:
    definition = harness_registry.get(harness_type)
    if not definition:
        return []
    phases = []
    for i, phase_def in enumerate(definition.phases):
        if status == "completed":
            phase_status = "completed"
        elif status == "failed" and i == current_phase:
            phase_status = "failed"
        elif str(i) in phase_results:
            phase_status = "completed"
        elif i == current_phase and status == "running":
            phase_status = "running"
        else:
            phase_status = "pending"
        phases.append(
            HarnessPhaseInfo(
                index=i,
                name=phase_def.name,
                phase_type=phase_def.phase_type.value,
                status=phase_status,
                result_summary=phase_results.get(str(i), {}).get("summary"),
            )
        )
    return phases


@router.get("/sessions/{session_id}")
async def get_harness_session(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> HarnessSessionResponse:
    session = await harness_repo.get_session(db, session_id)
    if not session or session.user_id != user.id:
        raise HTTPException(status_code=404, detail="Session not found")
    ht = _coerce_harness_type(session.harness_type)
    phases = (
        _build_phases(ht, session.current_phase, session.phase_results, session.status.value)
        if ht
        else []
    )
    return HarnessSessionResponse(
        id=session.id,
        user_id=session.user_id,
        project_id=session.project_id,
        harness_type=session.harness_type,
        status=session.status.value,
        current_phase=session.current_phase,
        phases=phases,
        claim_id=session.claim_id,
        error_message=session.error_message,
        created_at=session.created_at,
    )


@router.get("/sessions/{session_id}/stream")
async def stream_harness_session(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> StreamingResponse:
    session = await harness_repo.get_session(db, session_id)
    if not session or session.user_id != user.id:
        raise HTTPException(status_code=404, detail="Session not found")

    if session.status in (HarnessSessionStatus.completed, HarnessSessionStatus.failed):
        raise HTTPException(status_code=400, detail=f"Session already {session.status.value}")

    ht = _coerce_harness_type(session.harness_type)
    definition = harness_registry.get(ht) if ht is not None else None
    if not definition:
        raise HTTPException(status_code=400, detail=f"Unknown harness type: {session.harness_type}")

    # Capture values before the request-scoped db session closes
    sess_id = session.id
    sess_user_id = user.id
    sess_project_id = session.project_id

    async def event_stream():
        # Create a dedicated DB session that outlives the HTTP request scope
        async with async_session() as engine_db:
            engine = HarnessEngine(
                definition=definition,
                session_id=sess_id,
                user_id=sess_user_id,
                project_id=sess_project_id,
                db=engine_db,
            )
            try:
                async for event in engine.run():
                    yield _sse(event)
                yield "data: [DONE]\n\n"
            except Exception as e:
                logger.exception("harness_stream.error")
                try:
                    await engine._set_failed(str(e))
                except Exception:
                    # Best-effort status update; the stream error below is the
                    # primary signal, but don't swallow this one silently.
                    logger.exception("harness_stream.set_failed_error")
                yield _sse(HarnessErrorEvent(session_id=session_id, error=str(e)))
                yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/sessions/{session_id}/cancel")
async def cancel_harness_session(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    session = await harness_repo.get_session(db, session_id)
    if not session or session.user_id != user.id:
        raise HTTPException(status_code=404, detail="Session not found")
    await harness_repo.set_status(
        db, session_id, HarnessSessionStatus.failed, error_message="Cancelled by user"
    )
    await db.commit()
    return {"id": str(session_id), "status": "failed"}


@router.post("/sessions/{session_id}/rerun", status_code=201)
async def rerun_harness_session(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Re-run a FAILED harness session over its original Document.

    Creates a new pending session pointing at the same Document. A failed
    session produced no Claim, so nothing is deleted.
    """
    old = await harness_repo.get_session(db, session_id)
    if not old or old.user_id != user.id:
        raise HTTPException(status_code=404, detail="Session not found")
    if old.status != HarnessSessionStatus.failed:
        raise HTTPException(status_code=409, detail="Only failed sessions can be re-run")

    ht = _coerce_harness_type(old.harness_type)
    if ht is None:
        raise HTTPException(status_code=400, detail=f"Unknown harness type: {old.harness_type}")

    new_session = await harness_repo.create_session(
        db=db,
        user_id=user.id,
        project_id=old.project_id,
        harness_type=ht,
        document_id=old.document_id,
        config={"document_id": str(old.document_id)},
    )
    await db.commit()
    return {"harness_session_id": str(new_session.id)}


@router.get("/sessions/{session_id}/workspace")
async def list_workspace_files(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[WorkspaceFileResponse]:
    session = await harness_repo.get_session(db, session_id)
    if not session or session.user_id != user.id:
        raise HTTPException(status_code=404, detail="Session not found")
    files = await harness_repo.list_workspace_files(db, session_id)
    return [
        WorkspaceFileResponse(
            file_path=f.file_path, created_at=f.created_at, updated_at=f.updated_at
        )
        for f in files
    ]


@router.get("/sessions/{session_id}/workspace/{file_path:path}")
async def read_workspace_file(
    session_id: uuid.UUID,
    file_path: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> WorkspaceFileContentResponse:
    session = await harness_repo.get_session(db, session_id)
    if not session or session.user_id != user.id:
        raise HTTPException(status_code=404, detail="Session not found")
    content = await harness_repo.read_workspace_file(db, session_id, file_path)
    if content is None:
        raise HTTPException(status_code=404, detail=f"File not found: {file_path}")
    return WorkspaceFileContentResponse(file_path=file_path, content=content)
