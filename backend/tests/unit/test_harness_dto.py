import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from app.constants.enums import HarnessSessionStatus
from app.harness.definitions.claim_parse import claim_parse_definition
from app.schemas.harness import HarnessPhaseInfo, HarnessSessionResponse, WorkspaceFileResponse


def statuses(**kw) -> list[str]:
    return [p.status for p in HarnessPhaseInfo.from_definition(claim_parse_definition, **kw)]


def test_completed_session_marks_every_phase_completed():
    assert set(statuses(current_phase=6, phase_results={}, status="completed")) == {"completed"}


def test_running_session_marks_done_current_and_pending():
    out = statuses(current_phase=2, phase_results={"0": {}, "1": {}}, status="running")
    assert out[:3] == ["completed", "completed", "running"]
    assert set(out[3:]) == {"pending"}


def test_failed_session_marks_current_phase_failed():
    out = statuses(current_phase=1, phase_results={"0": {"summary": "ok"}}, status="failed")
    assert out[0] == "completed" and out[1] == "failed"
    infos = HarnessPhaseInfo.from_definition(
        claim_parse_definition, current_phase=1, phase_results={"0": {"summary": "ok"}}, status="failed"
    )
    assert infos[0].result_summary == "ok" and infos[1].result_summary is None


def fake_session(**overrides) -> SimpleNamespace:
    fields = {
        "id": uuid.uuid4(),
        "user_id": uuid.uuid4(),
        "project_id": uuid.uuid4(),
        "harness_type": "claim_parse",
        "status": HarnessSessionStatus.running,
        "current_phase": 2,
        "phase_results": {"0": {"summary": "ok"}, "1": {}},
        "claim_id": None,
        "error_message": None,
        "created_at": datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC),
    }
    return SimpleNamespace(**(fields | overrides))


def field_by_field(session, definition) -> HarnessSessionResponse:
    phases = (
        HarnessPhaseInfo.from_definition(
            definition, current_phase=session.current_phase, phase_results=session.phase_results, status=session.status
        )
        if definition
        else []
    )
    return HarnessSessionResponse(
        id=session.id,
        user_id=session.user_id,
        project_id=session.project_id,
        harness_type=session.harness_type,
        status=session.status,
        current_phase=session.current_phase,
        phases=phases,
        claim_id=session.claim_id,
        error_message=session.error_message,
        created_at=session.created_at,
    )


@pytest.mark.parametrize("definition", [claim_parse_definition, None])
def test_from_session_equals_the_field_by_field_mapping(definition):
    session = fake_session(claim_id=uuid.uuid4(), error_message="boom")
    dto = HarnessSessionResponse.from_session(session, definition)
    assert dto == field_by_field(session, definition)
    assert dto.model_dump(mode="json") == field_by_field(session, definition).model_dump(mode="json")


def test_workspace_file_response_reads_orm_attributes():
    row = SimpleNamespace(
        file_path="parsed_claim.json",
        created_at=datetime(2026, 1, 2, tzinfo=UTC),
        updated_at=None,
        content="{}",
        session_id=uuid.uuid4(),
    )
    dto = WorkspaceFileResponse.model_validate(row, from_attributes=True)
    assert dto == WorkspaceFileResponse(file_path=row.file_path, created_at=row.created_at, updated_at=row.updated_at)
