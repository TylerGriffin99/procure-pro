"""End-to-end test: upload claim -> create assessment -> approve items -> generate PR PDF."""
from decimal import Decimal
from pathlib import Path

import pytest
from httpx import AsyncClient

from app.tests.test_projects import get_auth_headers

CLAIM_1_PATH = Path(__file__).parent.parent.parent.parent / "claim" / "Gilmours" / "claims" / "Gilmours Central_Progress Claim No. 1.pdf"


@pytest.mark.skipif(not CLAIM_1_PATH.exists(), reason="Sample PDF not available")
@pytest.mark.asyncio
async def test_full_claim_flow(client: AsyncClient):
    headers = await get_auth_headers(client)

    # 1. Create project with retention tiers
    project = await client.post("/api/projects", json={
        "name": "Gilmours Central - Seismic Upgrade",
        "project_number": "S-02314",
        "client_name": "Foodstuffs North Island",
        "contractor_name": "Kynoch Construction",
        "contract_sum": "4172492.92",
        "gst_rate": "0.15",
        "retention_tiers": [
            {"tier_order": 1, "percentage": "0.10", "up_to_amount": "200000"},
            {"tier_order": 2, "percentage": "0.05", "up_to_amount": "800000"},
            {"tier_order": 3, "percentage": "0.0175", "up_to_amount": None},
        ],
    }, headers=headers)
    project_id = project.json()["id"]

    # 2. Upload claim PDF
    with open(CLAIM_1_PATH, "rb") as f:
        claim_resp = await client.post(
            f"/api/projects/{project_id}/claims/upload",
            files={"file": ("claim1.pdf", f, "application/pdf")},
            headers=headers,
        )
    assert claim_resp.status_code == 201
    claim_id = claim_resp.json()["id"]
    line_items = claim_resp.json()["line_items"]
    assert len(line_items) > 0

    # 3. Create assessment
    assess_resp = await client.post(
        f"/api/projects/{project_id}/assessments",
        json={"claim_id": claim_id},
        headers=headers,
    )
    assert assess_resp.status_code == 201
    assessment = assess_resp.json()
    assessment_id = assessment["id"]

    # 4. Approve some line items
    for li in assessment["line_items"]:
        if li["contractor_claim_to_date"] != "0.00":
            # Approve with claimed amount (accept as-is)
            resp = await client.patch(
                f"/api/projects/{project_id}/assessments/{assessment_id}/line-items/{li['id']}",
                json={
                    "status": "approved",
                    "total_recommended": li["contractor_claim_to_date"],
                    "comments": "As per progress noted on site",
                },
                headers=headers,
            )
            assert resp.status_code == 200

    # 5. Download PR PDF
    pdf_resp = await client.get(
        f"/api/projects/{project_id}/assessments/{assessment_id}/pdf",
        headers=headers,
    )
    assert pdf_resp.status_code == 200
    assert pdf_resp.headers["content-type"] == "application/pdf"
    assert pdf_resp.content[:5] == b"%PDF-"
