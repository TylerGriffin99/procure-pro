"""Harness session lifecycle: ownership checks, SSE streaming, cancel, re-run, workspace."""

from __future__ import annotations

import logging
import uuid
from collections.abc import AsyncGenerator, Awaitable

import anyio
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.constants.enums import HarnessSessionStatus
from app.database import async_session
from app.exceptions import BadRequestError, ConflictError, require
from app.harness.definitions import HARNESS_DEFINITIONS
from app.harness.engine import HarnessEngine, describe_error, mark_session_failed
from app.harness.factory import build_engine
from app.harness.models import HarnessDefinition, HarnessErrorEvent, HarnessEvent, HarnessType
from app.models.harness_session import HarnessSession
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


def require_owned(session: HarnessSession | None, user_id: uuid.UUID) -> HarnessSession:
    # A foreign session is reported as missing (404), not forbidden, so session ids cannot be probed.
    return require(session if session is not None and session.user_id == user_id else None, "Session")


async def get_owned_session(db: AsyncSession, session_id: uuid.UUID, user_id: uuid.UUID) -> HarnessSession:
    return require_owned(await harness_repo.get_session(db, session_id), user_id)


async def get_session(db: AsyncSession, session_id: uuid.UUID, user: User) -> HarnessSessionResponse:
    session = await get_owned_session(db, session_id, user.id)
    ht = coerce_harness_type(session.harness_type)
    definition = HARNESS_DEFINITIONS.get(ht) if ht else None
    return HarnessSessionResponse.from_session(session, definition)


async def prepare_stream(
    db: AsyncSession, session_id: uuid.UUID, user: User
) -> tuple[HarnessSession, HarnessDefinition]:
    session = await get_owned_session(db, session_id, user.id)
    if session.status in (HarnessSessionStatus.completed, HarnessSessionStatus.failed):
        raise BadRequestError(f"Session already {session.status.value}")
    ht = coerce_harness_type(session.harness_type)
    definition = HARNESS_DEFINITIONS.get(ht) if ht is not None else None
    if not definition:
        raise BadRequestError(f"Unknown harness type: {session.harness_type}")
    return session, definition


async def mark_stream_cancelled(db: AsyncSession, session_id: uuid.UUID) -> None:
    await db.rollback()
    await harness_repo.fail_if_running(db, session_id, "Stream cancelled")
    await db.commit()


async def record_stream_failure(step: Awaitable[None], session_id: uuid.UUID) -> None:
    try:
        await step
    except Exception:
        # Best effort (D5): if the status write itself fails the session stays `running`; there is no reaper.
        logger.exception("harness_stream.set_failed_error session=%s", session_id)


async def stream_events(
    *, definition: HarnessDefinition, session_id: uuid.UUID, user_id: uuid.UUID, project_id: uuid.UUID
) -> AsyncGenerator[str, None]:
    """Run the engine on a DB session that outlives the HTTP request and yield SSE frames."""
    async with async_session() as engine_db:
        engine: HarnessEngine | None = None
        try:
            engine = build_engine(
                settings=settings,
                definition=definition,
                session_id=session_id,
                user_id=user_id,
                project_id=project_id,
                db=engine_db,
            )
            async for event in engine.run():
                yield sse(event)
            yield "data: [DONE]\n\n"
        except Exception as e:
            logger.exception("harness_stream.error")
            with anyio.CancelScope(shield=True):
                await record_stream_failure(mark_session_failed(engine_db, session_id, describe_error(e)), session_id)
            yield sse(HarnessErrorEvent(session_id=session_id, error=describe_error(e)))
            yield "data: [DONE]\n\n"
        except BaseException:
            # Client disconnect (CancelledError) or generator close (GeneratorExit): no frame can be sent.
            logger.warning("harness_stream.cancelled session=%s", session_id)
            if engine is not None and engine.claimed:
                with anyio.CancelScope(shield=True):
                    await record_stream_failure(mark_stream_cancelled(engine_db, session_id), session_id)
            raise


async def cancel_session(db: AsyncSession, session_id: uuid.UUID, user: User) -> HarnessCancelResponse:
    await get_owned_session(db, session_id, user.id)
    await harness_repo.set_status(db, session_id, HarnessSessionStatus.failed, error_message="Cancelled by user")
    await db.commit()
    return HarnessCancelResponse(id=session_id, status=HarnessSessionStatus.failed)


async def rerun_session(db: AsyncSession, session_id: uuid.UUID, user: User) -> HarnessRerunResponse:
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


async def list_workspace_files(db: AsyncSession, session_id: uuid.UUID, user: User) -> list[WorkspaceFileResponse]:
    await get_owned_session(db, session_id, user.id)
    files = await harness_repo.list_workspace_files(db, session_id)
    return [
        WorkspaceFileResponse(file_path=f.file_path, created_at=f.created_at, updated_at=f.updated_at) for f in files
    ]


async def read_workspace_file(
    db: AsyncSession, session_id: uuid.UUID, user: User, file_path: str
) -> WorkspaceFileContentResponse:
    await get_owned_session(db, session_id, user.id)
    content = require(await harness_repo.read_workspace_file(db, session_id, file_path), f"File {file_path}")
    return WorkspaceFileContentResponse(file_path=file_path, content=content)
