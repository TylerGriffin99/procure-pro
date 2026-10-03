import pytest

from app.harness.matchers.llm import LlmMatcher
from app.harness.schemas import WbsMatch


class _Phase:
    name = "WBS Categorisation"
    workspace_inputs = []
    context_loaders = []
    system_prompt_template = "match"
    model = None
    output_schema = list[WbsMatch]


@pytest.mark.asyncio
async def test_llm_matcher_returns_match_outcome(monkeypatch):
    sample = [WbsMatch(item_index=0, wbs_code="DM-01", confidence=0.9)]

    async def fake_run_structured(*, output_type, system_prompt, user_prompt, model=None, phase_name=None):
        from pydantic import TypeAdapter

        from app.harness.agent_runner import StructuredResult

        return StructuredResult(
            output=sample,
            output_json=TypeAdapter(output_type).dump_json(sample).decode(),
            input_tokens=10,
            output_tokens=5,
        )

    monkeypatch.setattr("app.harness.matchers.llm.run_structured", fake_run_structured)

    out = await LlmMatcher().match(phase_def=_Phase(), db=None, project_id="p", session_id="s")
    assert out.output == sample
    assert out.input_tokens == 10
    assert out.output_tokens == 5
    assert out.output_json.startswith("[")
