import httpx
import pytest
from pydantic import TypeAdapter

from app.clients.jev_client import JevClient
from app.constants import MatcherName
from app.exceptions import ExternalServiceError
from app.harness.matchers.jev import NONE_OPTION, match_vps, match_wbs
from app.harness.schemas import JevTuning, MatchOutcome, ParsedClaimItem, Subcat, VpsRecord, WbsMatch
from tests.unit.jev_fakes import fake_client

TUNING = JevTuning(confidence_floor=0.6, max_concurrency=4)
SUBCATS = [Subcat(id="u1", code="DM-01", description="d", parent_code="DM", contract_sum=1.0)]
RECORDS = [VpsRecord(id="r1", description="rec", value=10.0, item_type="variation")]


def items(n, item_type="contract_work"):
    return [ParsedClaimItem(item_index=i, description="x", contract_value="1", item_type=item_type) for i in range(n)]


def err(code):
    return httpx.HTTPStatusError("boom", request=httpx.Request("POST", "http://x"), response=httpx.Response(code))


def fake_llm(n):
    res = [WbsMatch(item_index=i, wbs_code="DM-01", wbs_code_id="u1", confidence=0.8) for i in range(n)]

    async def llm():
        return MatchOutcome(
            matcher=MatcherName.llm, output=res, output_json=TypeAdapter(list[WbsMatch]).dump_json(res).decode()
        )

    return llm


async def no_fallback():
    raise AssertionError("must not fall back")


def ok(qid):
    return {"answers": {qid: {"choice": "DM-01", "confidence": 0.9, "probabilities": {}}}, "usage": {}}


async def wbs(client, n=1, fallback=no_fallback, subcats=SUBCATS):
    return await match_wbs(
        items(n), subcats, phase_name="WBS Categorisation", client=client, tuning=TUNING, fallback=fallback
    )


async def vps(client, n=1):
    return await match_vps(items(n, "variation"), RECORDS, phase_name="VPS Matching", client=client, tuning=TUNING)


@pytest.mark.asyncio
async def test_429_then_success_retries():
    calls = {"n": 0}

    async def flaky(*, state, questions, **k):
        calls["n"] += 1
        if calls["n"] == 1:
            raise err(429)
        return ok(next(iter(questions)))

    out = await wbs(fake_client(flaky))
    assert calls["n"] == 2
    assert out.output[0].wbs_code_id == "u1"


@pytest.mark.asyncio
async def test_persistent_529_falls_back_to_llm_and_logs(caplog):
    calls = {"n": 0}

    async def decide(*, state, questions, **k):
        qid = next(iter(questions))
        if qid == "item_0":
            calls["n"] += 1
            raise err(529)
        return ok(qid)

    with caplog.at_level("WARNING", logger="app.harness.matchers.jev"):
        out = await wbs(fake_client(decide), n=2, fallback=fake_llm(2))
    assert calls["n"] == 4  # bounded retries
    assert {m.item_index: m.wbs_code_id for m in out.output} == {0: "u1", 1: "u1"}
    assert any("item 0 fell back to LLM" in r.getMessage() for r in caplog.records)


@pytest.mark.asyncio
async def test_401_raises_without_fallback():
    calls = {"n": 0}

    async def unauthorized(*, state, questions, **k):
        calls["n"] += 1
        raise err(401)

    with pytest.raises(httpx.HTTPStatusError):
        await wbs(fake_client(unauthorized))
    assert calls["n"] == 1


@pytest.mark.asyncio
async def test_total_outage_all_fall_back_loudly(caplog):
    async def always_529(*, state, questions, **k):
        raise err(529)

    with caplog.at_level("WARNING", logger="app.harness.matchers.jev"):
        out = await wbs(fake_client(always_529), n=3, fallback=fake_llm(3))
    assert len(out.output) == 3 and all(m.wbs_code_id == "u1" for m in out.output)
    msgs = [r.getMessage() for r in caplog.records]
    assert any("all 3 items fell back" in m for m in msgs)


@pytest.mark.asyncio
async def test_vps_terminal_failure_defaults_to_new_record(caplog):
    async def first_fails(*, state, questions, **k):
        qid = next(iter(questions))
        if qid == "item_0":
            raise err(529)
        return {"answers": {qid: {"choice": "r1", "confidence": 0.9}}, "usage": {}}

    with caplog.at_level("WARNING", logger="app.harness.matchers.jev"):
        out = await vps(fake_client(first_fails), n=2)
    assert out.output[0].matched_id is None and out.output[0].confidence == 0.0
    assert out.output[1].matched_id == "r1"
    assert out.fell_back == 1
    assert any("VPS item 0" in r.getMessage() for r in caplog.records)


