import uuid
from decimal import Decimal

import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.claim_parse_flag import ClaimParseFlag
from app.models.document import Document
from app.models.harness_session import HarnessSession  # noqa: F401
from app.models.harness_workspace_file import HarnessWorkspaceFile  # noqa: F401
from app.models.project import Project
from app.models.user import User
from app.models.wbs_code import WBSCode, WBSLevel
from app.repos import document_repo
from app.utils.auth import create_access_token


async def list_flags_by_session(db: AsyncSession, session_id: uuid.UUID) -> list[ClaimParseFlag]:
    result = await db.execute(
        select(ClaimParseFlag).where(ClaimParseFlag.session_id == session_id).order_by(ClaimParseFlag.created_at)
    )
    return list(result.scalars().all())


@pytest_asyncio.fixture
async def test_user(db_session: AsyncSession) -> User:
    import uuid as _uuid

    user_id = _uuid.uuid4()
    user = User(
        id=user_id,
        email="test@example.com",
        hashed_password="hashed",
        first_name="Test",
        last_name="User",
        created_by=user_id,
    )
    db_session.add(user)
    await db_session.flush()
    return user


@pytest_asyncio.fixture
async def test_project(db_session: AsyncSession, test_user: User) -> Project:
    project = Project(
        name="Test Project",
        client_name="Test Client",
        contractor_name="Test Contractor",
        contract_sum=Decimal("1000000.00"),
        gst_rate=Decimal("0.15"),
        created_by=test_user.id,
    )
    db_session.add(project)
    await db_session.flush()
    return project


async def create_test_document(db_session: AsyncSession, project: Project) -> Document:
    """Helper: persist a minimal Document for a project (satisfies the session FK)."""
    return await document_repo.create_document(
        db_session, project.id, "test.pdf", "application/pdf", b"%PDF-1.4 test\n%%EOF"
    )


@pytest_asyncio.fixture
async def test_document(db_session: AsyncSession, test_project: Project) -> Document:
    return await create_test_document(db_session, test_project)


@pytest_asyncio.fixture
async def test_project_with_wbs(db_session: AsyncSession, test_user: User) -> Project:
    project = Project(
        name="Test Project WBS",
        client_name="Test Client",
        contractor_name="Test Contractor",
        contract_sum=Decimal("1000000.00"),
        gst_rate=Decimal("0.15"),
        created_by=test_user.id,
    )
    db_session.add(project)
    await db_session.flush()

    # Add a WBS parent category
    wbs_parent = WBSCode(
        project_id=project.id, code="EX", description="Excavation", level=WBSLevel.category, created_by=test_user.id
    )
    db_session.add(wbs_parent)
    await db_session.flush()
    return project


@pytest_asyncio.fixture
async def auth_headers(test_user: User) -> dict[str, str]:
    token = create_access_token(data={"sub": str(test_user.id)})
    return {"Authorization": f"Bearer {token}"}
