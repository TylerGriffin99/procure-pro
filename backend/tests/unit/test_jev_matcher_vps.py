import pytest

from app.harness.matchers.jev import NONE_OPTION, match_vps
from app.harness.schemas import JevTuning, ParsedClaimItem, VpsRecord
from tests.unit.jev_fakes import fake_client

ITEMS = [
    ParsedClaimItem(item_index=0, description="VO 1", contract_value="900", item_type="variation"),
    ParsedClaimItem(item_index=1, description="PS lift", contract_value="5000", item_type="provisional_sum"),
]
RECORDS = [
    VpsRecord(id="v1", description="Variation one", value=900.0, item_type="variation"),
    VpsRecord(id="v2", description="No value record", value=None, item_type="provisional_sum"),
]


def client_answering(answers, seen=None):
    async def fake_decide(*, state, questions, model, url, api_key, timeout=30.0):
        qid = next(iter(questions))
        if seen is not None:
            seen.append(questions[qid]["criteria"])
        return {"answers": {qid: answers[qid]}, "usage": {"input_tokens": 5}}

    return fake_client(fake_decide)


async def run(answers, items=ITEMS, seen=None, floor=0.6):
    return await match_vps(
        items,
        RECORDS,
        phase_name="Variation Matching",
        client=client_answering(answers, seen),
        tuning=JevTuning(confidence_floor=floor, max_concurrency=4),
    )


@pytest.mark.asyncio
async def test_vps_maps_and_none_is_null():
    answers = {"item_0": {"choice": "v1", "confidence": 0.9}, "item_1": {"choice": NONE_OPTION, "confidence": 0.5}}
    seen = []
    out = await run(answers, seen=seen)
    by_index = {m.item_index: m for m in out.output}
    assert set(by_index) == {0, 1}
    assert by_index[0].matched_id == "v1" and by_index[0].item_type == "variation"
    assert by_index[0].confidence == 0.9
    assert by_index[1].matched_id is None and by_index[1].item_type == "provisional_sum"
    assert out.input_tokens == 10
    crit = seen[0]
    assert crit["v1"] == "Variation one — $900.00"
    assert crit["v2"] == "No value record"
    assert NONE_OPTION in crit


@pytest.mark.asyncio
async def test_vps_out_of_criteria_is_null_and_warns(caplog):
    answers = {"item_0": {"choice": "bogus", "confidence": 0.7}, "item_1": {"choice": "v2", "confidence": 0.6}}
    with caplog.at_level("WARNING", logger="app.harness.matchers.jev"):
        out = await run(answers)
    by_index = {m.item_index: m for m in out.output}
    assert by_index[0].matched_id is None
    assert by_index[1].matched_id == "v2"
    assert "bogus" in caplog.text
    # The out-of-criteria choice is counted as a grounding violation; the valid one is not.
    assert out.out_of_criteria == 1


@pytest.mark.asyncio
async def test_vps_empty_in_scope_set():
    out = await run({}, items=[])
    assert out.output == [] and out.output_json == "[]"


@pytest.mark.asyncio
async def test_vps_valid_choice_below_floor_is_new_and_warns(caplog):
    answers = {"item_0": {"choice": "v1", "confidence": 0.3}, "item_1": {"choice": "v2", "confidence": 0.9}}
    with caplog.at_level("WARNING", logger="app.harness.matchers.jev"):
        out = await run(answers, floor=0.6)
    by_index = {m.item_index: m for m in out.output}
    assert by_index[0].matched_id is None and by_index[0].confidence == 0.3
    assert by_index[1].matched_id == "v2"
    assert "below floor" in caplog.text
    assert out.fell_back == 0
