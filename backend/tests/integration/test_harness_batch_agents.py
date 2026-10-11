"""Integration test: LLM_BATCH_AGENTS phases dispatch through the injected matcher table."""

import functools
import json
import logging

import pytest
from pydantic import TypeAdapter
from pydantic_ai.models.test import TestModel

from app.clients.llm_client import LlmClient
from app.config import Settings
from app.constants import LlmProvider, MatcherName, WBSLevel
from app.harness.engine import HarnessEngine
from app.harness.factory import build_matchers
from app.harness.matchers.jev import match_with_jev
from app.harness.models import HarnessDefinition, HarnessType, PhaseDefinition, PhaseType
from app.harness.schemas import JevTuning, MatchOutcome, ParsedClaim, ParsedClaimItem, WbsMatch
from app.repos import harness_repo, wbs_code_repo
from tests.integration.test_harness_llm_single import _make_session
from tests.unit.jev_fakes import fake_client

LLM = LlmClient(provider=LlmProvider.openai, model_name="m", api_key="k", model=TestModel())
SAMPLE = [WbsMatch(item_index=0, wbs_code="DM-01", confidence=0.9)]


def _batch_harness(matcher: str | None) -> HarnessDefinition:
    async def seed(**_):
        return ParsedClaim(line_items=[ParsedClaimItem(item_index=0)])

    return HarnessDefinition(
        harness_type=HarnessType.CLAIM_PARSE,
        display_name="Batch agents test",
        description="test",
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


async def fake_llm_matcher(phase):
    return MatchOutcome(
        matcher=MatcherName.llm,
        output=SAMPLE,
        output_json=TypeAdapter(list[WbsMatch]).dump_json(SAMPLE).decode(),
        input_tokens=3,
        output_tokens=4,
    )


async def _run(session, db_session, matcher, matchers):
    engine = HarnessEngine(
        definition=_batch_harness(matcher),
        session_id=session.id,
        user_id=session.user_id,
        project_id=session.project_id,
        db=db_session,
        llm=LLM,
        matchers=matchers,
        default_matcher=MatcherName.llm,
    )
    events = [event async for event in engine.run()]
    raw = await harness_repo.read_workspace_file(db_session, session.id, "wbs_matches.json")
    return events, raw


@pytest.mark.asyncio
async def test_batch_agents_phase_writes_workspace_via_llm_matcher(client, db_session):
    session = await _make_session(client, db_session)
    events, raw = await _run(session, db_session, "llm", {MatcherName.llm: fake_llm_matcher})

    types = [e.type for e in events]
    assert "harness_error" not in types
    assert "usage" in types
    result = next(e for e in events if e.type == "harness_phase_result" and e.phase_name == "WBS Matching")
    assert result.detail == "matcher=llm fell_back=0/1 residue=0/1"
    parsed = json.loads(raw)
    assert parsed[0]["wbs_code"] == "DM-01"


@pytest.mark.asyncio
async def test_unconfigured_jev_warns_and_falls_back_to_llm(client, db_session, caplog):
    session = await _make_session(client, db_session)
    settings = Settings(
        secret_key="k", llm_provider="openai", llm_model="m", openai_api_key="k", open_router_api_key=""
    )
    model = TestModel(custom_output_args=[s.model_dump() for s in SAMPLE])
    llm = LlmClient(provider=LlmProvider.openai, model_name="m", api_key="k", model=model)

    with caplog.at_level(logging.WARNING, logger="app.harness.factory"):
        events, raw = await _run(session, db_session, "jev", build_matchers(settings, llm=llm))

    assert "harness_error" not in [e.type for e in events]
    assert json.loads(raw)[0]["wbs_code"] == "DM-01"
    result = next(e for e in events if e.type == "harness_phase_result" and e.phase_name == "WBS Matching")
    assert result.detail.startswith("matcher=llm ")
    assert any("matcher=jev phases will run on the LLM matcher" in r.getMessage() for r in caplog.records)


@pytest.mark.asyncio
async def test_phase4_jev_end_to_end_with_fake_decisions(client, db_session):
    """Phase 4 as LLM_BATCH_AGENTS/jev yields a valid list[WbsMatch] via a fake decisions endpoint."""
    session = await _make_session(client, db_session)
    subcat = await wbs_code_repo.create(
        db_session,
        project_id=session.project_id,
        code="ZZ-01",
        description="Soft strip",
        level=WBSLevel.subcategory,
        contract_sum=100,
        created_by=session.user_id,
    )
    await db_session.commit()

    async def fake_decide(*, state, questions, model, url, api_key, timeout=30.0):
        qid = next(iter(questions))
        return {
            "answers": {qid: {"choice": "ZZ-01", "confidence": 0.95, "probabilities": {"ZZ-01": 0.95}}},
            "usage": {"input_tokens": 3},
        }

    jev = functools.partial(
        match_with_jev,
        client=fake_client(fake_decide),
        llm=LLM,
        tuning=JevTuning(confidence_floor=0.6, max_concurrency=2),
    )
    events, raw = await _run(session, db_session, "jev", {MatcherName.jev: jev})

    assert "harness_error" not in [e.type for e in events]
    parsed = TypeAdapter(list[WbsMatch]).validate_json(raw)
    assert len(parsed) == 1
    assert parsed[0].wbs_code == "ZZ-01" and parsed[0].wbs_code_id == str(subcat.id) and not parsed[0].is_new
