"""Characterisation: pins today's SSE error frames from harness_service.stream_events."""

import json

from app.harness.models import HarnessDefinition, HarnessType, PhaseDefinition, PhaseType
from app.harness.phase_context import build_phase_context, render_system_prompt
from app.models.harness_session import HarnessSessionStatus
from app.repos import document_repo, harness_repo
from app.services import harness_service
from tests.integration.characterisation_fixtures import seed_project, seed_user


async def _boom(db, session_id, user_id, project_id, config):
    raise RuntimeError("boom")


def _failing_definition() -> HarnessDefinition:
    return HarnessDefinition(
        harness_type=HarnessType.CLAIM_PARSE,
        display_name="Failing",
        description="First phase raises",
        prerequisites=None,
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


async def test_stream_events_today_emits_error_frames_then_done(db_session):
    user_id, project_id, session_id = await _pending_session(db_session)

    frames = [
        frame
        async for frame in harness_service.stream_events(
            definition=_failing_definition(), session_id=session_id, user_id=user_id, project_id=project_id
        )
    ]

    text = "".join(frames)
    assert "RuntimeError: boom" in text
    assert text.endswith("data: [DONE]\n\n")
    events = [json.loads(f.removeprefix("data: ")) for f in frames[:-1]]
    assert [e["type"] for e in events] == [
        "harness_start",
        "harness_phase_start",
        "harness_phase_error",
        "harness_error",
    ]
    assert events[2]["error"] == "RuntimeError: boom"
    assert events[3]["error"] == "RuntimeError: boom"

    db_session.expire_all()
    stored = await harness_repo.get_session(db_session, session_id)
    assert stored is not None
    assert stored.status == HarnessSessionStatus.failed
    assert stored.error_message == "Phase 'broken' failed: RuntimeError: boom"


async def _claim_raises(db, session_id):
    raise RuntimeError("boom")


async def test_stream_events_today_wraps_engine_level_error(db_session, monkeypatch):
    user_id, project_id, session_id = await _pending_session(db_session)
    monkeypatch.setattr("app.harness.engine.harness_repo.try_claim_running", _claim_raises)

    frames = [
        frame
        async for frame in harness_service.stream_events(
            definition=_failing_definition(), session_id=session_id, user_id=user_id, project_id=project_id
        )
    ]

    assert frames[-1] == "data: [DONE]\n\n"
    [event] = [json.loads(f.removeprefix("data: ")) for f in frames[:-1]]
    assert event == {"type": "harness_error", "session_id": str(session_id), "error": "RuntimeError: boom"}

    db_session.expire_all()
    stored = await harness_repo.get_session(db_session, session_id)
    assert stored is not None
    assert stored.status == HarnessSessionStatus.failed
    assert stored.error_message == "RuntimeError: boom"


# --- phase context fallback against the real repo (D7 flips to pytest.raises) ---


def _phase_reading(path: str) -> PhaseDefinition:
    return PhaseDefinition(
        name="match",
        description="Reads a workspace input",
        phase_type=PhaseType.LLM_SINGLE,
        workspace_output="out.json",
        system_prompt_template="Items: $workspace_parsed_claim",
        workspace_inputs=[path],
    )


async def test_phase_context_today_substitutes_file_not_found_for_missing_file(db_session):
    _, project_id, session_id = await _pending_session(db_session)
    phase = _phase_reading("parsed_claim.json")

    assert await harness_repo.read_workspace_file(db_session, session_id, "parsed_claim.json") is None
    ctx = await build_phase_context(db=db_session, session_id=session_id, project_id=project_id, phase_def=phase)

    assert ctx["workspace_parsed_claim"] == "FILE NOT FOUND"
    assert render_system_prompt(phase, ctx) == "Items: FILE NOT FOUND"


async def test_phase_context_today_substitutes_file_not_found_for_empty_file(db_session):
    _, project_id, session_id = await _pending_session(db_session)
    await harness_repo.write_workspace_file(db_session, session_id, "parsed_claim.json", "")
    await db_session.commit()
    phase = _phase_reading("parsed_claim.json")

    assert await harness_repo.read_workspace_file(db_session, session_id, "parsed_claim.json") == ""
    ctx = await build_phase_context(db=db_session, session_id=session_id, project_id=project_id, phase_def=phase)

    assert render_system_prompt(phase, ctx) == "Items: FILE NOT FOUND"
