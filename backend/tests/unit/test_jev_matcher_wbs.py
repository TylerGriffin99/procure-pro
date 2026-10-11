import pytest

from app.constants import MatcherName
from app.harness.matchers.jev import NONE_OPTION, build_wbs_criteria, match_wbs
from app.harness.schemas import JevTuning, MatchOutcome, ParsedClaimItem, Subcat, WbsMatch
from tests.unit.jev_fakes import fake_client

TUNING = JevTuning(confidence_floor=0.6, max_concurrency=4)
SUBCATS = [
    Subcat(id="u1", code="DM-01", description="Soft strip", parent_code="DM", contract_sum=12345.0),
    Subcat(id="u2", code="PL-03", description="Preliminaries", parent_code="PL", contract_sum=4000.0),
]
ITEMS = [
    ParsedClaimItem(item_index=0, description="Demolition", contract_value="12,345.00"),
    ParsedClaimItem(item_index=1, description="overhead", contract_value=None),
]


def client_answering(answers):
    async def fake_decide(*, state, questions, model, url, api_key, timeout=30.0):
        qid = next(iter(questions))  # one question per call
        return {"answers": {qid: answers[qid]}, "usage": {"input_tokens": 5, "output_tokens": 0, "cost": 0.0}}

    return fake_client(fake_decide)


async def no_fallback():
    raise AssertionError("the LLM fallback must not run")


async def run(answers, items=ITEMS, subcats=SUBCATS, fallback=no_fallback):
    return await match_wbs(
        items,
        subcats,
        phase_name="WBS Categorisation",
        client=client_answering(answers),
        tuning=TUNING,
        fallback=fallback,
    )


@pytest.mark.asyncio
async def test_wbs_happy_path_maps_choice_to_code_and_id():
    answers = {
        "item_0": {"choice": "DM-01", "confidence": 0.95, "probabilities": {"DM-01": 0.95}},
        "item_1": {"choice": "PL-03", "confidence": 0.8, "probabilities": {"PL-03": 0.8}},
    }
    out = await run(answers)
    by_index = {m.item_index: m for m in out.output}
    assert out.matcher is MatcherName.jev
    assert set(by_index) == {0, 1}
    assert by_index[0].wbs_code == "DM-01" and by_index[0].wbs_code_id == "u1"
    assert by_index[0].confidence == 0.95 and by_index[0].is_new is False
    assert by_index[1].wbs_code_id == "u2"  # null contract_value still matched


@pytest.mark.asyncio
async def test_wbs_empty_item_set_writes_empty_list():
    out = await run({}, items=[])
    assert out.output == [] and out.output_json == "[]"


@pytest.mark.asyncio
async def test_wbs_unknown_choice_becomes_residue_none(caplog):
    answers = {
        "item_0": {"choice": "ZZ-99", "confidence": 0.5, "probabilities": {}},
        "item_1": {"choice": NONE_OPTION, "confidence": 0.4, "probabilities": {}},
    }
    calls = []

    async def fake_llm():
        calls.append(1)
        res = [
            WbsMatch(item_index=0, wbs_code="NEW-00", is_new=True, confidence=0.7),
            WbsMatch(item_index=1, wbs_code="NEW-01", is_new=True, confidence=0.7),
        ]
        return MatchOutcome(matcher=MatcherName.llm, output=res, output_json="[]")

    with caplog.at_level("WARNING", logger="app.harness.matchers.jev"):
        out = await run(answers, fallback=fake_llm)
    assert len(calls) == 1  # one LLM call for the whole residue
    assert [m.wbs_code for m in out.output] == ["NEW-00", "NEW-01"]
    assert all(m.is_new for m in out.output)
    # Only the hallucinated choice warns; an intentional NONE is silent.
    warnings = [r for r in caplog.records if "out-of-criteria" in r.getMessage()]
    assert len(warnings) == 1 and "ZZ-99" in warnings[0].getMessage()
    # The grounding violation is counted; the intentional NONE is not.
    assert out.out_of_criteria == 1


@pytest.mark.asyncio
async def test_wbs_output_ordered_by_item_index():
    items = [ParsedClaimItem(item_index=i, description="d") for i in (5, 0, 1)]
    answers = {f"item_{i}": {"choice": "DM-01", "confidence": 0.9, "probabilities": {}} for i in (0, 1, 5)}
    out = await run(answers, items=items)
    assert [x.item_index for x in out.output] == [0, 1, 5]


@pytest.mark.asyncio
async def test_wbs_match_resolves_duplicate_code_to_chosen_id():
    dup = [
        Subcat(id="a1", code="DM-01", description="First", parent_code="DM", contract_sum=1.0),
        Subcat(id="b2", code="DM-01", description="Second", parent_code="DM", contract_sum=2.0),
    ]
    out = await run(
        {"item_0": {"choice": "DM-01#b2", "confidence": 0.9, "probabilities": {}}}, items=ITEMS[:1], subcats=dup
    )
    assert out.output[0].wbs_code == "DM-01" and out.output[0].wbs_code_id == "b2"
    assert out.output[0].wbs_description == "Second"


def test_wbs_duplicate_code_keys_by_id():
    subs = [
        Subcat(id="a1", code="DM-01", description="First", parent_code="DM", contract_sum=1.0),
        Subcat(id="b2", code="DM-01", description="Second", parent_code="DM", contract_sum=2.0),
        Subcat(id="c3", code="PL-03", description="Prelims", parent_code="PL", contract_sum=None),
    ]
    criteria, key_to_id = build_wbs_criteria(subs)
    assert "DM-01" not in key_to_id
    assert key_to_id["DM-01#a1"] == "a1" and key_to_id["DM-01#b2"] == "b2"
    assert key_to_id["PL-03"] == "c3"
    assert "$1.00" in criteria["DM-01#a1"] and "$2.00" in criteria["DM-01#b2"]
    assert NONE_OPTION in criteria
