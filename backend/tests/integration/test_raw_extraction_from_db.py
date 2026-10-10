import uuid
from pathlib import Path

import pytest

from app.harness.executors.raw_extraction import execute_raw_extraction
from app.repos import document_repo
from tests.e2e.fixtures.gilmours_claim1 import PROJECT
from tests.e2e.helpers import get_auth_headers

REPO_ROOT = Path(__file__).resolve().parents[3]
PDF_PATH = REPO_ROOT / "claim" / "Gilmours" / "claims" / "Gilmours Central_Progress Claim No. 1.pdf"


@pytest.mark.asyncio
async def test_raw_extraction_reads_bytes_from_document(client, db_session):
    if not PDF_PATH.exists():
        pytest.skip(f"fixture PDF not present: {PDF_PATH}")

    headers = await get_auth_headers(client)
    proj_resp = await client.post("/api/v1/projects", json=PROJECT, headers=headers)
    project_id = uuid.UUID(proj_resp.json()["id"])

    content = PDF_PATH.read_bytes()
    doc = await document_repo.create_document(
        db_session, project_id, PDF_PATH.name, "application/pdf", content,
    )
    await db_session.commit()

    result = await execute_raw_extraction(
        db=db_session,
        session_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        project_id=project_id,
        config={"document_id": str(doc.id)},
    )
    assert len(result["pages"]) > 0
    assert any(p["text"] for p in result["pages"])


@pytest.mark.asyncio
async def test_raw_extraction_missing_document_raises(db_session):
    with pytest.raises(FileNotFoundError):
        await execute_raw_extraction(
            db=db_session,
            session_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            project_id=uuid.uuid4(),
            config={"document_id": str(uuid.uuid4())},
        )
