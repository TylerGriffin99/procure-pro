"""pydantic-ai agent runner for harness phases.

Runs a single structured LLM call through a pydantic-ai ``Agent`` whose
``output_type`` is a pydantic model (or ``list`` of one), so every result is
validated and fully typed. Provider routing (:func:`build_model`) reads
``settings.llm_provider`` (anthropic / openai / openrouter / deepseek); all four are
reached through the OpenAI-compatible interface.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any

# Silence the first-run telemetry banner so test/log output stays pristine.
os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")

from pydantic import TypeAdapter
from pydantic_ai import Agent
from pydantic_ai.models import Model
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

from app.config import settings

logger = logging.getLogger(__name__)


def build_model(provider: str | None = None, model_name: str | None = None) -> OpenAIChatModel:
    """Build an OpenAI-compatible model for the configured (or given) provider."""
    provider = (provider or settings.llm_provider).lower()
    model_name = model_name or settings.llm_model

    if provider == "anthropic":
        openai_provider = OpenAIProvider(base_url="https://api.anthropic.com/v1/", api_key=settings.anthropic_api_key)
    elif provider == "openai":
        openai_provider = OpenAIProvider(api_key=settings.openai_api_key)
    elif provider == "openrouter":
        openai_provider = OpenAIProvider(base_url="https://openrouter.ai/api/v1", api_key=settings.open_router_api_key)
    elif provider == "deepseek":
        openai_provider = OpenAIProvider(base_url="https://api.deepseek.com", api_key=settings.deepseek_api_key)
    else:
        raise ValueError(f"Unknown LLM_PROVIDER: {provider!r}. Use 'anthropic', 'openai', 'openrouter', or 'deepseek'.")

    return OpenAIChatModel(model_name, provider=openai_provider)


@dataclass
class StructuredResult:
    """A validated, typed agent result plus its serialized form and usage."""

    output: Any
    output_json: str
    input_tokens: int
    output_tokens: int


async def run_structured(
    output_type: Any, system_prompt: str, user_prompt: str, model: Model | None = None, phase_name: str | None = None
) -> StructuredResult:
    """Run one structured completion, returning a validated ``output_type`` instance.

    ``output_type`` is any pydantic-ai output spec — a ``BaseModel`` subclass or a
    ``list[Model]``. The model response is validated against it by pydantic-ai; an
    unparseable or schema-violating response raises rather than passing through.
    """
    resolved_model = model or build_model()

    logger.info(
        "Agent run%s: output_type=%s",
        f" phase={phase_name}" if phase_name else "",
        getattr(output_type, "__name__", repr(output_type)),
    )

    agent = Agent(resolved_model, output_type=output_type, system_prompt=system_prompt)
    result = await agent.run(user_prompt)

    usage = result.usage
    return StructuredResult(
        output=result.output,
        output_json=TypeAdapter(output_type).dump_json(result.output).decode(),
        input_tokens=usage.input_tokens or 0,
        output_tokens=usage.output_tokens or 0,
    )
