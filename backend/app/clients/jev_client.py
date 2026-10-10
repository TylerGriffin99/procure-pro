"""Jev decisions API client: transport, retry, request shaping, error classification.

Everything that touches the Jev HTTP API lives here so the matcher
(:mod:`app.harness.matchers.jev`) stays a thin orchestrator.
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

import httpx

from app.harness.schemas import JevDecisionResponse
from app.schemas.common import RetryPolicy
from app.utils.retry import retry_async

if TYPE_CHECKING:
    from app.config import Settings
    from app.harness.schemas import ParsedClaimItem

logger = logging.getLogger(__name__)

RETRYABLE_STATUS = frozenset({429, 529})
# Config/auth/credit errors: raise, never fall back.
FATAL_STATUS = frozenset({400, 401, 402, 403, 404, 422})
MAX_CONTEXT_TOKENS = 32_000
DEFAULT_RETRY = RetryPolicy()


class JevClient:
    def __init__(
        self,
        *,
        url: str,
        api_key: str,
        model: str,
        timeout: float = 30.0,
        retry: RetryPolicy = DEFAULT_RETRY,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.url = url
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self.retry = retry
        self.transport = transport

    @classmethod
    def from_settings(cls, settings: Settings) -> JevClient:
        return cls(
            url=settings.jev_decisions_url,
            api_key=settings.open_router_api_key,
            model=settings.jev_model,
        )

    @staticmethod
    def is_fatal(exc: Exception) -> bool:
        """A Jev HTTP error that must not fall back (config/auth/credit error)."""
        return isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code in FATAL_STATUS

    @staticmethod
    def is_retryable(exc: Exception) -> bool:
        return (
            isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code in RETRYABLE_STATUS
        )

    @staticmethod
    def item_state(item: ParsedClaimItem) -> dict[str, Any]:
        """The per-item ``state`` payload sent to the decisions API."""
        return {
            "description": item.description,
            "contract_value": item.contract_value,
            "item_type": item.item_type,
        }

    def check_context_budget(
        self,
        *,
        phase_name: str,
        states: list[dict[str, Any]],
        criteria: dict[str, str],
        instructions: str,
        max_tokens: int = MAX_CONTEXT_TOKENS,
    ) -> None:
        """Reject a request whose largest serialized item exceeds ~32k tokens (chars/4 proxy)."""
        worst = max(states, key=lambda s: len(json.dumps(s, default=str)), default={})
        payload = json.dumps(
            {
                "state": worst,
                "questions": {"item_0": {"instructions": instructions, "criteria": criteria}},
            },
            default=str,
        )
        if len(payload) / 4 > max_tokens:
            raise ValueError(f"Jev request for '{phase_name}' exceeds 32k context")

    async def post_decisions(
        self, *, state: dict[str, Any], questions: dict[str, Any]
    ) -> dict[str, Any]:
        """POST one decisions request. Raises httpx.HTTPStatusError on non-2xx."""
        async with httpx.AsyncClient(timeout=self.timeout, transport=self.transport) as http:
            resp = await http.post(
                self.url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={"model": self.model, "state": state, "questions": questions},
            )
            resp.raise_for_status()
            return resp.json()

    async def choose(
        self,
        *,
        qid: str,
        state: dict[str, Any],
        criteria: dict[str, str],
        instructions: str,
    ) -> JevDecisionResponse:
        """Ask one ``choice`` question. 429/529 are retried per ``self.retry``; fatal
        statuses raise immediately; any other terminal failure is logged and re-raised."""
        questions = {qid: {"type": "choice", "instructions": instructions, "criteria": criteria}}

        async def attempt() -> dict[str, Any]:
            return await self.post_decisions(state=state, questions=questions)

        try:
            raw = await retry_async(attempt, policy=self.retry, should_retry=self.is_retryable)
        except httpx.HTTPStatusError as exc:
            if not self.is_fatal(exc):
                logger.warning("Jev decision %s failed: HTTP %s", qid, exc.response.status_code)
            raise
        return JevDecisionResponse.model_validate(raw)
