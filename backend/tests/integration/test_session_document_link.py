import uuid

import pytest

from app.harness.models import HarnessType
from app.repos import document_repo, harness_repo, user_repo
from tests.e2e.fixtures.gilmours_claim1 import PROJECT
from tests.e2e.helpers import get_auth_headers


@pytest.mark.asyncio
async def test_session_requires_document_and_cascades(client, db_session):
    headers = await get_auth_headers(client)
    user = await user_repo.get_by_email(db_session, "qs@dmp.co.nz")
    proj_resp = await client.post("/api/v1/projects", json=PROJECT, headers=headers)
    project_id = uuid.UUID(proj_resp.json()["id"])

    doc = await document_repo.create_document(
        db_session, project_id, "c.pdf", "application/pdf", b"%PDF-1.4 x",
    )
    session = await harness_repo.create_session(
        db=db_session,
        user_id=user.id,
        project_id=project_id,
        harness_type=HarnessType.CLAIM_PARSE,
        document_id=doc.id,
        config={"document_id": str(doc.id)},
    )
    await db_session.commit()
    assert session.document_id == doc.id

    # Deleting the Document cascades away the session
    await db_session.delete(doc)
    await db_session.commit()
    assert await harness_repo.get_session(db_session, session.id) is None
