import uuid
from decimal import Decimal

from sqlalchemy import func as sa_func
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.harness.models import HarnessType
from app.models.claim_parse_flag import ClaimParseFlag, FlagSeverity, FlagType
from app.models.harness_session import HarnessSession, HarnessSessionStatus
from app.models.harness_workspace_file import HarnessWorkspaceFile


async def create_session(
    db: AsyncSession,
    user_id: uuid.UUID,
    project_id: uuid.UUID,
    harness_type: HarnessType,
    document_id: uuid.UUID,
    config: dict | None = None,
) -> HarnessSession:
    session = HarnessSession(
        user_id=user_id,
        project_id=project_id,
        harness_type=harness_type,
        config=config or {},
        document_id=document_id,
    )
    db.add(session)
    await db.flush()
    return session


async def get_session(db: AsyncSession, session_id: uuid.UUID) -> HarnessSession | None:
    result = await db.execute(select(HarnessSession).where(HarnessSession.id == session_id))
    return result.scalar_one_or_none()


async def get_session_by_claim(db: AsyncSession, claim_id: uuid.UUID) -> HarnessSession | None:
    """Find the harness session that produced a given claim."""
    result = await db.execute(
        select(HarnessSession)
        .where(HarnessSession.claim_id == claim_id)
        .order_by(HarnessSession.created_at.desc())
    )
    return result.scalars().first()


async def try_claim_running(db: AsyncSession, session_id: uuid.UUID) -> bool:
    """Atomically set status to running if currently pending. Returns True if claimed."""
    result = await db.execute(
        update(HarnessSession)
        .where(
            HarnessSession.id == session_id,
            HarnessSession.status == HarnessSessionStatus.pending,
        )
        .values(status=HarnessSessionStatus.running)
        .returning(HarnessSession.id)
    )
    row = result.first()
    await db.flush()
    return row is not None


async def set_status(
    db: AsyncSession,
    session_id: uuid.UUID,
    status: HarnessSessionStatus,
    error_message: str | None = None,
) -> None:
    values: dict = {"status": status}
    if error_message is not None:
        values["error_message"] = error_message
    await db.execute(update(HarnessSession).where(HarnessSession.id == session_id).values(**values))
    await db.flush()


async def update_phase(
    db: AsyncSession,
    session_id: uuid.UUID,
    phase_key: str,
    result: dict,
    next_phase: int,
) -> None:
    """Update phase result and advance current_phase."""
    session = await get_session(db, session_id)
    if session is None:
        return
    phase_results = dict(session.phase_results)
    phase_results[phase_key] = result
    await db.execute(
        update(HarnessSession)
        .where(HarnessSession.id == session_id)
        .values(phase_results=phase_results, current_phase=next_phase)
    )
    await db.flush()


async def set_claim_id(db: AsyncSession, session_id: uuid.UUID, claim_id: uuid.UUID) -> None:
    await db.execute(
        update(HarnessSession).where(HarnessSession.id == session_id).values(claim_id=claim_id)
    )
    await db.flush()


# -- Workspace files --


async def write_workspace_file(
    db: AsyncSession,
    session_id: uuid.UUID,
    file_path: str,
    content: str,
    internal: bool = False,
) -> None:
    """Upsert a workspace file."""
    stmt = pg_insert(HarnessWorkspaceFile).values(
        session_id=session_id,
        file_path=file_path,
        content=content,
        internal=internal,
    )
    stmt = stmt.on_conflict_do_update(
        constraint="uq_workspace_session_filepath",
        set_={"content": content, "internal": internal},
    )
    await db.execute(stmt)
    await db.flush()


async def read_workspace_file(
    db: AsyncSession,
    session_id: uuid.UUID,
    file_path: str,
) -> str | None:
    result = await db.execute(
        select(HarnessWorkspaceFile.content).where(
            HarnessWorkspaceFile.session_id == session_id,
            HarnessWorkspaceFile.file_path == file_path,
        )
    )
    row = result.first()
    return row[0] if row else None


async def list_workspace_files(
    db: AsyncSession,
    session_id: uuid.UUID,
    include_internal: bool = False,
) -> list[HarnessWorkspaceFile]:
    stmt = select(HarnessWorkspaceFile).where(HarnessWorkspaceFile.session_id == session_id)
    if not include_internal:
        stmt = stmt.where(HarnessWorkspaceFile.internal == False)  # noqa: E712
    result = await db.execute(stmt)
    return list(result.scalars().all())


# -- Flags --


async def create_flag(
    db: AsyncSession,
    session_id: uuid.UUID,
    flag_type: FlagType,
    severity: FlagSeverity,
    description: str,
    line_item_ref: str | None = None,
    expected_value: Decimal | None = None,
    actual_value: Decimal | None = None,
    claim_id: uuid.UUID | None = None,
) -> ClaimParseFlag:
    flag = ClaimParseFlag(
        session_id=session_id,
        claim_id=claim_id,
        flag_type=flag_type,
        severity=severity,
        line_item_ref=line_item_ref,
        description=description,
        expected_value=expected_value,
        actual_value=actual_value,
    )
    db.add(flag)
    await db.flush()
    return flag


async def list_flags_by_session(
    db: AsyncSession,
    session_id: uuid.UUID,
) -> list[ClaimParseFlag]:
    result = await db.execute(
        select(ClaimParseFlag)
        .where(ClaimParseFlag.session_id == session_id)
        .order_by(ClaimParseFlag.created_at)
    )
    return list(result.scalars().all())


async def list_flags_by_claim(
    db: AsyncSession,
    claim_id: uuid.UUID,
) -> list[ClaimParseFlag]:
    result = await db.execute(
        select(ClaimParseFlag)
        .where(ClaimParseFlag.claim_id == claim_id)
        .order_by(ClaimParseFlag.created_at)
    )
    return list(result.scalars().all())


async def resolve_flag(
    db: AsyncSession,
    flag_id: uuid.UUID,
    user_id: uuid.UUID,
) -> ClaimParseFlag | None:
    result = await db.execute(select(ClaimParseFlag).where(ClaimParseFlag.id == flag_id))
    flag = result.scalar_one_or_none()
    if flag is None:
        return None
    flag.resolved = True
    flag.resolved_by = user_id
    flag.resolved_at = sa_func.now()
    await db.flush()
    return flag


async def delete_sessions_by_claim(db: AsyncSession, claim_id: uuid.UUID) -> None:
    """Delete all harness sessions linked to a claim (cascades to workspace_files & flags)."""
    result = await db.execute(select(HarnessSession).where(HarnessSession.claim_id == claim_id))
    for session in result.scalars().all():
        await db.delete(session)
    await db.flush()


async def delete_sessions_by_project(db: AsyncSession, project_id: uuid.UUID) -> None:
    """Delete all harness sessions for a project (cascades to workspace_files & flags)."""
    result = await db.execute(select(HarnessSession).where(HarnessSession.project_id == project_id))
    for session in result.scalars().all():
        await db.delete(session)
    await db.flush()


async def link_flags_to_claim(
    db: AsyncSession,
    session_id: uuid.UUID,
    claim_id: uuid.UUID,
) -> None:
    """Set claim_id on all flags for a session (called in Phase 5)."""
    await db.execute(
        update(ClaimParseFlag)
        .where(ClaimParseFlag.session_id == session_id)
        .values(claim_id=claim_id)
    )
    await db.flush()
