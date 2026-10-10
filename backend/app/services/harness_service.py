"""Harness session lifecycle: ownership checks, SSE streaming, cancel, re-run, workspace."""

from __future__ import annotations

import logging
import uuid
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

import app.harness.definitions  # noqa: F401 — triggers registration
from app.database import async_session
from app.exceptions import BadRequestError, ConflictError, NotFoundError
from app.harness.engine import HarnessEngine
from app.harness.models import HarnessDefinition, HarnessErrorEvent, HarnessEvent, HarnessType
from app.harness.registry import harness_registry
from app.models.harness_session import HarnessSession, HarnessSessionStatus
from app.models.user import User
from app.repos import harness_repo
from app.schemas.harness import (
    HarnessCancelResponse,
    HarnessRerunResponse,
    HarnessSessionResponse,
    WorkspaceFileContentResponse,
    WorkspaceFileResponse,
)

logger = logging.getLogger(__name__)


def sse(event: HarnessEvent) -> str:
    return f"data: {event.model_dump_json()}\n\n"


def coerce_harness_type(value: str) -> HarnessType | None:
    """Parse a stored harness_type string, or None for a legacy/removed value."""
    try:
        return HarnessType(value)
    except ValueError:
        return None


async def get_owned_session(
    db: AsyncSession, session_id: uuid.UUID, user_id: uuid.UUID
) -> HarnessSession:
    session = await harness_repo.get_session(db, session_id)
    if not session or session.user_id != user_id:
        raise NotFoundError("Session not found")
    return session


async def get_session(
    db: AsyncSession, session_id: uuid.UUID, user: User
) -> HarnessSessionResponse:
    session = await get_owned_session(db, session_id, user.id)
    ht = coerce_harness_type(session.harness_type)
    definition = harness_registry.get(ht) if ht else None
    return HarnessSessionResponse.from_session(session, definition)


async def prepare_stream(
    db: AsyncSession, session_id: uuid.UUID, user: User
) -> tuple[HarnessSession, HarnessDefinition]:
    session = await get_owned_session(db, session_id, user.id)
    if session.status in (HarnessSessionStatus.completed, HarnessSessionStatus.failed):
        raise BadRequestError(f"Session already {session.status.value}")
    ht = coerce_harness_type(session.harness_type)
    definition = harness_registry.get(ht) if ht is not None else None
    if not definition:
        raise BadRequestError(f"Unknown harness type: {session.harness_type}")
    return session, definition


async def stream_events(
    *,
    definition: HarnessDefinition,
    session_id: uuid.UUID,
    user_id: uuid.UUID,
    project_id: uuid.UUID,
) -> AsyncGenerator[str, None]:
    """Run the engine on a DB session that outlives the HTTP request and yield SSE frames."""
    async with async_session() as engine_db:
        engine = HarnessEngine(
            definition=definition,
            session_id=session_id,
            user_id=user_id,
            project_id=project_id,
            db=engine_db,
        )
        try:
            async for event in engine.run():
                yield sse(event)
            yield "data: [DONE]\n\n"
        except Exception as e:
            logger.exception("harness_stream.error")
            try:
                await engine.set_failed(str(e))
            except Exception:
                # Best-effort status update; the stream error below is the primary signal.
                logger.exception("harness_stream.set_failed_error")
            yield sse(HarnessErrorEvent(session_id=session_id, error=str(e)))
            yield "data: [DONE]\n\n"


async def cancel_session(
    db: AsyncSession, session_id: uuid.UUID, user: User
) -> HarnessCancelResponse:
    await get_owned_session(db, session_id, user.id)
    await harness_repo.set_status(
        db, session_id, HarnessSessionStatus.failed, error_message="Cancelled by user"
    )
    await db.commit()
    return HarnessCancelResponse(id=session_id, status="failed")


async def rerun_session(
    db: AsyncSession, session_id: uuid.UUID, user: User
) -> HarnessRerunResponse:
    """Re-run a FAILED session over its original Document as a new pending session."""
    old = await get_owned_session(db, session_id, user.id)
    if old.status != HarnessSessionStatus.failed:
        raise ConflictError("Only failed sessions can be re-run")
    ht = coerce_harness_type(old.harness_type)
    if ht is None:
        raise BadRequestError(f"Unknown harness type: {old.harness_type}")
    new_session = await harness_repo.create_session(
        db=db,
        user_id=user.id,
        project_id=old.project_id,
        harness_type=ht,
        document_id=old.document_id,
        config={"document_id": str(old.document_id)},
    )
    await db.commit()
    return HarnessRerunResponse(harness_session_id=new_session.id)


async def list_workspace_files(
    db: AsyncSession, session_id: uuid.UUID, user: User
) -> list[WorkspaceFileResponse]:
    await get_owned_session(db, session_id, user.id)
    files = await harness_repo.list_workspace_files(db, session_id)
    return [
        WorkspaceFileResponse(
            file_path=f.file_path, created_at=f.created_at, updated_at=f.updated_at
        )
        for f in files
    ]


async def read_workspace_file(
    db: AsyncSession, session_id: uuid.UUID, user: User, file_path: str
) -> WorkspaceFileContentResponse:
    await get_owned_session(db, session_id, user.id)
    content = await harness_repo.read_workspace_file(db, session_id, file_path)
    if content is None:
        raise NotFoundError(f"File not found: {file_path}")
    return WorkspaceFileContentResponse(file_path=file_path, content=content)
