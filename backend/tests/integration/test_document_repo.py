import hashlib
import uuid

import pytest

from app.repos import document_repo
from tests.e2e.fixtures.gilmours_claim1 import PROJECT
from tests.e2e.helpers import get_auth_headers


@pytest.mark.asyncio
async def test_create_and_get_document_roundtrips_bytes(client, db_session):
    headers = await get_auth_headers(client)
    proj_resp = await client.post("/api/v1/projects", json=PROJECT, headers=headers)
    assert proj_resp.status_code == 201, proj_resp.text
    project_id = uuid.UUID(proj_resp.json()["id"])

    content = b"%PDF-1.4\nhello world\n%%EOF"
    doc = await document_repo.create_document(
        db_session, project_id, "claim.pdf", "application/pdf", content,
    )
    await db_session.commit()

    fetched = await document_repo.get_document(db_session, doc.id)
    assert fetched is not None
    assert fetched.file_data == content
    assert fetched.file_size == len(content)
    assert fetched.sha256 == hashlib.sha256(content).hexdigest()
    assert fetched.content_type == "application/pdf"
    assert fetched.project_id == project_id
