from app.harness.definitions.claim_parse import claim_parse_definition
from app.schemas.harness import HarnessPhaseInfo


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
        claim_parse_definition,
        current_phase=1,
        phase_results={"0": {"summary": "ok"}},
        status="failed",
    )
    assert infos[0].result_summary == "ok" and infos[1].result_summary is None
