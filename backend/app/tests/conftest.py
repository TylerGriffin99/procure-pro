import asyncio
from collections.abc import AsyncGenerator
from decimal import Decimal

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import Base, get_db
from app.main import app
from app.models.user import User
from app.models.project import Project
from app.models.wbs_code import WBSCode, WBSLevel
from app.models.document import Document  # noqa: F401
from app.models.harness_session import HarnessSession  # noqa: F401
from app.models.harness_workspace_file import HarnessWorkspaceFile  # noqa: F401
from app.models.claim_parse_flag import ClaimParseFlag  # noqa: F401
from app.repos import document_repo
from app.utils.auth import create_access_token

TEST_DB_URL = "postgresql+asyncpg://claimreview:claimreview_dev@localhost:6000/claimreview_test"


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    engine_test = create_async_engine(TEST_DB_URL, echo=False)
    async_session_test = async_sessionmaker(engine_test, class_=AsyncSession, expire_on_commit=False)

    async with engine_test.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    async with async_session_test() as session:
        yield session

    await engine_test.dispose()


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


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
        db_session, project.id, "test.pdf", "application/pdf", b"%PDF-1.4 test\n%%EOF",
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
        project_id=project.id,
        code="EX",
        description="Excavation",
        level=WBSLevel.category,
        created_by=test_user.id,
    )
    db_session.add(wbs_parent)
    await db_session.flush()
    return project


@pytest_asyncio.fixture
async def auth_headers(test_user: User) -> dict[str, str]:
    token = create_access_token(data={"sub": str(test_user.id)})
    return {"Authorization": f"Bearer {token}"}
