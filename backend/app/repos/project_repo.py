import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.project import Project
from app.models.wbs_code import WBSCode


def _eager_options():
    return [
        selectinload(Project.retention_tiers),
        selectinload(Project.wbs_codes).selectinload(WBSCode.children),
    ]


async def create(db: AsyncSession, **kwargs) -> Project:
    project = Project(**kwargs)
    db.add(project)
    await db.flush()
    return project


async def get_all(db: AsyncSession) -> list[Project]:
    result = await db.execute(
        select(Project).options(*_eager_options()).order_by(Project.created_at.desc())
    )
    return list(result.scalars().all())


async def get_by_id(db: AsyncSession, project_id: uuid.UUID) -> Project | None:
    result = await db.execute(
        select(Project).options(*_eager_options()).where(Project.id == project_id)
    )
    return result.scalar_one_or_none()


async def get_by_id_with_retention(db: AsyncSession, project_id: uuid.UUID) -> Project | None:
    result = await db.execute(
        select(Project)
        .options(selectinload(Project.retention_tiers))
        .where(Project.id == project_id)
    )
    return result.scalar_one_or_none()