@pytest.mark.asyncio
async def test_32k_guard_wbs():
    big = [
        Subcat(id=f"u{i}", code=f"C-{i}", description="d" * 200, parent_code="C", contract_sum=1.0) for i in range(1000)
    ]

    async def decide(**k):
        raise AssertionError("should not be called")

    with pytest.raises(ValueError, match="exceeds 32k context"):
        await wbs(fake_client(decide), subcats=big)


@pytest.mark.asyncio
async def test_vps_total_outage_fails_the_phase(caplog):
    async def always_529(*, state, questions, **k):
        raise err(529)

    with caplog.at_level("WARNING", logger="app.harness.matchers.jev"):
        with pytest.raises(ExternalServiceError, match="Jev matcher failed for every item"):
            await vps(fake_client(always_529), n=2)
    assert any("all 2 VPS items failed Jev" in r.getMessage() for r in caplog.records)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "bad",
    [
        {"answers": {"item_0": None}},
        {"answers": {"item_0": {"choice": "DM-01", "confidence": "abc"}}},
        {"answers": {"item_0": {"choice": ["x"], "confidence": 0.9}}},
        {"answers": {}},
    ],
)
async def test_wbs_malformed_answer_falls_back(caplog, bad):
    async def decide(*, state, questions, **k):
        qid = next(iter(questions))
        return bad if qid == "item_0" else ok(qid)

    with caplog.at_level("WARNING", logger="app.harness.matchers.jev"):
        out = await wbs(fake_client(decide), n=2, fallback=fake_llm(2))
    assert len(out.output) == 2 and out.output[0].wbs_code_id == "u1"
    assert any("item 0 fell back to LLM" in r.getMessage() for r in caplog.records)


@pytest.mark.asyncio
async def test_vps_malformed_answer_falls_back(caplog):
    async def decide(*, state, questions, **k):
        qid = next(iter(questions))
        if qid == "item_0":
            return {"answers": {qid: None}}
        return {"answers": {qid: {"choice": "r1", "confidence": 0.9}}, "usage": {}}

    with caplog.at_level("WARNING", logger="app.harness.matchers.jev"):
        out = await vps(fake_client(decide), n=2)
    assert out.output[0].matched_id is None
    assert any("VPS item 0" in r.getMessage() for r in caplog.records)


@pytest.mark.asyncio
@pytest.mark.parametrize("code", [400, 401, 402, 403, 404, 422])
async def test_vps_fatal_raises(code):
    async def decide(**k):
        raise err(code)

    with pytest.raises(httpx.HTTPStatusError):
        await vps(fake_client(decide))


@pytest.mark.asyncio
async def test_wbs_403_raises():
    async def decide(**k):
        raise err(403)

    with pytest.raises(httpx.HTTPStatusError):
        await wbs(fake_client(decide))


@pytest.mark.asyncio
async def test_connect_error_logged_and_falls_back(caplog):
    async def decide(**k):
        raise httpx.ConnectError("refused")

    with caplog.at_level("WARNING", logger="app.harness.matchers.jev"):
        out = await wbs(fake_client(decide), fallback=fake_llm(1))
    assert out.output[0].wbs_code_id == "u1"
    assert any("ConnectError" in r.getMessage() for r in caplog.records)


@pytest.mark.asyncio
async def test_all_none_does_not_emit_outage_summary(caplog):
    async def decide(*, state, questions, **k):
        qid = next(iter(questions))
        return {"answers": {qid: {"choice": NONE_OPTION, "confidence": 0.9}}, "usage": {}}

    with caplog.at_level("WARNING", logger="app.harness.matchers.jev"):
        await wbs(fake_client(decide), n=2, fallback=fake_llm(2))
    assert not any("all 2 items fell back" in r.getMessage() for r in caplog.records)


@pytest.mark.asyncio
@pytest.mark.parametrize("code", [402, 404])
async def test_wbs_credit_and_notfound_raise(code):
    async def decide(**k):
        raise err(code)

    with pytest.raises(httpx.HTTPStatusError):
        await wbs(fake_client(decide))


@pytest.mark.asyncio
async def test_bad_url_scheme_raises_without_fallback():
    client = JevClient(url="openrouter.ai/no-scheme", api_key="k", model="m")
    with pytest.raises(httpx.UnsupportedProtocol):
        await wbs(client)
