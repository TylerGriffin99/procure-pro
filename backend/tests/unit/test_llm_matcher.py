import pytest
from pydantic_ai.models.test import TestModel

from app.clients.llm_client import LlmClient
from app.config import settings
from app.constants import MatcherName
from app.harness.matchers.llm import match_with_llm
from app.harness.models import PhaseDefinition, PhaseRun, PhaseType
from app.harness.schemas import WbsMatch

PHASE = PhaseDefinition(
    name="WBS Categorisation",
    description="match",
    phase_type=PhaseType.LLM_BATCH_AGENTS,
    workspace_output="wbs_matches.json",
    system_prompt_template="match",
    output_schema=list[WbsMatch],
)


@pytest.mark.asyncio
async def test_llm_matcher_returns_match_outcome():
    model = TestModel(custom_output_args=[{"item_index": 0, "wbs_code": "DM-01", "confidence": 0.9}])
    llm = LlmClient(provider=settings.llm_provider, model_name="m", api_key="k", model=model)

    out = await match_with_llm(PhaseRun(phase_def=PHASE, db=None, project_id="p", session_id="s"), llm=llm)

    assert out.matcher is MatcherName.llm
    assert out.output == [WbsMatch(item_index=0, wbs_code="DM-01", confidence=0.9)]
    assert out.input_tokens > 0
    assert out.output_tokens > 0
    assert out.output_json.startswith("[")
