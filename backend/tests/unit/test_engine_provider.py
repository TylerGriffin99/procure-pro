import functools
import json
import logging
import uuid
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app import dependencies
from app.clients.llm_client import LlmClient
from app.config import get_settings, settings
from app.constants import HarnessSessionStatus, MatcherName
from app.database import get_db, get_session_factory
from app.dependencies import get_current_user, get_engine_builder, get_llm_client, get_matchers
from app.harness.engine import HarnessEngine
from app.harness.models import HarnessCompleteEvent, HarnessStartEvent, HarnessType
from app.main import app
from app.models.harness_session import HarnessSession
from app.models.user import User

USER = User(id=uuid.uuid4())


class FakeDb:
    def __init__(self, session: HarnessSession) -> None:
        self.session = session

    async def execute(self, statement):
        return SimpleNamespace(scalar_one_or_none=lambda: self.session)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return None


class FakeEngine:
    def __init__(self, **kwargs) -> None:
        self.kwargs = kwargs
        self.claimed = False

    async def run(self):
        session_id = self.kwargs["session_id"]
        yield HarnessStartEvent(session_id=session_id, harness_type=HarnessType.CLAIM_PARSE, total_phases=0)
        yield HarnessCompleteEvent(session_id=session_id, claim_id=None)


@pytest.fixture
def fresh_providers():
    get_llm_client.cache_clear()
    get_matchers.cache_clear()
    yield
    get_llm_client.cache_clear()
    get_matchers.cache_clear()


@pytest.fixture
def stream_client():
    session = HarnessSession(
        id=uuid.uuid4(),
        user_id=USER.id,
        project_id=uuid.uuid4(),
        harness_type=HarnessType.CLAIM_PARSE.value,
        status=HarnessSessionStatus.pending,
    )
    db = FakeDb(session)
    built: list[FakeEngine] = []

    def fake_builder(**kwargs) -> FakeEngine:
        built.append(FakeEngine(**kwargs))
        return built[-1]

    async def fake_get_db():
        yield db

    app.dependency_overrides[get_db] = fake_get_db
    app.dependency_overrides[get_current_user] = lambda: USER
    app.dependency_overrides[get_session_factory] = lambda: lambda: db
    app.dependency_overrides[get_engine_builder] = lambda: fake_builder
    yield TestClient(app), session, built, db
    app.dependency_overrides.clear()


def test_stream_endpoint_runs_the_injected_engine_builder(stream_client):
    client, session, built, db = stream_client

    resp = client.get(f"{settings.api_prefix}/harness/sessions/{session.id}/stream")

    assert resp.status_code == 200
    frames = [line.removeprefix("data: ") for line in resp.text.splitlines() if line.startswith("data: ")]
    assert frames[-1] == "[DONE]"
    assert [json.loads(f)["type"] for f in frames[:-1]] == ["harness_start", "harness_complete"]
    (engine,) = built
    assert engine.kwargs["session_id"] == session.id
    assert engine.kwargs["user_id"] == USER.id
    assert engine.kwargs["project_id"] == session.project_id
    assert engine.kwargs["db"] is db


def test_get_settings_is_the_module_settings_instance():
    assert get_settings() is settings


def test_engine_builder_binds_settings_and_the_process_wide_collaborators(fresh_providers):
    build = get_engine_builder(settings, get_llm_client(), get_matchers())

    assert isinstance(build, functools.partial) and build.func is HarnessEngine
    assert build.keywords["default_matcher"] is settings.matcher_default
    assert build.keywords["llm"] is get_llm_client()
    assert build.keywords["matchers"] is get_matchers()
    assert isinstance(get_llm_client(), LlmClient)
    assert set(get_matchers()) == set(MatcherName)


def test_unset_jev_key_warning_logs_once_per_process(fresh_providers, monkeypatch, caplog):
    monkeypatch.setattr(settings, "open_router_api_key", "")
    with caplog.at_level(logging.WARNING, logger="app.harness.factory"):
        for _ in range(3):
            dependencies.get_engine_builder(settings, get_llm_client(), get_matchers())

    warnings = [r for r in caplog.records if "falling back to matcher=llm" in r.getMessage()]
    assert len(warnings) == 1


def test_cors_origins_come_from_settings():
    cors = next(m for m in app.user_middleware if m.cls.__name__ == "CORSMiddleware")
    assert cors.kwargs["allow_origins"] == settings.cors_origins
    assert settings.cors_origins == ["http://localhost:5173"]
