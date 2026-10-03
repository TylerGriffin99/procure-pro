# backend/tests/unit/test_jev_matcher_wbs.py
import json
import pytest
from app.harness.matchers.jev import JevMatcher, NONE_OPTION
from app.harness.matchers.data import Subcat
from app.harness.schemas import WbsMatch


class _Phase:
    name = "WBS Categorisation"
    output_schema = list[WbsMatch]


SUBCATS = [
    Subcat(id="u1", code="DM-01", description="Soft strip", parent_code="DM", contract_sum=12345.0),
    Subcat(id="u2", code="PL-03", description="Preliminaries", parent_code="PL", contract_sum=4000.0),
]
PARSED = {"line_items": [
    {"item_index": 0, "description": "Demolition", "contract_value": "12,345.00", "item_type": "contract_work"},
    {"item_index": 1, "description": "overhead", "contract_value": None, "item_type": "contract_work"},
    {"item_index": 2, "description": "a variation", "contract_value": "900", "item_type": "variation"},
]}


def _matcher(monkeypatch, answers):
    async def fake_read(db, sid, path):
        return json.dumps(PARSED)
    monkeypatch.setattr("app.harness.matchers.jev.harness_repo.read_workspace_file", fake_read)

    async def fake_subs(*, db, project_id):
        return SUBCATS
    monkeypatch.setattr("app.harness.matchers.jev.wbs_subcategories", fake_subs)

    async def fake_decide(*, state, questions, model, url, api_key, timeout=30.0):
        qid = next(iter(questions))            # one question per call
        return {"answers": {qid: answers[qid]}, "usage": {"input_tokens": 5, "output_tokens": 0, "cost": 0.0}}
    return JevMatcher(decide_fn=fake_decide)


@pytest.mark.asyncio
async def test_wbs_happy_path_maps_choice_to_code_and_id(monkeypatch):
    answers = {
        "item_0": {"choice": "DM-01", "confidence": 0.95, "probabilities": {"DM-01": 0.95}},
        "item_1": {"choice": "PL-03", "confidence": 0.8, "probabilities": {"PL-03": 0.8}},
    }
    out = await _matcher(monkeypatch, answers).match(phase_def=_Phase(), db=None, project_id="p", session_id="s")
    by_index = {m.item_index: m for m in out.output}
    assert set(by_index) == {0, 1}                       # only contract_work items (index 2 excluded)
    assert by_index[0].wbs_code == "DM-01" and by_index[0].wbs_code_id == "u1"
    assert by_index[0].confidence == 0.95 and by_index[0].is_new is False
    assert by_index[1].wbs_code_id == "u2"               # null contract_value still matched


@pytest.mark.asyncio
async def test_wbs_empty_item_set_writes_empty_list(monkeypatch):
    m = _matcher(monkeypatch, {})
    async def only_variation(db, sid, path):
        return json.dumps({"line_items": [PARSED["line_items"][2]]})
    monkeypatch.setattr("app.harness.matchers.jev.harness_repo.read_workspace_file", only_variation)
    out = await m.match(phase_def=_Phase(), db=None, project_id="p", session_id="s")
    assert out.output == [] and out.output_json == "[]"


@pytest.mark.asyncio
async def test_wbs_unknown_choice_becomes_residue_none(monkeypatch):
    # Jev returns a code not in criteria -> treated as none (is_new, no bogus wbs_code_id).
    answers = {"item_0": {"choice": "ZZ-99", "confidence": 0.5, "probabilities": {}},
               "item_1": {"choice": NONE_OPTION, "confidence": 0.5, "probabilities": {}}}
    out = await _matcher(monkeypatch, answers).match(phase_def=_Phase(), db=None, project_id="p", session_id="s")
    for m in out.output:
        assert m.wbs_code_id is None and m.is_new is True   # residue placeholder until Task 8 mints real codes


def test_wbs_duplicate_code_keys_by_id():
    from app.harness.matchers.jev import build_wbs_criteria
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
