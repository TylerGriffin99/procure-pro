import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.repos import harness_repo
from app.models.claim import Claim


@pytest.mark.asyncio
async def test_get_session_by_claim(db_session: AsyncSession, test_user, test_project, test_document):
    # Create a real claim so the FK constraint is satisfied
    claim = Claim(
        project_id=test_project.id,
        claim_number=1,
        created_by=test_user.id,
    )
    db_session.add(claim)
    await db_session.flush()

    session = await harness_repo.create_session(
        document_id=test_document.id,
        db=db_session, user_id=test_user.id,
        project_id=test_project.id, harness_type="claim_parse",
    )
    await harness_repo.set_claim_id(db_session, session.id, claim.id)
    await db_session.flush()

    found = await harness_repo.get_session_by_claim(db_session, claim.id)
    assert found is not None
    assert found.id == session.id
    assert found.document_id == test_document.id


@pytest.mark.asyncio
async def test_get_session_by_claim_not_found(db_session: AsyncSession):
    found = await harness_repo.get_session_by_claim(db_session, uuid.uuid4())
    assert found is None
