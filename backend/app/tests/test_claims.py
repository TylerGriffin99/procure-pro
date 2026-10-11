from pathlib import Path

import pytest
from httpx import AsyncClient

from app.tests.test_projects import get_auth_headers

CLAIM_1_PATH = Path(__file__).parent.parent.parent.parent / "claim" / "Gilmours" / "claims" / "Gilmours Central_Progress Claim No. 1.pdf"


@pytest.mark.skipif(not CLAIM_1_PATH.exists(), reason="Sample PDF not available")
@pytest.mark.asyncio
async def test_upload_and_parse_claim(client: AsyncClient):
    headers = await get_auth_headers(client)

    # Create project first
    project_resp = await client.post("/api/v1/projects", json={
        "name": "Gilmours Central",
        "client_name": "Foodstuffs",
        "contractor_name": "Kynoch",
        "contract_sum": "4172492.92",
    }, headers=headers)
    project_id = project_resp.json()["id"]

    # Upload claim PDF
    with open(CLAIM_1_PATH, "rb") as f:
        resp = await client.post(
            f"/api/v1/projects/{project_id}/claims/upload",
            files={"file": ("claim1.pdf", f, "application/pdf")},
            headers=headers,
        )
    assert resp.status_code == 201
    data = resp.json()
    assert "harness_session_id" in data
