"""Unit tests for the pydantic-ai agent runner (no network)."""
import pytest
from pydantic import BaseModel
from pydantic_ai import UnexpectedModelBehavior
from pydantic_ai.messages import ModelResponse, ToolCallPart
from pydantic_ai.models.function import AgentInfo, FunctionModel
from pydantic_ai.models.test import TestModel

from app.harness import agent_runner
from app.harness.agent_runner import build_model, run_structured


class _Item(BaseModel):
    item_index: int
    label: str
    confidence: float


class TestBuildModel:
    def test_unknown_provider_raises(self, monkeypatch):
        monkeypatch.setattr(agent_runner.settings, "llm_provider", "bogus")
        with pytest.raises(ValueError, match="bogus"):
            build_model()

    @pytest.mark.parametrize(
        "provider,host",
        [
            ("anthropic", "api.anthropic.com"),
            ("openai", "api.openai.com"),
            ("openrouter", "openrouter.ai"),
            ("deepseek", "api.deepseek.com"),
        ],
    )
    def test_provider_routes_to_expected_base_url(self, monkeypatch, provider, host):
        monkeypatch.setattr(agent_runner.settings, "llm_provider", provider)
        monkeypatch.setattr(agent_runner.settings, "llm_model", "some-model")
        for key in ("anthropic_api_key", "openai_api_key", "open_router_api_key", "deepseek_api_key"):
            monkeypatch.setattr(agent_runner.settings, key, "test-key")

        model = build_model()

        assert host in str(model.client.base_url)
        assert model.model_name == "some-model"

    def test_explicit_model_name_overrides_settings(self, monkeypatch):
        monkeypatch.setattr(agent_runner.settings, "llm_provider", "openai")
        monkeypatch.setattr(agent_runner.settings, "llm_model", "default-model")
        monkeypatch.setattr(agent_runner.settings, "openai_api_key", "test-key")

        model = build_model(model_name="override-model")

        assert model.model_name == "override-model"


@pytest.mark.asyncio
async def test_run_structured_returns_typed_output_and_usage():
    result = await run_structured(
        output_type=list[_Item],
        system_prompt="system",
        user_prompt="user",
        model=TestModel(custom_output_args=[{"item_index": 0, "label": "x", "confidence": 0.9}]),
    )

    assert isinstance(result.output, list)
    assert isinstance(result.output[0], _Item)
    assert result.output[0].label == "x"
    # Serialized JSON is a bare array in field order — the workspace-file contract.
    assert result.output_json == '[{"item_index":0,"label":"x","confidence":0.9}]'
    assert result.input_tokens > 0
    assert result.output_tokens > 0


@pytest.mark.asyncio
async def test_run_structured_raises_on_schema_violation():
    """A schema-violating model response must raise, never silently pass through."""

    def bad_response(messages, info: AgentInfo) -> ModelResponse:
        name = info.output_tools[0].name
        return ModelResponse(
            parts=[ToolCallPart(tool_name=name, args={"response": [{"item_index": "not-an-int", "label": 5}]})]
        )

    with pytest.raises(UnexpectedModelBehavior):
        await run_structured(
            output_type=list[_Item],
            system_prompt="system",
            user_prompt="user",
            model=FunctionModel(bad_response),
        )
