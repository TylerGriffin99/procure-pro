import pytest
from pydantic_ai.models.test import TestModel

from app.clients.llm_client import LlmClient
from app.config import settings
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
async def test_llm_matcher_returns_match_outcome():
    model = TestModel(custom_output_args=[{"item_index": 0, "wbs_code": "DM-01", "confidence": 0.9}])
    llm = LlmClient(provider=settings.llm_provider, model_name="m", api_key="k", model=model)

    out = await LlmMatcher(llm=llm).match(phase_def=_Phase(), db=None, project_id="p", session_id="s")

    assert out.output == [WbsMatch(item_index=0, wbs_code="DM-01", confidence=0.9)]
    assert out.input_tokens > 0
    assert out.output_tokens > 0
    assert out.output_json.startswith("[")
