import pytest
from pydantic import ValidationError

from app.config import Settings
from app.constants.enums import LlmProvider
from app.constants.values import PROVIDER_TABLE

NO_KEYS = {key_field: "" for _, key_field in PROVIDER_TABLE.values()}


@pytest.mark.parametrize("provider", list(LlmProvider))
def test_configured_provider_with_its_key_loads(provider):
    _, key_field = PROVIDER_TABLE[provider]

    settings = Settings(secret_key="k", llm_provider=provider.value, llm_model="m", **{**NO_KEYS, key_field: "key"})

    assert settings.llm_provider is provider


@pytest.mark.parametrize("provider", list(LlmProvider))
def test_configured_provider_with_an_empty_key_fails_at_boot(provider):
    _, key_field = PROVIDER_TABLE[provider]

    with pytest.raises(ValidationError, match=key_field.upper()):
        Settings(secret_key="k", llm_provider=provider.value, llm_model="m", **NO_KEYS)
