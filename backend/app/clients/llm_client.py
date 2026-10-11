from __future__ import annotations

import logging
from typing import Any

from pydantic import TypeAdapter
from pydantic_ai import Agent
from pydantic_ai.models import Model
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

from app.config import Settings
from app.constants.enums import LlmProvider
from app.constants.values import PROVIDER_TABLE
from app.schemas.base import StrictModel

logger = logging.getLogger(__name__)


class StructuredResult[T](StrictModel):
    output: T
    output_json: str
    input_tokens: int
    output_tokens: int


class LlmClient:
    def __init__(
        self,
        *,
        provider: LlmProvider,
        model_name: str,
        api_key: str,
        base_url: str | None = None,
        model: Model | None = None,
    ) -> None:
        self.provider = provider
        self.model_name = model_name
        self.api_key = api_key
        self.base_url = base_url
        self.model = model

    @classmethod
    def from_settings(cls, settings: Settings) -> LlmClient:
        base_url, key_field = PROVIDER_TABLE[settings.llm_provider]
        return cls(
            provider=settings.llm_provider,
            model_name=settings.llm_model,
            api_key=getattr(settings, key_field),
            base_url=base_url,
        )

    def build_model(self, model_name: str | None = None) -> Model:
        if self.model is not None:
            return self.model
        provider = OpenAIProvider(base_url=self.base_url, api_key=self.api_key)
        return OpenAIChatModel(model_name or self.model_name, provider=provider)

    async def run_structured[T](
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        output_type: type[T] | Any,
        model_name: str | None = None,
        phase_name: str | None = None,
    ) -> StructuredResult[T]:
        logger.info(
            "Agent run%s: output_type=%s",
            f" phase={phase_name}" if phase_name else "",
            getattr(output_type, "__name__", repr(output_type)),
        )
        agent = Agent(self.build_model(model_name), output_type=output_type, system_prompt=system_prompt)
        result = await agent.run(user_prompt)
        usage = result.usage
        return StructuredResult[T](
            output=result.output,
            output_json=TypeAdapter(output_type).dump_json(result.output).decode(),
            input_tokens=usage.input_tokens or 0,
            output_tokens=usage.output_tokens or 0,
        )
