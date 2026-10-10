import json
import pytest
from app.harness.matchers.jev import JevMatcher, NONE_OPTION
from app.harness.schemas import VpsRecord
from app.harness.schemas import VpsMatch


class _Phase:
    name = "Variation Matching"
    output_schema = list[VpsMatch]


PARSED = {"line_items": [
    {"item_index": 0, "description": "VO 1", "contract_value": "900", "item_type": "variation"},
    {"item_index": 1, "description": "PS lift", "contract_value": "5000", "item_type": "provisional_sum"},
    {"item_index": 2, "description": "work", "contract_value": "1", "item_type": "contract_work"},
]}
RECORDS = [VpsRecord(id="v1", description="Variation one", value=900.0, item_type="variation"),
           VpsRecord(id="v2", description="No value record", value=None, item_type="provisional_sum")]


def _matcher(monkeypatch, answers, parsed=PARSED, seen=None):
    async def fake_read(db, sid, path):
        return json.dumps(parsed)
    monkeypatch.setattr("app.repos.harness_repo.read_workspace_file", fake_read)

    async def fake_records(*, db, project_id):
        return RECORDS
    monkeypatch.setattr("app.harness.matchers.jev.vps_records", fake_records)

    async def fake_decide(*, state, questions, model, url, api_key, timeout=30.0):
        qid = next(iter(questions))
        if seen is not None:
            seen.append(questions[qid]["criteria"])
        return {"answers": {qid: answers[qid]}, "usage": {"input_tokens": 5}}
    return JevMatcher(decide_fn=fake_decide)


async def _run(m):
    return await m.match(phase_def=_Phase(), db=None, project_id="p", session_id="s")


@pytest.mark.asyncio
async def test_vps_maps_and_none_is_null(monkeypatch):
    answers = {"item_0": {"choice": "v1", "confidence": 0.9},
               "item_1": {"choice": NONE_OPTION, "confidence": 0.5}}
    seen = []
    out = await _run(_matcher(monkeypatch, answers, seen=seen))
    by_index = {m.item_index: m for m in out.output}
    assert set(by_index) == {0, 1}                       # contract_work excluded
    assert by_index[0].matched_id == "v1" and by_index[0].item_type == "variation"
    assert by_index[0].confidence == 0.9
    assert by_index[1].matched_id is None and by_index[1].item_type == "provisional_sum"
    assert out.input_tokens == 10
    crit = seen[0]
    assert crit["v1"] == "Variation one — $900.00"
    assert crit["v2"] == "No value record"
    assert NONE_OPTION in crit


@pytest.mark.asyncio
async def test_vps_out_of_criteria_is_null_and_warns(monkeypatch, caplog):
    answers = {"item_0": {"choice": "bogus", "confidence": 0.7},
               "item_1": {"choice": "v2", "confidence": 0.6}}
    with caplog.at_level("WARNING", logger="app.harness.matchers.jev"):
        out = await _run(_matcher(monkeypatch, answers))
    by_index = {m.item_index: m for m in out.output}
    assert by_index[0].matched_id is None
    assert by_index[1].matched_id == "v2"
    assert "bogus" in caplog.text
    # The out-of-criteria choice is counted as a grounding violation; the valid one is not.
    assert out.out_of_criteria == 1


@pytest.mark.asyncio
async def test_vps_empty_in_scope_set(monkeypatch):
    parsed = {"line_items": [PARSED["line_items"][2]]}
    out = await _run(_matcher(monkeypatch, {}, parsed=parsed))
    assert out.output == [] and out.output_json == "[]"


@pytest.mark.asyncio
async def test_vps_valid_choice_below_floor_is_new_and_warns(monkeypatch, caplog):
    import app.config
    monkeypatch.setattr(app.config.settings, "jev_confidence_floor", 0.6, raising=False)
    answers = {"item_0": {"choice": "v1", "confidence": 0.3},
               "item_1": {"choice": "v2", "confidence": 0.9}}
    with caplog.at_level("WARNING", logger="app.harness.matchers.jev"):
        out = await _run(_matcher(monkeypatch, answers))
    by_index = {m.item_index: m for m in out.output}
    assert by_index[0].matched_id is None and by_index[0].confidence == 0.3
    assert by_index[1].matched_id == "v2"
    assert "below floor" in caplog.text
    assert out.fell_back == 0
