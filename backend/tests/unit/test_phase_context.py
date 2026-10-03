import pytest

from app.harness.phase_context import build_phase_context, render_system_prompt


class _FakePhase:
    workspace_inputs = ["parsed_claim.json"]
    context_loaders = []
    system_prompt_template = "Items: $workspace_parsed_claim / $extra"


@pytest.mark.asyncio
async def test_build_phase_context_reads_workspace(monkeypatch):
    async def fake_read(db, sid, path):
        return '{"line_items": []}'

    monkeypatch.setattr("app.harness.phase_context.harness_repo.read_workspace_file", fake_read)
    phase = _FakePhase()

    async def loader(db, project_id, session_id):
        return {"extra": "X"}

    phase.context_loaders = [loader]

    ctx = await build_phase_context(db=None, session_id="s", project_id="p", phase_def=phase)
    assert ctx["workspace_parsed_claim"] == '{"line_items": []}'
    assert ctx["extra"] == "X"
    assert render_system_prompt(phase, ctx) == 'Items: {"line_items": []} / X'
