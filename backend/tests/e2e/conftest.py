"""E2E test fixtures — spins up an isolated PostgreSQL container via testcontainers.

Set E2E_DATABASE_URL to skip the container and use an existing database instead.
This lets data persist after the test so you can inspect it in the UI.

Example:
    E2E_DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/claimreview \
        python -m pytest tests/e2e/test_e2e_full_pipeline.py -v -x -s
"""
import asyncio
import os
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from testcontainers.postgres import PostgresContainer

import app.database as database_module
import app.services.harness_service as harness_module
from app.database import Base, get_db
from app.main import app
from app.models.harness_session import HarnessSession  # noqa: F401
from app.models.harness_workspace_file import HarnessWorkspaceFile  # noqa: F401
from app.models.claim_parse_flag import ClaimParseFlag  # noqa: F401

_EXTERNAL_DB_URL = os.environ.get("E2E_DATABASE_URL")


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def postgres_container():
    """Spin up an isolated PostgreSQL container for the entire test session.

    Skipped when E2E_DATABASE_URL is set (external DB mode).
    """
    if _EXTERNAL_DB_URL:
        yield None
        return
    with PostgresContainer(
        image="postgres:16-alpine",
        username="test",
        password="test",
        dbname="claimreview_test",
    ) as pg:
        yield pg


@pytest.fixture(scope="session")
def test_db_url(postgres_container) -> str:
    """Build asyncpg connection URL from the running container or env var."""
    if _EXTERNAL_DB_URL:
        return _EXTERNAL_DB_URL
    host = postgres_container.get_container_host_ip()
    port = postgres_container.get_exposed_port(5432)
    return f"postgresql+asyncpg://test:test@{host}:{port}/claimreview_test"


@pytest_asyncio.fixture
async def db_session(test_db_url: str) -> AsyncGenerator[AsyncSession, None]:
    engine_test = create_async_engine(test_db_url, echo=False)
    async_session_test = async_sessionmaker(engine_test, class_=AsyncSession, expire_on_commit=False)

    async with engine_test.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    # Patch async_session in both database module AND harness service
    # (the service imports async_session at module load time)
    orig_db = database_module.async_session
    orig_harness = harness_module.async_session
    database_module.async_session = async_session_test
    harness_module.async_session = async_session_test

    async with async_session_test() as session:
        yield session

    database_module.async_session = orig_db
    harness_module.async_session = orig_harness
    await engine_test.dispose()


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()
