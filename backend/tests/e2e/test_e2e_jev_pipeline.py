"""
E2E: full CLAIM_PARSE pipeline under matcher=jev with a FAKE decisions endpoint.

Drives the real harness (phases 0-6) on Gilmours Claim 1. Phases 4 & 5 are
declared matcher="jev"; the HTTP decisions call is replaced by a deterministic
in-process fake, so no network and no real LLM/credentials are needed
(Gilmours is WBPRO, so phase 2 is deterministic too). The LLM residue fallback
is booby-trapped so any accidental LLM call fails the test loudly.

Requires: Docker (testcontainers Postgres) or E2E_DATABASE_URL, and
claim/Gilmours/claims/Gilmours Central_Progress Claim No. 1.pdf.
"""
import difflib
import json
import re
from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy import select

import app.harness.matchers.jev as jev_module
from app.config import settings
from app.models.harness_session import HarnessSession
from app.repos import harness_repo
from tests.e2e.fixtures.gilmours_claim1 import (
    EXPECTED_CLAIM_ITEM_COUNT,
    EXPECTED_CLAIM_LINE_ITEMS,
    PROJECT,
)
from tests.e2e.helpers import get_auth_headers, upload_claim_deep_mode

CLAIM_1_PATH = (
    Path(__file__).parent.parent.parent.parent
    / "claim" / "Gilmours" / "claims" / "Gilmours Central_Progress Claim No. 1.pdf"
)

EXPECTED_CONTRACT_WORK = [i for i in EXPECTED_CLAIM_LINE_ITEMS if i["item_type"] == "contract_work"]
RECLASSIFIED_PS = [i for i in EXPECTED_CLAIM_LINE_ITEMS if i["item_type"] == "provisional_sum"]
_SUM_RE = re.compile(r"contract sum \$([\d,]+\.\d\d)")


@pytest.fixture
def fake_jev(monkeypatch):
    """Deterministic stand-in for the Jev decisions endpoint. Returns the call log."""
    calls: list[dict] = []

    async def fake_call_decisions(*, state, questions, model, url, api_key, timeout=30.0):
        (qid, q), = questions.items()
        criteria = {k: v for k, v in q["criteria"].items() if k != jev_module.NONE_OPTION}
        choice = jev_module.NONE_OPTION
        if criteria:
            value = state.get("contract_value")
            exact = [
                k for k, text in criteria.items()
                if (m := _SUM_RE.search(text)) and value is not None
                and abs(float(m.group(1).replace(",", "")) - float(value)) < 0.01
            ]
            pool = exact or list(criteria)
            # Exact contract-sum match wins; otherwise nearest description.
            choice = max(pool, key=lambda k: difflib.SequenceMatcher(
                None, state["description"].lower(), criteria[k].lower()).ratio())
        calls.append({"qid": qid, "choice": choice, "api_key": api_key})
        return {"answers": {qid: {"choice": choice, "confidence": 0.95}},
                "usage": {"input_tokens": 1}}

    async def llm_must_not_run(*a, **kw):
        raise AssertionError("LLM residue fallback invoked; jev fake should resolve every item")

    monkeypatch.setattr(jev_module, "call_decisions", fake_call_decisions)
    monkeypatch.setattr(jev_module, "run_llm_matches", llm_must_not_run)
    monkeypatch.setattr(settings, "open_router_api_key", "test-key")
    return calls


@pytest.mark.skipif(not CLAIM_1_PATH.exists(), reason="Sample PDF not available")
@pytest.mark.asyncio
async def test_gilmours_claim1_pipeline_under_jev(client: AsyncClient, db_session, fake_jev):
    headers = await get_auth_headers(client)
    project_resp = await client.post("/api/projects", json=PROJECT, headers=headers)
    assert project_resp.status_code == 201, project_resp.text
    project_id = project_resp.json()["id"]

    claim_id = await upload_claim_deep_mode(client, project_id, CLAIM_1_PATH, headers)

    # Phases 4 & 5 went through the (fake) Jev endpoint once per matched item (29 WBS + 3 VPS).
    assert len(fake_jev) == EXPECTED_CLAIM_ITEM_COUNT
    assert {c["api_key"] for c in fake_jev} == {"test-key"}

    # Workspace: one WBS match per contract-work item, all resolved to existing codes.
    session_id = (await db_session.execute(select(HarnessSession.id))).scalars().one()
    wbs = json.loads(await harness_repo.read_workspace_file(db_session, session_id, "wbs_matches.json"))
    parsed = json.loads(await harness_repo.read_workspace_file(db_session, session_id, "parsed_claim.json"))
    parsed_cw = [i for i in parsed["line_items"] if i["item_type"] == "contract_work"]
    parsed_vps = [i for i in parsed["line_items"] if i["item_type"] != "contract_work"]
    # WBPRO parse tags the 4 "Provisional sum - ..." rows as contract_work; create_records
    # reclassifies them to provisional_sum AFTER phase 4, so Jev matches 25 + 4 = 29 items.
    assert len(parsed_cw) == len(EXPECTED_CONTRACT_WORK) + len(RECLASSIFIED_PS) == 29
    assert len(wbs) == len(parsed_cw)  # one match per parsed contract-work item
    assert {m["item_index"] for m in wbs} == {i["item_index"] for i in parsed_cw}
    assert all(not m["is_new"] and m["wbs_code_id"] for m in wbs)
    vps = json.loads(await harness_repo.read_workspace_file(db_session, session_id, "vps_matches.json"))
    assert len(vps) == len(parsed_vps) == 3  # the 3 variations
    assert all(m["matched_id"] is None for m in vps)  # no pre-existing records -> new

    # Claim record: same item count as the LLM-path e2e.
    claim = (await client.get(f"/api/projects/{project_id}/claims/{claim_id}", headers=headers)).json()
    assert len(claim["line_items"]) == EXPECTED_CLAIM_ITEM_COUNT
    n_cw = sum(1 for li in claim["line_items"] if li["item_type"] == "contract_work")
    assert n_cw == len(EXPECTED_CONTRACT_WORK)
    assert n_cw == len(wbs) - len(RECLASSIFIED_PS)  # 4 PS rows reclassified out of contract_work

    # Assessment record created. create_records emits one history row per existing
    # PS/variation record plus one row per claim line item, so we assert on the rows
    # linked to this claim's items (the history-row count is matcher-independent).
    assessment = await _assessment(client, project_id, claim_id, headers)
    assert assessment["id"]
    assert len(assessment["line_items"]) >= 28
    linked_vars = [v for v in assessment["variation_items"] if v["claim_line_item_id"]]
    linked_ps = [p for p in assessment["provisional_sum_items"] if p["claim_line_item_id"]]
    assert len(linked_vars) == 3
    assert len(linked_ps) == len(RECLASSIFIED_PS) == 4


async def _assessment(client, project_id, claim_id, headers) -> dict:
    resp = await client.get(
        f"/api/projects/{project_id}/assessments/by-claim/{claim_id}", headers=headers)
    assert resp.status_code == 200, resp.text
    return resp.json()
