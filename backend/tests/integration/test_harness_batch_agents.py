"""Integration test: LLM_BATCH_AGENTS phases dispatch through the selected matcher."""
import json
import logging

import pytest
from pydantic import TypeAdapter

from app.config import settings
from app.harness.engine import HarnessEngine
from app.harness.schemas import MatchOutcome
from app.harness.models import HarnessDefinition, HarnessType, PhaseDefinition, PhaseType
from app.harness.schemas import WbsMatch
from app.repos import harness_repo
from tests.integration.test_harness_llm_single import _make_session


def _batch_harness(matcher: str | None) -> HarnessDefinition:
    async def seed(db, session_id, user_id, project_id, config):
        return {"line_items": [{"item_index": 0, "item_type": "contract_work"}]}

    return HarnessDefinition(
        harness_type=HarnessType.CLAIM_PARSE,
        display_name="Batch agents test",
        description="test",
        prerequisites=None,
        phases=[
            PhaseDefinition(
                name="Seed",
                description="seed parsed_claim",
                phase_type=PhaseType.PROGRAMMATIC,
                workspace_output="parsed_claim.json",
                executor=seed,
            ),
            PhaseDefinition(
                name="WBS Matching",
                description="match wbs",
                phase_type=PhaseType.LLM_BATCH_AGENTS,
                workspace_output="wbs_matches.json",
                workspace_inputs=["parsed_claim.json"],
                output_schema=list[WbsMatch],
                matcher=matcher,
            ),
        ],
    )


def _patch_llm_match(monkeypatch):
    sample = [WbsMatch(item_index=0, wbs_code="DM-01", confidence=0.9)]

    async def fake_match(self, *, phase_def, db, project_id, session_id):
        return MatchOutcome(
            output=sample,
            output_json=TypeAdapter(list[WbsMatch]).dump_json(sample).decode(),
            input_tokens=3,
            output_tokens=4,
        )

    monkeypatch.setattr("app.harness.matchers.llm.LlmMatcher.match", fake_match)


async def _run(client, db_session, matcher):
    session = await _make_session(client, db_session)
    engine = HarnessEngine(
        definition=_batch_harness(matcher),
        session_id=session.id,
        user_id=session.user_id,
        project_id=session.project_id,
        db=db_session,
    )
    events = [event async for event in engine.run()]
    raw = await harness_repo.read_workspace_file(db_session, session.id, "wbs_matches.json")
    return events, raw


@pytest.mark.asyncio
async def test_batch_agents_phase_writes_workspace_via_llm_matcher(client, db_session, monkeypatch):
    _patch_llm_match(monkeypatch)

    events, raw = await _run(client, db_session, "llm")

    types = [e.type for e in events]
    assert "harness_error" not in types
    assert "usage" in types
    result = next(e for e in events if e.type == "harness_phase_result" and e.phase_name == "WBS Matching")
    assert "fell_back=0/1" in result.detail and "residue=0/1" in result.detail
    parsed = json.loads(raw)
    assert parsed[0]["wbs_code"] == "DM-01"


@pytest.mark.asyncio
async def test_unconfigured_jev_warns_and_falls_back_to_llm(client, db_session, monkeypatch, caplog):
    _patch_llm_match(monkeypatch)
    monkeypatch.setattr(settings, "open_router_api_key", "")

    with caplog.at_level(logging.WARNING, logger="app.harness.engine"):
        events, raw = await _run(client, db_session, "jev")

    assert "harness_error" not in [e.type for e in events]
    assert json.loads(raw)[0]["wbs_code"] == "DM-01"
    assert any("falling back to matcher=llm" in r.getMessage() for r in caplog.records)


@pytest.mark.asyncio
async def test_phase4_jev_end_to_end_with_fake_decisions(client, db_session, monkeypatch):
    """Phase 4 as LLM_BATCH_AGENTS/jev yields a valid list[WbsMatch] via a fake decisions endpoint."""
    from app.harness.schemas import Subcat

    monkeypatch.setattr(settings, "open_router_api_key", "test-key")

    async def fake_subs(*, db, project_id):
        return [Subcat(id="u1", code="DM-01", description="Soft strip", parent_code="DM", contract_sum=100.0)]

    monkeypatch.setattr("app.harness.matchers.jev.wbs_subcategories", fake_subs)

    async def fake_decide(*, state, questions, model, url, api_key, timeout=30.0):
        qid = next(iter(questions))
        return {
            "answers": {qid: {"choice": "DM-01", "confidence": 0.95, "probabilities": {"DM-01": 0.95}}},
            "usage": {"input_tokens": 3},
        }

    monkeypatch.setattr("app.harness.matchers.jev.call_decisions", fake_decide)

    events, raw = await _run(client, db_session, "jev")

    assert "harness_error" not in [e.type for e in events]
    parsed = TypeAdapter(list[WbsMatch]).validate_json(raw)
    assert len(parsed) == 1
    assert parsed[0].wbs_code == "DM-01" and parsed[0].wbs_code_id == "u1" and not parsed[0].is_new
