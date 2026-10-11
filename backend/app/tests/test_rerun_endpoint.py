import json
import uuid
from pathlib import Path
from unittest.mock import patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.assessment import Assessment, AssessmentStatus
from app.models.claim import Claim
from app.repos import harness_repo


@pytest.mark.asyncio
async def test_rerun_creates_new_session(
    client: AsyncClient, db_session: AsyncSession, test_user, test_project, auth_headers,
):
    """POST /rerun should delete old claim, create new harness session."""
    session = await harness_repo.create_session(
        db=db_session, user_id=test_user.id,
        project_id=test_project.id, harness_type="claim_parse",
        config={"file_path": "/tmp/test.pdf"},
        input_file_path="/tmp/test.pdf",
    )
    claim = Claim(
        project_id=test_project.id, claim_number=1,
        created_by=test_user.id,
    )
    db_session.add(claim)
    await db_session.flush()

    assessment = Assessment(
        claim_id=claim.id, project_id=test_project.id,
        version=1, created_by=test_user.id,
    )
    db_session.add(assessment)
    await db_session.flush()

    await harness_repo.set_claim_id(db_session, session.id, claim.id)
    await db_session.commit()

    with patch("pathlib.Path.exists", return_value=True):
        resp = await client.post(
            f"/api/v1/projects/{test_project.id}/claims/{claim.id}/rerun",
            headers=auth_headers,
        )

    assert resp.status_code == 201
    data = resp.json()
    assert "harness_session_id" in data
    assert data["harness_session_id"] != str(session.id)


@pytest.mark.asyncio
async def test_rerun_blocks_finalised(
    client: AsyncClient, db_session: AsyncSession, test_user, test_project, auth_headers,
):
    """POST /rerun should return 409 for finalised assessments."""
    session = await harness_repo.create_session(
        db=db_session, user_id=test_user.id,
        project_id=test_project.id, harness_type="claim_parse",
        config={"file_path": "/tmp/test.pdf"},
        input_file_path="/tmp/test.pdf",
    )
    claim = Claim(
        project_id=test_project.id, claim_number=1,
        created_by=test_user.id,
    )
    db_session.add(claim)
    await db_session.flush()

    assessment = Assessment(
        claim_id=claim.id, project_id=test_project.id,
        version=1, status=AssessmentStatus.finalised,
        created_by=test_user.id,
    )
    db_session.add(assessment)
    await db_session.flush()

    await harness_repo.set_claim_id(db_session, session.id, claim.id)
    await db_session.commit()

    resp = await client.post(
        f"/api/v1/projects/{test_project.id}/claims/{claim.id}/rerun",
        headers=auth_headers,
    )
    assert resp.status_code == 409
