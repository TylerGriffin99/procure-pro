"""OpenAI-compatible client factory for harness LLM utilities.

Routes to Anthropic, OpenAI, OpenRouter, or DeepSeek via the OpenAI-compatible
interface. Used by the non-agent utilities (`utils/categoriser`,
`utils/variation_matcher`); harness phases use `agent_runner` for validated,
typed structured outputs.
"""

import logging

import openai

from app.config import settings

logger = logging.getLogger(__name__)


def get_client() -> openai.AsyncOpenAI:
    """Return an AsyncOpenAI client configured for the active provider."""
    provider = settings.llm_provider.lower()

    if provider == "anthropic":
        return openai.AsyncOpenAI(
            base_url="https://api.anthropic.com/v1/",
            api_key=settings.anthropic_api_key,
        )
    if provider == "openai":
        return openai.AsyncOpenAI(api_key=settings.openai_api_key)
    if provider == "openrouter":
        return openai.AsyncOpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=settings.open_router_api_key,
        )
    if provider == "deepseek":
        return openai.AsyncOpenAI(
            base_url="https://api.deepseek.com",
            api_key=settings.deepseek_api_key,
        )

    raise ValueError(
        f"Unknown LLM_PROVIDER: {provider!r}. Use 'anthropic', 'openai', 'openrouter', or 'deepseek'."
    )
