import json

import httpx
import pytest
from pydantic import TypeAdapter

from app.harness.matchers.base import MatchOutcome
from app.harness.matchers.data import Subcat, VpsRecord
from app.harness.matchers.jev import JevMatcher
from app.harness.schemas import VpsMatch, WbsMatch


class _Phase:
    name = "WBS Categorisation"
    output_schema = list[WbsMatch]


class _VpsPhase:
    name = "VPS Matching"
    output_schema = list[VpsMatch]


def _async(v):
    async def _a(*a, **k):
        return v
    return _a()


def _err(code):
    return httpx.HTTPStatusError(
        "boom", request=httpx.Request("POST", "http://x"), response=httpx.Response(code))


def _setup(monkeypatch, n_items=1, item_type="contract_work"):
    parsed = {"line_items": [{"item_index": i, "description": "x", "contract_value": "1",
                              "item_type": item_type} for i in range(n_items)]}
    monkeypatch.setattr("app.harness.matchers.jev.harness_repo.read_workspace_file",
                        lambda db, sid, path: _async(json.dumps(parsed)))
    monkeypatch.setattr("app.harness.matchers.jev.wbs_subcategories",
                        lambda **k: _async([Subcat("u1", "DM-01", "d", "DM", 1.0)]))

    async def no_sleep(*a, **k):
        return None
    monkeypatch.setattr("app.harness.matchers.jev.asyncio.sleep", no_sleep)


def _fake_llm(n):
    res = [WbsMatch(item_index=i, wbs_code="DM-01", wbs_code_id="u1", confidence=0.8) for i in range(n)]

    async def fake_llm(*, phase_def, db, project_id, session_id):
        return MatchOutcome(output=res, output_json=TypeAdapter(list[WbsMatch]).dump_json(res).decode())
    return fake_llm


def _ok(qid):
    return {"answers": {qid: {"choice": "DM-01", "confidence": 0.9, "probabilities": {}}}, "usage": {}}


@pytest.mark.asyncio
async def test_429_then_success_retries(monkeypatch):
    _setup(monkeypatch)
    calls = {"n": 0}

    async def flaky(*, state, questions, **k):
        calls["n"] += 1
        if calls["n"] == 1:
            raise _err(429)
        return _ok(next(iter(questions)))

    out = await JevMatcher(decide_fn=flaky).match(phase_def=_Phase(), db=None, project_id="p", session_id="s")
    assert calls["n"] == 2
    assert out.output[0].wbs_code_id == "u1"


@pytest.mark.asyncio
async def test_persistent_529_falls_back_to_llm_and_logs(monkeypatch, caplog):
    _setup(monkeypatch, n_items=2)
    calls = {"n": 0}

    async def decide(*, state, questions, **k):
        qid = next(iter(questions))
        if qid == "item_0":
            calls["n"] += 1
            raise _err(529)
        return _ok(qid)
    monkeypatch.setattr("app.harness.matchers.jev.run_llm_matches", _fake_llm(2))

    with caplog.at_level("WARNING", logger="app.harness.matchers.jev"):
        out = await JevMatcher(decide_fn=decide).match(phase_def=_Phase(), db=None, project_id="p", session_id="s")
    assert calls["n"] == 4  # bounded retries
    assert {m.item_index: m.wbs_code_id for m in out.output} == {0: "u1", 1: "u1"}
    assert any("item 0 fell back to LLM" in r.getMessage() for r in caplog.records)


@pytest.mark.asyncio
async def test_401_raises_without_fallback(monkeypatch):
    _setup(monkeypatch)
    calls = {"n": 0}

    async def unauthorized(*, state, questions, **k):
        calls["n"] += 1
        raise _err(401)

    async def boom_llm(**k):
        raise AssertionError("must not fall back on 401")
    monkeypatch.setattr("app.harness.matchers.jev.run_llm_matches", boom_llm)

    with pytest.raises(httpx.HTTPStatusError):
        await JevMatcher(decide_fn=unauthorized).match(phase_def=_Phase(), db=None, project_id="p", session_id="s")
    assert calls["n"] == 1


@pytest.mark.asyncio
async def test_total_outage_all_fall_back_loudly(monkeypatch, caplog):
    _setup(monkeypatch, n_items=3)

    async def always_529(*, state, questions, **k):
        raise _err(529)
    monkeypatch.setattr("app.harness.matchers.jev.run_llm_matches", _fake_llm(3))

    with caplog.at_level("WARNING", logger="app.harness.matchers.jev"):
        out = await JevMatcher(decide_fn=always_529).match(phase_def=_Phase(), db=None, project_id="p", session_id="s")
    assert len(out.output) == 3 and all(m.wbs_code_id == "u1" for m in out.output)
    msgs = [r.getMessage() for r in caplog.records]
    assert any("all 3 items fell back" in m for m in msgs)


@pytest.mark.asyncio
async def test_vps_terminal_failure_defaults_to_new_record(monkeypatch, caplog):
    _setup(monkeypatch, n_items=1, item_type="variation")
    monkeypatch.setattr("app.harness.matchers.jev.vps_records",
                        lambda **k: _async([VpsRecord("r1", "rec", 10.0, "variation")]))

    async def always_529(*, state, questions, **k):
        raise _err(529)

    with caplog.at_level("WARNING", logger="app.harness.matchers.jev"):
        out = await JevMatcher(decide_fn=always_529).match(phase_def=_VpsPhase(), db=None, project_id="p", session_id="s")
    assert out.output[0].matched_id is None and out.output[0].confidence == 0.0
    assert any("VPS item 0" in r.getMessage() for r in caplog.records)


