"""Integration test: the engine's LLM_SINGLE phase writes validated structured output."""
import json
import uuid

import pytest
from pydantic_ai.models.test import TestModel

from app.harness import agent_runner
from app.harness.engine import HarnessEngine
from app.harness.models import HarnessDefinition, HarnessType, PhaseDefinition, PhaseType
from app.harness.schemas import WbsMatch
from app.repos import document_repo, harness_repo, user_repo
from tests.e2e.fixtures.gilmours_claim1 import PROJECT
from tests.e2e.helpers import get_auth_headers


def _llm_single_harness() -> HarnessDefinition:
    """A programmatic seed phase feeding one LLM_SINGLE phase (output: list[WbsMatch])."""

    async def seed(db, session_id, user_id, project_id, config):
        return {"line_items": [{"item_index": 0, "item_type": "contract_work"}]}

    return HarnessDefinition(
        harness_type=HarnessType.CLAIM_PARSE,
        display_name="LLM single test",
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
                name="WBS Categorisation",
                description="match wbs",
                phase_type=PhaseType.LLM_SINGLE,
                workspace_output="wbs_matches.json",
                workspace_inputs=["parsed_claim.json"],
                system_prompt_template="Categorise: $workspace_parsed_claim",
                output_schema=list[WbsMatch],
            ),
        ],
    )


async def _make_session(client, db_session):
    headers = await get_auth_headers(client)
    user = await user_repo.get_by_email(db_session, "qs@dmp.co.nz")
    proj_resp = await client.post("/api/v1/projects", json=PROJECT, headers=headers)
    project_id = uuid.UUID(proj_resp.json()["id"])
    doc = await document_repo.create_document(
        db_session, project_id, "c.pdf", "application/pdf", b"%PDF-1.4 x",
    )
    session = await harness_repo.create_session(
        db=db_session, user_id=user.id, project_id=project_id,
        harness_type=HarnessType.CLAIM_PARSE, document_id=doc.id,
        config={"document_id": str(doc.id)},
    )
    await db_session.commit()
    return session


@pytest.mark.asyncio
async def test_llm_single_writes_validated_json_array(client, db_session, monkeypatch):
    session = await _make_session(client, db_session)

    fake_model = TestModel(
        custom_output_args=[
            {
                "item_index": 0,
                "wbs_code_id": None,
                "wbs_code": "DM-01",
                "wbs_description": "Demolition",
                "parent_code": "DM",
                "is_new": True,
                "confidence": 0.9,
            }
        ]
    )
    monkeypatch.setattr(agent_runner, "build_model", lambda *a, **k: fake_model)

    engine = HarnessEngine(
        definition=_llm_single_harness(),
        session_id=session.id,
        user_id=session.user_id,
        project_id=session.project_id,
        db=db_session,
    )

    events = [event async for event in engine.run()]
    event_types = [e.type for e in events]

    assert "harness_error" not in event_types
    assert "usage" in event_types

    raw = await harness_repo.read_workspace_file(db_session, session.id, "wbs_matches.json")
    parsed = json.loads(raw)

    assert isinstance(parsed, list)
    assert parsed[0]["wbs_code"] == "DM-01"
    assert parsed[0]["item_index"] == 0
    # Fully validated: every schema field is present and typed.
    assert set(parsed[0]) == {
        "item_index", "wbs_code_id", "wbs_code", "wbs_description",
        "parent_code", "is_new", "confidence",
    }


@pytest.mark.asyncio
async def test_llm_single_without_output_schema_errors(client, db_session, monkeypatch):
    """An LLM_SINGLE phase missing an output_schema must fail loudly, not silently."""
    session = await _make_session(client, db_session)

    definition = _llm_single_harness()
    definition.phases[1].output_schema = None  # strip the schema

    # build_model must never be reached — guard fires first.
    def _boom(*a, **k):
        raise AssertionError("build_model should not be called without an output_schema")

    monkeypatch.setattr(agent_runner, "build_model", _boom)

    engine = HarnessEngine(
        definition=definition,
        session_id=session.id,
        user_id=session.user_id,
        project_id=session.project_id,
        db=db_session,
    )

    events = [event async for event in engine.run()]
    assert any(e.type == "harness_error" for e in events)
