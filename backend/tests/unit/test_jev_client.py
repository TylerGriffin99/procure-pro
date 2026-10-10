import json

import httpx
import pytest

from app.clients.jev_client import FATAL_STATUS, JevClient
from app.config import settings
from app.schemas.common import RetryPolicy


def make_client(handler) -> JevClient:
    return JevClient(
        url="https://jev.test/decisions",
        api_key="k",
        model="typesafe/jev-1.13",
        transport=httpx.MockTransport(handler),
        retry=RetryPolicy(base_delay=0.0),
    )


async def test_post_decisions_posts_and_parses():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["auth"] = request.headers["authorization"]
        captured["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "answers": {"item_0": {"choice": "DM-01", "confidence": 0.9, "probabilities": {"DM-01": 0.9}}},
                "usage": {"input_tokens": 100, "output_tokens": 0, "cost": 0.0001},
            },
        )

    state = {"description": "demo"}
    questions = {"item_0": {"type": "choice", "instructions": "?", "criteria": {"DM-01": "x"}}}
    data = await make_client(handler).post_decisions(state=state, questions=questions)
    assert data["answers"]["item_0"]["choice"] == "DM-01"
    assert data["usage"]["input_tokens"] == 100
    assert captured["url"] == "https://jev.test/decisions"
    assert captured["auth"] == "Bearer k"
    assert captured["body"] == {"model": "typesafe/jev-1.13", "state": state, "questions": questions}


async def test_post_decisions_raises_on_http_error():
    client = make_client(lambda r: httpx.Response(500, json={"error": "boom"}))
    with pytest.raises(httpx.HTTPStatusError):
        await client.post_decisions(state={}, questions={})


async def test_choose_wraps_one_choice_question_and_validates():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["questions"] = json.loads(request.content)["questions"]
        return httpx.Response(200, json={"answers": {"item_3": {"choice": "A", "confidence": 0.7}}, "usage": {"input_tokens": 5}})

    out = await make_client(handler).choose(qid="item_3", state={"d": 1}, criteria={"A": "a", "B": "b"}, instructions="pick")
    assert seen["questions"] == {"item_3": {"type": "choice", "instructions": "pick", "criteria": {"A": "a", "B": "b"}}}
    assert out.answers["item_3"].choice == "A"
    assert out.usage.input_tokens == 5


async def test_choose_retries_429_then_succeeds():
    n = {"calls": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        n["calls"] += 1
        if n["calls"] == 1:
            return httpx.Response(429)
        return httpx.Response(200, json={"answers": {"q": {"choice": "A", "confidence": 1.0}}})

    out = await make_client(handler).choose(qid="q", state={}, criteria={"A": "a"}, instructions="i")
    assert n["calls"] == 2
    assert out.answers["q"].choice == "A"


async def test_choose_gives_up_after_max_attempts_on_529():
    n = {"calls": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        n["calls"] += 1
        return httpx.Response(529)

    with pytest.raises(httpx.HTTPStatusError):
        await make_client(handler).choose(qid="q", state={}, criteria={}, instructions="i")
    assert n["calls"] == 4


@pytest.mark.parametrize("code", sorted(FATAL_STATUS))
async def test_choose_fatal_status_raises_without_retry(code):
    n = {"calls": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        n["calls"] += 1
        return httpx.Response(code)

    with pytest.raises(httpx.HTTPStatusError) as exc_info:
        await make_client(handler).choose(qid="q", state={}, criteria={}, instructions="i")
    assert n["calls"] == 1
    assert JevClient.is_fatal(exc_info.value)


def test_check_context_budget_rejects_oversized_request():
    client = make_client(lambda r: httpx.Response(200))
    criteria = {f"C-{i}": "d" * 200 for i in range(1000)}
    with pytest.raises(ValueError, match="exceeds 32k context"):
        client.check_context_budget(phase_name="WBS", states=[{"description": "x"}], criteria=criteria, instructions="i")


def test_from_settings_reads_jev_settings():
    client = JevClient.from_settings(settings)
    assert client.url == settings.jev_decisions_url
    assert client.model == settings.jev_model
    assert client.api_key == settings.open_router_api_key


def test_item_state_shape():
    from app.harness.schemas import ParsedClaimItem

    item = ParsedClaimItem(item_index=0, description="d", item_type="variation", contract_value="1")
    assert JevClient.item_state(item) == {"description": "d", "contract_value": "1", "item_type": "variation"}


def test_is_fatal_for_transport_misconfiguration():
    req = httpx.Request("POST", "http://x")
    assert JevClient.is_fatal(httpx.UnsupportedProtocol("x", request=req)) is True
    assert JevClient.is_fatal(httpx.LocalProtocolError("x")) is True
    for code in (301, 405):
        err = httpx.HTTPStatusError("boom", request=req, response=httpx.Response(code, request=req))
        assert JevClient.is_fatal(err) is True
    assert JevClient.is_fatal(httpx.ConnectError("x")) is False