@pytest.mark.asyncio
async def test_32k_guard_wbs(monkeypatch):
    _setup(monkeypatch)
    big = [Subcat(f"u{i}", f"C-{i}", "d" * 200, "C", 1.0) for i in range(1000)]
    monkeypatch.setattr("app.harness.matchers.jev.wbs_subcategories", lambda **k: _async(big))

    async def decide(**k):
        raise AssertionError("should not be called")
    with pytest.raises(ValueError, match="exceeds 32k context"):
        await JevMatcher(decide_fn=decide).match(phase_def=_Phase(), db=None, project_id="p", session_id="s")


@pytest.mark.asyncio
async def test_vps_total_outage_summary(monkeypatch, caplog):
    _setup(monkeypatch, n_items=2, item_type="variation")
    monkeypatch.setattr("app.harness.matchers.jev.vps_records",
                        lambda **k: _async([VpsRecord("r1", "rec", 10.0, "variation")]))

    async def always_529(*, state, questions, **k):
        raise _err(529)

    with caplog.at_level("WARNING", logger="app.harness.matchers.jev"):
        out = await JevMatcher(decide_fn=always_529).match(phase_def=_VpsPhase(), db=None, project_id="p", session_id="s")
    assert [m.matched_id for m in out.output] == [None, None]
    assert any("all 2 VPS items failed Jev" in r.getMessage() for r in caplog.records)


@pytest.mark.asyncio
@pytest.mark.parametrize("bad", [
    {"answers": {"item_0": None}},
    {"answers": {"item_0": {"choice": "DM-01", "confidence": "abc"}}},
    {"answers": {"item_0": {"choice": ["x"], "confidence": 0.9}}},
    {"answers": {}},
])
async def test_wbs_malformed_answer_falls_back(monkeypatch, caplog, bad):
    _setup(monkeypatch, n_items=2)
    monkeypatch.setattr("app.harness.matchers.jev.run_llm_matches", _fake_llm(2))

    async def decide(*, state, questions, **k):
        qid = next(iter(questions))
        return bad if qid == "item_0" else _ok(qid)

    with caplog.at_level("WARNING", logger="app.harness.matchers.jev"):
        out = await JevMatcher(decide_fn=decide).match(phase_def=_Phase(), db=None, project_id="p", session_id="s")
    assert len(out.output) == 2 and out.output[0].wbs_code_id == "u1"
    assert any("item 0 fell back to LLM" in r.getMessage() for r in caplog.records)


@pytest.mark.asyncio
async def test_vps_malformed_answer_falls_back(monkeypatch, caplog):
    _setup(monkeypatch, n_items=1, item_type="variation")
    monkeypatch.setattr("app.harness.matchers.jev.vps_records",
                        lambda **k: _async([VpsRecord("r1", "rec", 10.0, "variation")]))

    async def decide(*, state, questions, **k):
        return {"answers": {next(iter(questions)): None}}

    with caplog.at_level("WARNING", logger="app.harness.matchers.jev"):
        out = await JevMatcher(decide_fn=decide).match(phase_def=_VpsPhase(), db=None, project_id="p", session_id="s")
    assert out.output[0].matched_id is None
    assert any("VPS item 0" in r.getMessage() for r in caplog.records)


@pytest.mark.asyncio
@pytest.mark.parametrize("code", [401, 403])
async def test_vps_fatal_raises(monkeypatch, code):
    _setup(monkeypatch, n_items=1, item_type="variation")
    monkeypatch.setattr("app.harness.matchers.jev.vps_records",
                        lambda **k: _async([VpsRecord("r1", "rec", 10.0, "variation")]))

    async def decide(**k):
        raise _err(code)
    with pytest.raises(httpx.HTTPStatusError):
        await JevMatcher(decide_fn=decide).match(phase_def=_VpsPhase(), db=None, project_id="p", session_id="s")


@pytest.mark.asyncio
async def test_wbs_403_raises(monkeypatch):
    _setup(monkeypatch)

    async def decide(**k):
        raise _err(403)
    with pytest.raises(httpx.HTTPStatusError):
        await JevMatcher(decide_fn=decide).match(phase_def=_Phase(), db=None, project_id="p", session_id="s")


@pytest.mark.asyncio
async def test_connect_error_logged_and_falls_back(monkeypatch, caplog):
    _setup(monkeypatch)
    monkeypatch.setattr("app.harness.matchers.jev.run_llm_matches", _fake_llm(1))

    async def decide(**k):
        raise httpx.ConnectError("refused")

    with caplog.at_level("WARNING", logger="app.harness.matchers.jev"):
        out = await JevMatcher(decide_fn=decide).match(phase_def=_Phase(), db=None, project_id="p", session_id="s")
    assert out.output[0].wbs_code_id == "u1"
    assert any("ConnectError" in r.getMessage() for r in caplog.records)


@pytest.mark.asyncio
async def test_all_none_does_not_emit_outage_summary(monkeypatch, caplog):
    from app.harness.matchers.jev import NONE_OPTION
    _setup(monkeypatch, n_items=2)
    monkeypatch.setattr("app.harness.matchers.jev.run_llm_matches", _fake_llm(2))

    async def decide(*, state, questions, **k):
        qid = next(iter(questions))
        return {"answers": {qid: {"choice": NONE_OPTION, "confidence": 0.9}}, "usage": {}}

    with caplog.at_level("WARNING", logger="app.harness.matchers.jev"):
        await JevMatcher(decide_fn=decide).match(phase_def=_Phase(), db=None, project_id="p", session_id="s")
    assert not any("all 2 items fell back" in r.getMessage() for r in caplog.records)
