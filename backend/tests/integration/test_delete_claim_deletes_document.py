import uuid

import pytest

from app.harness.models import HarnessType
from app.repos import document_repo, harness_repo, user_repo
from tests.e2e.fixtures.gilmours_claim1 import PROJECT
from tests.e2e.helpers import get_auth_headers


@pytest.mark.asyncio
async def test_delete_claim_deletes_its_document(client, db_session):
    headers = await get_auth_headers(client)
    user = await user_repo.get_by_email(db_session, "qs@dmp.co.nz")
    proj_resp = await client.post("/api/v1/projects", json=PROJECT, headers=headers)
    project_id = proj_resp.json()["id"]

    # Create a minimal claim via the API.
    claim_resp = await client.post(
        f"/api/v1/projects/{project_id}/claims", json={"claim_number": 1}, headers=headers,
    )
    assert claim_resp.status_code == 201, claim_resp.text
    claim_id = uuid.UUID(claim_resp.json()["id"])

    # Attach a Document + session to that claim (as the pipeline would on success).
    doc = await document_repo.create_document(
        db_session, uuid.UUID(project_id), "c.pdf", "application/pdf", b"%PDF-1.4 x",
    )
    session = await harness_repo.create_session(
        db=db_session, user_id=user.id, project_id=uuid.UUID(project_id),
        harness_type=HarnessType.CLAIM_PARSE, document_id=doc.id,
        config={"document_id": str(doc.id)},
    )
    await harness_repo.set_claim_id(db_session, session.id, claim_id)
    await db_session.commit()

    # Delete the claim via the API.
    del_resp = await client.delete(
        f"/api/v1/projects/{project_id}/claims/{claim_id}", headers=headers,
    )
    assert del_resp.status_code == 204, del_resp.text

    # Document and session are gone.
    assert await document_repo.get_document(db_session, doc.id) is None
    assert await harness_repo.get_session(db_session, session.id) is None


@pytest.mark.asyncio
async def test_old_claim_rerun_endpoint_removed(client):
    headers = await get_auth_headers(client)
    proj_resp = await client.post("/api/v1/projects", json=PROJECT, headers=headers)
    project_id = proj_resp.json()["id"]
    resp = await client.post(
        f"/api/v1/projects/{project_id}/claims/{uuid.uuid4()}/rerun", headers=headers,
    )
    assert resp.status_code == 404
