import json
import pytest
from typing import cast
from unittest.mock import AsyncMock, patch

from sqlalchemy.ext.asyncio import AsyncSession

from app.harness.engine import HarnessEngine
from app.harness.models import HarnessDefinition, HarnessPrerequisites, PhaseDefinition, PhaseType
from app.harness.registry import HarnessRegistry
from app.models.harness_session import HarnessSessionStatus
from app.repos import harness_repo
from app.harness.models import HarnessType


# Test-only harness ids that are deliberately not members of HarnessType.
TEST_HARNESS = cast(HarnessType, "test_harness")
FAIL_TEST = cast(HarnessType, "fail_test")


def _make_test_harness() -> HarnessDefinition:
    """Two-phase harness: one programmatic, one LLM_SINGLE (mocked)."""

    async def phase0_executor(db, session_id, user_id, project_id, config):
        return {"pages": [{"page_num": 1, "text": "test content"}]}

    return HarnessDefinition(
        harness_type=TEST_HARNESS,
        display_name="Test Harness",
        description="For testing",
        prerequisites=None,
        phases=[
            PhaseDefinition(
                name="extract",
                description="Extract raw data",
                phase_type=PhaseType.PROGRAMMATIC,
                workspace_output="raw_extraction.json",
                executor=phase0_executor,
            ),
        ],
    )


@pytest.mark.asyncio
async def test_engine_runs_programmatic_phase(db_session: AsyncSession, test_user, test_project, test_document):
    harness_def = _make_test_harness()

    session = await harness_repo.create_session(
        document_id=test_document.id,
        db=db_session,
        user_id=test_user.id,
        project_id=test_project.id,
        harness_type=TEST_HARNESS,
    )

    engine = HarnessEngine(
        definition=harness_def,
        session_id=session.id,
        user_id=test_user.id,
        project_id=test_project.id,
        db=db_session,
    )

    events = []
    async for event in engine.run():
        events.append(event)

    event_types = [e.type for e in events]
    assert "harness_start" in event_types
    assert "harness_phase_start" in event_types
    assert "harness_phase_result" in event_types
    assert "harness_complete" in event_types

    # Verify workspace file was written
    content = await harness_repo.read_workspace_file(db_session, session.id, "raw_extraction.json")
    assert content is not None
    assert "test content" in content


@pytest.mark.asyncio
async def test_engine_sets_failed_on_error(db_session: AsyncSession, test_user, test_project, test_document):
    async def failing_executor(db, session_id, user_id, project_id, config):
        raise RuntimeError("PDF is corrupted")

    harness_def = HarnessDefinition(
        harness_type=FAIL_TEST,
        display_name="Fail Test",
        description="Test failure",
        prerequisites=None,
        phases=[
            PhaseDefinition(
                name="broken",
                description="Will fail",
                phase_type=PhaseType.PROGRAMMATIC,
                workspace_output="never.json",
                executor=failing_executor,
            ),
        ],
    )

    session = await harness_repo.create_session(
        document_id=test_document.id,
        db=db_session, user_id=test_user.id,
        project_id=test_project.id, harness_type=FAIL_TEST,
    )

    engine = HarnessEngine(
        definition=harness_def, session_id=session.id,
        user_id=test_user.id, project_id=test_project.id, db=db_session,
    )

    events = []
    async for event in engine.run():
        events.append(event)

    assert any(e.type == "harness_error" for e in events)
    await db_session.refresh(session)
    assert session.status == HarnessSessionStatus.failed


@pytest.mark.asyncio
async def test_registry():
    registry = HarnessRegistry()
    defn = _make_test_harness()
    registry.register(defn)
    assert registry.get(TEST_HARNESS) is defn
    assert registry.get(cast(HarnessType, "nonexistent")) is None
    assert len(registry.list_types()) == 1
