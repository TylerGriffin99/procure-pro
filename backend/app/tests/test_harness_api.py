import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.repos import harness_repo


@pytest.mark.asyncio
async def test_get_session_not_found(client: AsyncClient, auth_headers):
    import uuid
    resp = await client.get(f"/api/harness/sessions/{uuid.uuid4()}", headers=auth_headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_session(client: AsyncClient, db_session: AsyncSession, test_user, test_project, auth_headers, test_document):
    session = await harness_repo.create_session(
        document_id=test_document.id,
        db=db_session, user_id=test_user.id,
        project_id=test_project.id, harness_type="claim_parse",
    )
    await db_session.commit()
    resp = await client.get(f"/api/harness/sessions/{session.id}", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "pending"
    assert data["harness_type"] == "claim_parse"


@pytest.mark.asyncio
async def test_cancel_session(client: AsyncClient, db_session: AsyncSession, test_user, test_project, auth_headers, test_document):
    session = await harness_repo.create_session(
        document_id=test_document.id,
        db=db_session, user_id=test_user.id,
        project_id=test_project.id, harness_type="claim_parse",
    )
    await db_session.commit()
    resp = await client.post(f"/api/harness/sessions/{session.id}/cancel", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "failed"
