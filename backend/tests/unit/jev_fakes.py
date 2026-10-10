"""Adapt the legacy ``decide_fn`` test doubles to a ``JevClient``.

The matcher tests were written against ``async def decide(*, state, questions, **_) -> dict``.
``fake_client`` serves such a function through an httpx.MockTransport so those tests only
change their constructor line. An ``httpx.HTTPStatusError`` raised by ``decide`` becomes a
response with that status (so the client's retry/fatal logic is exercised for real); any
other exception propagates out of the transport as a connection-level failure would.
"""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from typing import Any

import httpx

from app.clients.jev_client import JevClient
from app.schemas.common import RetryPolicy

DecideFn = Callable[..., Awaitable[dict[str, Any]]]


def fake_client(decide: DecideFn) -> JevClient:
    async def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        try:
            data = await decide(
                state=body["state"],
                questions=body["questions"],
                model=body["model"],
                url=str(request.url),
                api_key="test",
            )
        except httpx.HTTPStatusError as exc:
            return httpx.Response(exc.response.status_code, json={"error": "fake"})
        return httpx.Response(200, json=data)

    return JevClient(
        url="https://jev.test/decisions",
        api_key="test",
        model="test-model",
        transport=httpx.MockTransport(handler),
        retry=RetryPolicy(base_delay=0.0),
    )
