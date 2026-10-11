import pytest
from pydantic import BaseModel, ValidationError
from pydantic_ai import UnexpectedModelBehavior
from pydantic_ai.messages import ModelResponse, ToolCallPart
from pydantic_ai.models.function import AgentInfo, FunctionModel
from pydantic_ai.models.test import TestModel

from app.clients.llm_client import LlmClient, StructuredResult
from app.config import Settings
from app.constants import LlmProvider
from app.constants.values import PROVIDER_TABLE

KEYS = {
    "anthropic_api_key": "k-anthropic",
    "openai_api_key": "k-openai",
    "open_router_api_key": "k-openrouter",
    "deepseek_api_key": "k-deepseek",
}


class _Item(BaseModel):
    item_index: int
    label: str
    confidence: float


def _settings(provider: str, model: str = "some-model") -> Settings:
    return Settings(secret_key="k", llm_provider=provider, llm_model=model, **KEYS)


def _test_client(model) -> LlmClient:
    return LlmClient(provider=LlmProvider.openai, model_name="m", api_key="k", model=model)


class TestSettings:
    def test_unknown_provider_is_rejected_at_settings_load(self):
        with pytest.raises(ValidationError, match="llm_provider"):
            Settings(secret_key="k", llm_provider="bogus", llm_model="m", **KEYS)

    def test_provider_is_case_insensitive_at_settings_load(self):
        assert (
            Settings(secret_key="k", llm_provider="OpenRouter", llm_model="m", **KEYS).llm_provider
            is LlmProvider.openrouter
        )


class TestFromSettings:
    @pytest.mark.parametrize("provider", list(LlmProvider))
    def test_selects_base_url_and_key_per_provider_table(self, provider):
        base_url, key_field = PROVIDER_TABLE[provider]

        client = LlmClient.from_settings(_settings(provider.value))

        assert client.provider is provider
        assert client.base_url == base_url
        assert client.api_key == KEYS[key_field]
        assert client.model_name == "some-model"

    @pytest.mark.parametrize(
        "provider,host",
        [
            ("anthropic", "api.anthropic.com"),
            ("openai", "api.openai.com"),
            ("openrouter", "openrouter.ai"),
            ("deepseek", "api.deepseek.com"),
        ],
    )
    def test_built_model_routes_to_expected_host(self, provider, host):
        model = LlmClient.from_settings(_settings(provider)).build_model()

        assert host in str(model.client.base_url)
        assert model.model_name == "some-model"

    def test_explicit_model_name_overrides_default(self):
        model = LlmClient.from_settings(_settings("openai")).build_model("override-model")

        assert model.model_name == "override-model"

    def test_injected_model_is_used_verbatim(self):
        fake = TestModel()

        assert _test_client(fake).build_model("ignored") is fake


@pytest.mark.asyncio
async def test_run_structured_returns_typed_result():
    client = _test_client(TestModel(custom_output_args=[{"item_index": 0, "label": "x", "confidence": 0.9}]))

    result = await client.run_structured(system_prompt="system", user_prompt="user", output_type=list[_Item])

    assert isinstance(result, StructuredResult)
    assert isinstance(result.output[0], _Item)
    assert result.output[0].label == "x"
    assert result.output_json == '[{"item_index":0,"label":"x","confidence":0.9}]'
    assert result.input_tokens > 0
    assert result.output_tokens > 0


@pytest.mark.asyncio
async def test_run_structured_raises_on_schema_violation():
    def bad_response(messages, info: AgentInfo) -> ModelResponse:
        name = info.output_tools[0].name
        return ModelResponse(
            parts=[ToolCallPart(tool_name=name, args={"response": [{"item_index": "not-an-int", "label": 5}]})]
        )

    client = _test_client(FunctionModel(bad_response))

    with pytest.raises(UnexpectedModelBehavior):
        await client.run_structured(system_prompt="system", user_prompt="user", output_type=list[_Item])
