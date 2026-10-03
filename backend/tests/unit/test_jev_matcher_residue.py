import json
import pytest
from pydantic import TypeAdapter
from app.harness.matchers.jev import JevMatcher, NONE_OPTION
from app.harness.matchers.data import Subcat
from app.harness.matchers.base import MatchOutcome
from app.harness.schemas import WbsMatch


class _Phase:
    name = "WBS Categorisation"
    output_schema = list[WbsMatch]


def _async(v):
    async def _a(*a, **k):
        return v
    return _a()


@pytest.mark.asyncio
async def test_none_and_lowconf_items_routed_to_llm(monkeypatch):
    parsed = {"line_items": [
        {"item_index": 0, "description": "x", "contract_value": "1", "item_type": "contract_work"},
        {"item_index": 1, "description": "y", "contract_value": "2", "item_type": "contract_work"},
    ]}
    monkeypatch.setattr("app.harness.matchers.jev.harness_repo.read_workspace_file",
                        lambda db, sid, path: _async(json.dumps(parsed)))
    monkeypatch.setattr("app.harness.matchers.jev.wbs_subcategories",
                        lambda **k: _async([Subcat("u1", "DM-01", "d", "DM", 1.0)]))

    async def fake_decide(*, state, questions, **k):
        qid = next(iter(questions))
        ans = {"item_0": {"choice": NONE_OPTION, "confidence": 0.9, "probabilities": {}},
               "item_1": {"choice": "DM-01", "confidence": 0.2, "probabilities": {"DM-01": 0.2}}}[qid]
        return {"answers": {qid: ans}, "usage": {}}

    llm_result = [WbsMatch(item_index=0, wbs_code="NEW-01", wbs_description="minted", parent_code="DM",
                           is_new=True, confidence=0.7),
                  WbsMatch(item_index=1, wbs_code="DM-01", wbs_code_id="u1", confidence=0.85)]

    async def fake_llm(*, phase_def, db, project_id, session_id):
        return MatchOutcome(output=llm_result,
                            output_json=TypeAdapter(list[WbsMatch]).dump_json(llm_result).decode())
    monkeypatch.setattr("app.harness.matchers.jev.run_llm_matches", fake_llm)

    import app.config
    monkeypatch.setattr(app.config.settings, "jev_confidence_floor", 0.6, raising=False)

    out = await JevMatcher(decide_fn=fake_decide).match(phase_def=_Phase(), db=None, project_id="p", session_id="s")
    by_index = {m.item_index: m for m in out.output}
    assert by_index[0].wbs_code == "NEW-01" and by_index[0].is_new is True
    assert by_index[1].wbs_code_id == "u1" and by_index[1].confidence == 0.85
