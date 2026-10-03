from __future__ import annotations

from typing import Any

import httpx

# Overridable in tests via monkeypatch (httpx.MockTransport).
_transport: httpx.BaseTransport | None = None


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
