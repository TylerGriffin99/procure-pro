import json

import httpx
import pytest

from app.harness.matchers.jev_client import call_decisions


@pytest.mark.asyncio
async def test_call_decisions_posts_and_parses(monkeypatch):
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["auth"] = request.headers["authorization"]
        captured["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "answers": {
                    "item_0": {"choice": "DM-01", "confidence": 0.9, "probabilities": {"DM-01": 0.9}}
                },
                "usage": {"input_tokens": 100, "output_tokens": 0, "cost": 0.0001},
            },
        )

    monkeypatch.setattr("app.harness.matchers.jev_client._transport", httpx.MockTransport(handler))

    state = {"description": "demo"}
    questions = {"item_0": {"type": "choice", "instructions": "?", "criteria": {"DM-01": "x"}}}
    url = "https://openrouter.ai/api/alpha/decisions"
    data = await call_decisions(
        state=state, questions=questions, model="typesafe/jev-1.13", url=url, api_key="k"
    )
    assert data["answers"]["item_0"]["choice"] == "DM-01"
    assert data["usage"]["input_tokens"] == 100
    assert captured["url"] == url
    assert captured["auth"] == "Bearer k"
    assert captured["body"] == {"model": "typesafe/jev-1.13", "state": state, "questions": questions}


@pytest.mark.asyncio
async def test_call_decisions_raises_on_http_error(monkeypatch):
    transport = httpx.MockTransport(lambda r: httpx.Response(500, json={"error": "boom"}))
    monkeypatch.setattr("app.harness.matchers.jev_client._transport", transport)
    with pytest.raises(httpx.HTTPStatusError):
        await call_decisions(state={}, questions={}, model="m", url="https://x.test/d", api_key="k")
