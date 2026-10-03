import pytest
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.harness_session import HarnessSessionStatus
from app.models.claim_parse_flag import FlagType, FlagSeverity
from app.repos import harness_repo


@pytest.mark.asyncio
async def test_create_session(db_session: AsyncSession, test_user, test_project, test_document):
    session = await harness_repo.create_session(
        document_id=test_document.id,
        db=db_session,
        user_id=test_user.id,
        project_id=test_project.id,
        harness_type="claim_parse",
        config={"file_path": "/tmp/test.pdf"},
    )
    assert session.id is not None
    assert session.status == HarnessSessionStatus.pending
    assert session.current_phase == 0


@pytest.mark.asyncio
async def test_get_session(db_session: AsyncSession, test_user, test_project, test_document):
    session = await harness_repo.create_session(
        document_id=test_document.id,
        db=db_session,
        user_id=test_user.id,
        project_id=test_project.id,
        harness_type="claim_parse",
    )
    fetched = await harness_repo.get_session(db_session, session.id)
    assert fetched is not None
    assert fetched.id == session.id


@pytest.mark.asyncio
async def test_try_claim_running(db_session: AsyncSession, test_user, test_project, test_document):
    session = await harness_repo.create_session(
        document_id=test_document.id,
        db=db_session,
        user_id=test_user.id,
        project_id=test_project.id,
        harness_type="claim_parse",
    )
    assert await harness_repo.try_claim_running(db_session, session.id) is True
    # Second claim should fail
    assert await harness_repo.try_claim_running(db_session, session.id) is False


@pytest.mark.asyncio
async def test_update_phase(db_session: AsyncSession, test_user, test_project, test_document):
    session = await harness_repo.create_session(
        document_id=test_document.id,
        db=db_session,
        user_id=test_user.id,
        project_id=test_project.id,
        harness_type="claim_parse",
    )
    await harness_repo.try_claim_running(db_session, session.id)
    await harness_repo.update_phase(
        db=db_session,
        session_id=session.id,
        phase_key="0",
        result={"status": "completed", "summary": "Extracted 5 pages"},
        next_phase=1,
    )
    await db_session.refresh(session)
    assert session.current_phase == 1
    assert session.phase_results["0"]["status"] == "completed"


@pytest.mark.asyncio
async def test_write_and_read_workspace_file(db_session: AsyncSession, test_user, test_project, test_document):
    session = await harness_repo.create_session(
        document_id=test_document.id,
        db=db_session,
        user_id=test_user.id,
        project_id=test_project.id,
        harness_type="claim_parse",
    )
    await harness_repo.write_workspace_file(
        db=db_session,
        session_id=session.id,
        file_path="raw_extraction.json",
        content='{"pages": []}',
    )
    content = await harness_repo.read_workspace_file(db_session, session.id, "raw_extraction.json")
    assert content == '{"pages": []}'


@pytest.mark.asyncio
async def test_write_workspace_file_upsert(db_session: AsyncSession, test_user, test_project, test_document):
    session = await harness_repo.create_session(
        document_id=test_document.id,
        db=db_session,
        user_id=test_user.id,
        project_id=test_project.id,
        harness_type="claim_parse",
    )
    await harness_repo.write_workspace_file(db_session, session.id, "test.json", "v1")
    await harness_repo.write_workspace_file(db_session, session.id, "test.json", "v2")
    content = await harness_repo.read_workspace_file(db_session, session.id, "test.json")
    assert content == "v2"


@pytest.mark.asyncio
async def test_create_and_list_flags(db_session: AsyncSession, test_user, test_project, test_document):
    session = await harness_repo.create_session(
        document_id=test_document.id,
        db=db_session,
        user_id=test_user.id,
        project_id=test_project.id,
        harness_type="claim_parse",
    )
    await harness_repo.create_flag(
        db=db_session,
        session_id=session.id,
        flag_type=FlagType.over_claim,
        severity=FlagSeverity.warning,
        description="PTD exceeds contract value",
        line_item_ref="1001",
        expected_value=Decimal("100000"),
        actual_value=Decimal("120000"),
    )
    await harness_repo.create_flag(
        db=db_session,
        session_id=session.id,
        flag_type=FlagType.total_mismatch,
        severity=FlagSeverity.error,
        description="Section total mismatch",
    )
    flags = await harness_repo.list_flags_by_session(db_session, session.id)
    assert len(flags) == 2


@pytest.mark.asyncio
async def test_set_status(db_session: AsyncSession, test_user, test_project, test_document):
    session = await harness_repo.create_session(
        document_id=test_document.id,
        db=db_session,
        user_id=test_user.id,
        project_id=test_project.id,
        harness_type="claim_parse",
    )
    await harness_repo.set_status(db_session, session.id, HarnessSessionStatus.failed, error_message="Phase 1 failed")
    await db_session.refresh(session)
    assert session.status == HarnessSessionStatus.failed
    assert session.error_message == "Phase 1 failed"
