import hashlib
import io
import uuid

import pytest

from app.repos import document_repo, harness_repo
from tests.e2e.fixtures.gilmours_claim1 import PROJECT
from tests.e2e.helpers import get_auth_headers


@pytest.mark.asyncio
async def test_upload_persists_document_and_links_session(client, db_session):
    headers = await get_auth_headers(client)
    proj_resp = await client.post("/api/projects", json=PROJECT, headers=headers)
    project_id = proj_resp.json()["id"]

    content = b"%PDF-1.4\nminimal\n%%EOF"
    resp = await client.post(
        f"/api/projects/{project_id}/claims/upload",
        files={"file": ("claim.pdf", io.BytesIO(content), "application/pdf")},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    session_id = uuid.UUID(resp.json()["harness_session_id"])

    session = await harness_repo.get_session(db_session, session_id)
    assert session is not None
    assert session.document_id is not None
    assert session.config["document_id"] == str(session.document_id)

    doc = await document_repo.get_document(db_session, session.document_id)
    assert doc.file_data == content
    assert doc.sha256 == hashlib.sha256(content).hexdigest()


@pytest.mark.asyncio
async def test_upload_rejects_non_pdf(client):
    headers = await get_auth_headers(client)
    proj_resp = await client.post("/api/projects", json=PROJECT, headers=headers)
    project_id = proj_resp.json()["id"]

    resp = await client.post(
        f"/api/projects/{project_id}/claims/upload",
        files={"file": ("notes.txt", io.BytesIO(b"hello"), "text/plain")},
        headers=headers,
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_upload_rejects_oversized(client):
    headers = await get_auth_headers(client)
    proj_resp = await client.post("/api/projects", json=PROJECT, headers=headers)
    project_id = proj_resp.json()["id"]

    big = b"%PDF-1.4" + b"0" * (26 * 1024 * 1024)
    resp = await client.post(
        f"/api/projects/{project_id}/claims/upload",
        files={"file": ("big.pdf", io.BytesIO(big), "application/pdf")},
        headers=headers,
    )
    assert resp.status_code == 400
