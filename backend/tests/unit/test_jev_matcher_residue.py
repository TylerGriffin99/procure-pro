import pytest
from pydantic import TypeAdapter

from app.constants import MatcherName
from app.harness.matchers.jev import NONE_OPTION, match_wbs
from app.harness.schemas import JevTuning, MatchOutcome, ParsedClaimItem, Subcat, WbsMatch
from tests.unit.jev_fakes import fake_client

SUBCATS = [Subcat(id="u1", code="DM-01", description="d", parent_code="DM", contract_sum=1.0)]
TUNING = JevTuning(confidence_floor=0.6, max_concurrency=4)


def items(*indexes):
    return [ParsedClaimItem(item_index=i, description="x", contract_value="1") for i in indexes]


def llm_returning(result, **usage):
    async def fake_llm():
        return MatchOutcome(
            matcher=MatcherName.llm,
            output=result,
            output_json=TypeAdapter(list[WbsMatch]).dump_json(result).decode(),
            **usage,
        )

    return fake_llm


async def run(decide, item_list, fallback):
    return await match_wbs(
        item_list,
        SUBCATS,
        phase_name="WBS Categorisation",
        client=fake_client(decide),
        tuning=TUNING,
        fallback=fallback,
    )


@pytest.mark.asyncio
async def test_none_and_lowconf_items_routed_to_llm():
    async def fake_decide(*, state, questions, **k):
        qid = next(iter(questions))
        ans = {
            "item_0": {"choice": NONE_OPTION, "confidence": 0.9, "probabilities": {}},
            "item_1": {"choice": "DM-01", "confidence": 0.2, "probabilities": {"DM-01": 0.2}},
        }[qid]
        return {"answers": {qid: ans}, "usage": {}}

    llm_result = [
        WbsMatch(
            item_index=0, wbs_code="NEW-01", wbs_description="minted", parent_code="DM", is_new=True, confidence=0.7
        ),
        WbsMatch(item_index=1, wbs_code="DM-01", wbs_code_id="u1", confidence=0.85),
    ]

    out = await run(fake_decide, items(0, 1), llm_returning(llm_result))
    by_index = {m.item_index: m for m in out.output}
    assert by_index[0].wbs_code == "NEW-01" and by_index[0].is_new is True
    assert by_index[1].wbs_code_id == "u1" and by_index[1].confidence == 0.85


@pytest.mark.asyncio
async def test_unresolved_residue_warns_and_keeps_placeholder(caplog):
    async def fake_decide(*, state, questions, **k):
        qid = next(iter(questions))
        return {"answers": {qid: {"choice": NONE_OPTION, "confidence": 0.9, "probabilities": {}}}, "usage": {}}

    fallback = llm_returning([WbsMatch(item_index=0, wbs_code="NEW-01", is_new=True, confidence=0.7)])
    with caplog.at_level("WARNING", logger="app.harness.matchers.jev"):
        out = await run(fake_decide, items(0, 1), fallback)
    by_index = {m.item_index: m for m in out.output}
    assert by_index[0].wbs_code == "NEW-01"  # replaced by LLM
    assert by_index[1].wbs_code == "" and by_index[1].wbs_code_id is None  # placeholder kept
    warns = [r.getMessage() for r in caplog.records if "not resolved by LLM" in r.getMessage()]
    assert len(warns) == 1 and "[1]" in warns[0]


@pytest.mark.asyncio
async def test_residue_tokens_and_counts_accumulate():
    async def fake_decide(*, state, questions, **k):
        qid = next(iter(questions))
        return {
            "answers": {qid: {"choice": NONE_OPTION, "confidence": 0.9, "probabilities": {}}},
            "usage": {"input_tokens": 7},
        }

    llm_result = [WbsMatch(item_index=0, wbs_code="NEW-01", parent_code="DM", is_new=True, confidence=0.7)]
    out = await run(fake_decide, items(0), llm_returning(llm_result, input_tokens=100, output_tokens=40))
    assert out.input_tokens == 107 and out.output_tokens == 40
    assert out.residue == 1 and out.fell_back == 0
