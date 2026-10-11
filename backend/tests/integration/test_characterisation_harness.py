"""Characterisation: pins today's SSE error frames from harness_service.stream_events."""

import asyncio
import json

import pytest

from app.config import settings
from app.database import get_session_factory
from app.dependencies import get_llm_client, get_matchers
from app.exceptions import BadRequestError
from app.harness.factory import engine_builder
from app.harness.models import HarnessDefinition, HarnessType, PhaseDefinition, PhaseType
from app.harness.phase_context import build_phase_context
from app.models.harness_session import HarnessSessionStatus
from app.repos import document_repo, harness_repo
from app.services import harness_service
from tests.integration.characterisation_fixtures import seed_project, seed_user


@pytest.fixture
def stream_deps():
    build = engine_builder(settings=settings, llm=get_llm_client(), matchers=get_matchers())
    return {"build": build, "sessions": get_session_factory()}


async def _boom(**_):
    raise RuntimeError("boom")


def _failing_definition() -> HarnessDefinition:
    return HarnessDefinition(
        harness_type=HarnessType.CLAIM_PARSE,
        display_name="Failing",
        description="First phase raises",
        phases=[
            PhaseDefinition(
                name="broken",
                description="Raises RuntimeError",
                phase_type=PhaseType.PROGRAMMATIC,
                workspace_output="never.json",
                executor=_boom,
            )
        ],
    )


async def _pending_session(db):
    user = await seed_user(db)
    project = await seed_project(db, user)
    doc = await document_repo.create_document(db, project.id, "c.pdf", "application/pdf", b"%PDF-1.4 x")
    session = await harness_repo.create_session(
        db=db, user_id=user.id, project_id=project.id, harness_type=HarnessType.CLAIM_PARSE, document_id=doc.id
    )
    await db.commit()
    return user.id, project.id, session.id


async def test_stream_events_emits_classified_error_frames_then_done(db_session, stream_deps, caplog):
    user_id, project_id, session_id = await _pending_session(db_session)

    frames = [
        frame
        async for frame in harness_service.stream_events(
            definition=_failing_definition(),
            session_id=session_id,
            user_id=user_id,
            project_id=project_id,
            **stream_deps,
        )
    ]

    text = "".join(frames)
    assert "boom" not in text
    assert text.endswith("data: [DONE]\n\n")
    events = [json.loads(f.removeprefix("data: ")) for f in frames[:-1]]
    assert [e["type"] for e in events] == [
        "harness_start",
        "harness_phase_start",
        "harness_phase_error",
        "harness_error",
    ]
    assert events[2]["error"] == "RuntimeError"
    assert events[3]["error"] == "RuntimeError"
    assert any(r.exc_info and "boom" in str(r.exc_info[1]) for r in caplog.records)

    db_session.expire_all()
    stored = await harness_repo.get_session(db_session, session_id)
    assert stored is not None
    assert stored.status == HarnessSessionStatus.failed
    assert stored.error_message == "Phase 'broken' failed: RuntimeError"


async def _claim_raises(db, session_id):
    raise RuntimeError("boom")


async def test_stream_events_wraps_engine_level_error(db_session, stream_deps, monkeypatch):
    user_id, project_id, session_id = await _pending_session(db_session)
    monkeypatch.setattr("app.harness.engine.harness_repo.try_claim_running", _claim_raises)

    frames = [
        frame
        async for frame in harness_service.stream_events(
            definition=_failing_definition(),
            session_id=session_id,
            user_id=user_id,
            project_id=project_id,
            **stream_deps,
        )
    ]

    assert frames[-1] == "data: [DONE]\n\n"
    [event] = [json.loads(f.removeprefix("data: ")) for f in frames[:-1]]
    assert event == {"type": "harness_error", "session_id": str(session_id), "error": "RuntimeError"}

    db_session.expire_all()
    stored = await harness_repo.get_session(db_session, session_id)
    assert stored is not None
    assert stored.status == HarnessSessionStatus.failed
    assert stored.error_message == "RuntimeError"


# --- a cancelled stream does not leave the session running (hunter M6) ---


def _hanging_definition(started: asyncio.Event) -> HarnessDefinition:
    async def hang(**_):
        started.set()
        await asyncio.Event().wait()

    return HarnessDefinition(
        harness_type=HarnessType.CLAIM_PARSE,
        display_name="Hanging",
        description="First phase never returns",
        phases=[
            PhaseDefinition(
                name="hang",
                description="Waits forever",
                phase_type=PhaseType.PROGRAMMATIC,
                workspace_output="never.json",
                executor=hang,
            )
        ],
    )


async def test_cancelled_stream_marks_session_failed(db_session, stream_deps):
    user_id, project_id, session_id = await _pending_session(db_session)
    started = asyncio.Event()

    async def consume():
        async for _ in harness_service.stream_events(
            definition=_hanging_definition(started),
            session_id=session_id,
            user_id=user_id,
            project_id=project_id,
            **stream_deps,
        ):
            pass

    task = asyncio.create_task(consume())
    await started.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    db_session.expire_all()
    stored = await harness_repo.get_session(db_session, session_id)
    assert stored is not None
    assert stored.status == HarnessSessionStatus.failed
    assert stored.error_message == "Stream cancelled"


# --- phase context: a missing or empty workspace input is fatal (D7 applied) ---


def _phase_reading(path: str) -> PhaseDefinition:
    return PhaseDefinition(
        name="match",
        description="Reads a workspace input",
        phase_type=PhaseType.LLM_SINGLE,
        workspace_output="out.json",
        system_prompt_template="Items: $workspace_parsed_claim",
        workspace_inputs=[path],
    )


async def test_phase_context_missing_file_is_fatal(db_session):
    _, project_id, session_id = await _pending_session(db_session)
    phase = _phase_reading("parsed_claim.json")

    assert await harness_repo.read_workspace_file(db_session, session_id, "parsed_claim.json") is None
    with pytest.raises(BadRequestError, match="Workspace file parsed_claim.json missing for phase match"):
        await build_phase_context(db=db_session, session_id=session_id, project_id=project_id, phase_def=phase)


async def test_phase_context_empty_file_is_fatal(db_session):
    _, project_id, session_id = await _pending_session(db_session)
    await harness_repo.write_workspace_file(db_session, session_id, "parsed_claim.json", "")
    await db_session.commit()
    phase = _phase_reading("parsed_claim.json")

    assert await harness_repo.read_workspace_file(db_session, session_id, "parsed_claim.json") == ""
    with pytest.raises(BadRequestError, match="Workspace file parsed_claim.json missing for phase match"):
        await build_phase_context(db=db_session, session_id=session_id, project_id=project_id, phase_def=phase)


async def test_losing_stream_closed_after_already_running_leaves_session_untouched(db_session, stream_deps):
    user_id, project_id, session_id = await _pending_session(db_session)
    await harness_repo.set_status(db_session, session_id, HarnessSessionStatus.running)
    await db_session.commit()

    stream = harness_service.stream_events(
        definition=_failing_definition(), session_id=session_id, user_id=user_id, project_id=project_id, **stream_deps
    )
    first = json.loads((await anext(stream)).removeprefix("data: "))
    assert first["error"] == "Session already running"
    await stream.aclose()

    db_session.expire_all()
    stored = await harness_repo.get_session(db_session, session_id)
    assert stored is not None
    assert stored.status == HarnessSessionStatus.running
    assert stored.error_message is None
