"""The engine dispatches each PhaseType to its runner through collaborators injected in the constructor."""

import json

import pytest
from pydantic_ai.models.test import TestModel

from app.clients.llm_client import LlmClient
from app.constants import HarnessSessionStatus, LlmProvider, MatcherName
from app.harness.engine import HarnessEngine
from app.harness.models import HarnessDefinition, HarnessType, PhaseDefinition, PhaseType
from app.harness.schemas import MatchOutcome, ParsedClaim, ParsedClaimItem, VpsMatch, WbsMatch
from app.repos import harness_repo
from tests.integration.test_harness_llm_single import _make_session

WBS = [WbsMatch(item_index=0, wbs_code="DM-01", confidence=0.9)]


def definition(*phases: PhaseDefinition) -> HarnessDefinition:
    return HarnessDefinition(
        harness_type=HarnessType.CLAIM_PARSE, display_name="t", description="t", phases=list(phases)
    )


def programmatic(name: str, executor) -> PhaseDefinition:
    return PhaseDefinition(
        name=name,
        description=name,
        phase_type=PhaseType.PROGRAMMATIC,
        workspace_output=f"{name}.json",
        executor=executor,
    )


def engine_for(session, db, phases, *, matchers=None, model=None):
    return HarnessEngine(
        definition=definition(*phases),
        session_id=session.id,
        user_id=session.user_id,
        project_id=session.project_id,
        db=db,
        llm=LlmClient(provider=LlmProvider.openai, model_name="m", api_key="k", model=model or TestModel()),
        matchers=matchers or {},
        default_matcher=MatcherName.jev,
    )


@pytest.mark.asyncio
async def test_each_phase_type_reaches_its_runner(client, db_session):
    session = await _make_session(client, db_session)
    seen = {}

    async def seed(**kwargs):
        seen["executor_llm"] = kwargs["llm"]
        return ParsedClaim(line_items=[ParsedClaimItem(item_index=0)])

    async def jev_matcher(phase):
        seen["matcher_phase"] = phase.phase_def.name
        return MatchOutcome(matcher=MatcherName.jev, output=[], output_json="[]", input_tokens=2, output_tokens=1)

    model = TestModel(custom_output_args=[m.model_dump() for m in WBS])
    phases = [
        programmatic("seed", seed),
        PhaseDefinition(
            name="single",
            description="llm",
            phase_type=PhaseType.LLM_SINGLE,
            workspace_output="single.json",
            system_prompt_template="go",
            output_schema=list[WbsMatch],
        ),
        PhaseDefinition(
            name="match",
            description="matcher",
            phase_type=PhaseType.LLM_BATCH_AGENTS,
            workspace_output="match.json",
            output_schema=list[VpsMatch],
        ),
    ]
    engine = engine_for(session, db_session, phases, matchers={MatcherName.jev: jev_matcher}, model=model)

    events = [e async for e in engine.run()]

    assert [e.type for e in events] == [
        "harness_start",
        "harness_phase_start",
        "harness_phase_result",
        "harness_phase_start",
        "usage",
        "harness_phase_result",
        "harness_phase_start",
        "usage",
        "harness_phase_result",
        "harness_complete",
    ]
    assert seen == {"executor_llm": engine.llm, "matcher_phase": "match"}
    assert json.loads(await harness_repo.read_workspace_file(db_session, session.id, "seed.json")) == {
        "metadata": {"claim_number": "", "period_from": "", "period_to": "", "payment_due": ""},
        "line_items": [{"item_index": 0, "ref_code": "", "description": "", "item_type": "contract_work"}],
        "summary": {},
    }
    assert json.loads(await harness_repo.read_workspace_file(db_session, session.id, "single.json"))[0]["wbs_code"] == (
        "DM-01"
    )
    session_id = session.id
    db_session.expire_all()
    stored = await harness_repo.get_session(db_session, session_id)
    assert stored.status == HarnessSessionStatus.completed
    assert stored.current_phase == 3
    assert stored.phase_results["2"]["summary"] == "Produced match.json (matcher=jev fell_back=0/0 residue=0/0)"


@pytest.mark.asyncio
async def test_session_cancelled_between_phases_stops_and_never_completes(client, db_session):
    session = await _make_session(client, db_session)
    ran = []

    async def cancel_during_phase(*, db, session_id, **_):
        ran.append("first")
        await harness_repo.set_status(db, session_id, HarnessSessionStatus.failed, error_message="Cancelled by user")
        return ParsedClaim(line_items=[])

    async def never(**_):
        ran.append("second")
        return ParsedClaim(line_items=[])

    engine = engine_for(
        session, db_session, [programmatic("first", cancel_during_phase), programmatic("second", never)]
    )

    events = [e async for e in engine.run()]

    assert ran == ["first"]
    assert [e.type for e in events][-1] == "harness_error"
    assert events[-1].error == "Cancelled"
    assert "harness_complete" not in [e.type for e in events]
    session_id = session.id
    db_session.expire_all()
    stored = await harness_repo.get_session(db_session, session_id)
    assert (stored.status, stored.error_message) == (HarnessSessionStatus.failed, "Cancelled by user")
