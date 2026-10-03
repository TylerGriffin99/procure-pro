import uuid

import pytest

from app.harness.models import HarnessType
from app.models.harness_session import HarnessSessionStatus
from app.repos import document_repo, harness_repo, user_repo
from tests.e2e.fixtures.gilmours_claim1 import PROJECT
from tests.e2e.helpers import get_auth_headers


async def _make_session(client, db_session, status):
    headers = await get_auth_headers(client)
    user = await user_repo.get_by_email(db_session, "qs@dmp.co.nz")
    proj_resp = await client.post("/api/projects", json=PROJECT, headers=headers)
    project_id = uuid.UUID(proj_resp.json()["id"])
    doc = await document_repo.create_document(
        db_session, project_id, "c.pdf", "application/pdf", b"%PDF-1.4 x",
    )
    session = await harness_repo.create_session(
        db=db_session, user_id=user.id, project_id=project_id,
        harness_type=HarnessType.CLAIM_PARSE, document_id=doc.id,
        config={"document_id": str(doc.id)},
    )
    await harness_repo.set_status(db_session, session.id, status)
    await db_session.commit()
    return headers, session, doc


@pytest.mark.asyncio
async def test_rerun_failed_session_creates_new_session_same_document(client, db_session):
    headers, session, doc = await _make_session(client, db_session, HarnessSessionStatus.failed)

    resp = await client.post(f"/api/harness/sessions/{session.id}/rerun", headers=headers)
    assert resp.status_code == 201, resp.text
    new_id = uuid.UUID(resp.json()["harness_session_id"])
    assert new_id != session.id

    new = await harness_repo.get_session(db_session, new_id)
    assert new.document_id == doc.id
    assert new.status == HarnessSessionStatus.pending
    assert new.config["document_id"] == str(doc.id)


@pytest.mark.asyncio
async def test_rerun_rejects_non_failed_session(client, db_session):
    headers, session, _ = await _make_session(client, db_session, HarnessSessionStatus.pending)
    resp = await client.post(f"/api/harness/sessions/{session.id}/rerun", headers=headers)
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_rerun_unknown_session_404(client):
    headers = await get_auth_headers(client)
    resp = await client.post(f"/api/harness/sessions/{uuid.uuid4()}/rerun", headers=headers)
    assert resp.status_code == 404
