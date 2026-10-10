"""Jev decisions API client: transport, retry, request-shaping, and error classification.

Everything that touches the Jev HTTP API lives here so the matcher
(:mod:`app.harness.matchers.jev`) stays a thin orchestrator. ``call_decisions`` is the
raw transport seam (and the default ``decide_fn``); ``decide_with_retry`` wraps a
``decide_fn`` with bounded backoff and validates the response into a typed
:class:`~app.harness.schemas.JevDecisionResponse`.
"""
from __future__ import annotations

import asyncio
import json
import logging
import random
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any

import httpx

from app.harness.schemas import JevDecisionResponse

if TYPE_CHECKING:
    from app.harness.schemas import ParsedClaimItem

logger = logging.getLogger(__name__)

# The decisions-call seam: ``call_decisions`` or a test double with the same shape.
DecideFn = Callable[..., Awaitable[dict[str, Any]]]

RETRYABLE_STATUS = {429, 529}
FATAL_STATUS = {400, 401, 402, 403, 404, 422}  # config/auth/credit errors: raise, never fall back
MAX_CONTEXT_TOKENS = 32_000

# Overridable in tests via monkeypatch (httpx.MockTransport).
_transport: httpx.AsyncBaseTransport | None = None


async def call_decisions(
    *, state: Any, questions: Any, model: str, url: str, api_key: str, timeout: float = 30.0
) -> dict[str, Any]:
    """POST one decisions request. Raises httpx.HTTPStatusError on non-2xx."""
    async with httpx.AsyncClient(timeout=timeout, transport=_transport) as client:
        resp = await client.post(
            url,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={"model": model, "state": state, "questions": questions},
        )
        resp.raise_for_status()
        return resp.json()


def is_fatal(exc: Exception) -> bool:
    """True for a Jev HTTP error that must not fall back (config/auth/credit error)."""
    return isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code in FATAL_STATUS


def item_state(item: ParsedClaimItem) -> dict[str, Any]:
    """The per-item ``state`` payload sent to the Jev decisions API."""
    return {"description": item.description,
            "contract_value": item.contract_value,
            "item_type": item.item_type}


def check_context_budget(
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
        {"state": worst, "questions": {"item_0": {"instructions": instructions, "criteria": criteria}}},
        default=str,
    )
    if len(payload) / 4 > max_tokens:
        raise ValueError(f"Jev request for '{phase_name}' exceeds 32k context")


async def decide_with_retry(
    decide_fn: DecideFn,
    *,
    qid: str,
    state: dict[str, Any],
    criteria: dict[str, str],
    instructions: str,
    model: str,
    url: str,
    api_key: str,
    max_attempts: int = 4,
) -> JevDecisionResponse:
    """Call Jev once per attempt, retrying 429/529 with exponential backoff + jitter.

    Config/auth/credit errors (``FATAL_STATUS``) are raised immediately (never fall back);
    any other terminal failure is logged and re-raised. The backoff uses ``asyncio.sleep``,
    which yields to the event loop (it never blocks it). The caller sleeps while still
    holding its concurrency slot — a deliberate backpressure choice: when Jev is rate-
    limiting us (429/529) we must not launch *more* concurrent calls at it.
    """
    delay = 0.5
    for attempt in range(1, max_attempts + 1):
        try:
            raw = await decide_fn(
                state=state,
                questions={qid: {"type": "choice", "instructions": instructions, "criteria": criteria}},
                model=model, url=url, api_key=api_key,
            )
            return JevDecisionResponse.model_validate(raw)
        except httpx.HTTPStatusError as e:
            code = e.response.status_code
            if code in FATAL_STATUS:
                raise
            if code in RETRYABLE_STATUS and attempt < max_attempts:
                await asyncio.sleep(delay + random.uniform(0, delay))
                delay *= 2
                continue
            logger.warning("Jev decision %s failed after %d attempt(s): HTTP %s", qid, attempt, code)
            raise
    raise RuntimeError("unreachable: decide_with_retry loop exhausted")
