"""Workspace file read/write for harness phases."""
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.repos import harness_repo


async def read_workspace(
    db: AsyncSession,
    session_id: uuid.UUID,
    file_path: str,
) -> str:
    content = await harness_repo.read_workspace_file(db, session_id, file_path)
    if content is None:
        return f"FILE NOT FOUND: {file_path}"
    return content


async def write_workspace(
    db: AsyncSession,
    session_id: uuid.UUID,
    file_path: str,
    content: str,
    internal: bool = False,
) -> None:
    await harness_repo.write_workspace_file(db, session_id, file_path, content, internal)
