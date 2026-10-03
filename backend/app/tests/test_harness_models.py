import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.harness_session import HarnessSession, HarnessSessionStatus
from app.models.harness_workspace_file import HarnessWorkspaceFile
from app.models.claim_parse_flag import ClaimParseFlag, FlagType, FlagSeverity


@pytest.mark.asyncio
async def test_create_harness_session(db_session: AsyncSession, test_user, test_project, test_document):
    session = HarnessSession(
        user_id=test_user.id,
        project_id=test_project.id,
        harness_type="claim_parse",
        document_id=test_document.id,
        config={"document_id": str(test_document.id)},
    )
    db_session.add(session)
    await db_session.flush()

    assert session.id is not None
    assert session.status == HarnessSessionStatus.pending
    assert session.current_phase == 0
    assert session.phase_results == {}


@pytest.mark.asyncio
async def test_create_workspace_file(db_session: AsyncSession, test_user, test_project, test_document):
    hs = HarnessSession(
        user_id=test_user.id,
        project_id=test_project.id,
        harness_type="claim_parse",
        document_id=test_document.id,
    )
    db_session.add(hs)
    await db_session.flush()

    wf = HarnessWorkspaceFile(
        session_id=hs.id,
        file_path="raw_extraction.json",
        content='{"pages": []}',
    )
    db_session.add(wf)
    await db_session.flush()

    assert wf.id is not None
    assert wf.internal is False


@pytest.mark.asyncio
async def test_create_claim_parse_flag(db_session: AsyncSession, test_user, test_project, test_document):
    hs = HarnessSession(
        user_id=test_user.id,
        project_id=test_project.id,
        harness_type="claim_parse",
        document_id=test_document.id,
    )
    db_session.add(hs)
    await db_session.flush()

    flag = ClaimParseFlag(
        session_id=hs.id,
        flag_type=FlagType.over_claim,
        severity=FlagSeverity.warning,
        line_item_ref="1001",
        description="PTD exceeds contract value",
        expected_value=100000,
        actual_value=120000,
    )
    db_session.add(flag)
    await db_session.flush()

    assert flag.id is not None
    assert flag.resolved is False
