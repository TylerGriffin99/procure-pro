import pytest
from httpx import AsyncClient

from app.tests.test_projects import get_auth_headers


@pytest.mark.asyncio
async def test_create_assessment_from_claim(client: AsyncClient):
    """Creating an assessment should generate unapproved line items from claim data."""
    headers = await get_auth_headers(client)

    # Setup: create project
    project_resp = await client.post("/api/v1/projects", json={
        "name": "Test",
        "client_name": "Client",
        "contractor_name": "Contractor",
        "contract_sum": "4172492.92",
    }, headers=headers)
    project_id = project_resp.json()["id"]

    # Create a claim manually (no PDF upload in this test)
    claim_resp = await client.post(f"/api/v1/projects/{project_id}/claims", json={
        "claim_number": 1,
        "period_from": "2025-08-18",
        "period_to": "2025-08-31",
        "line_items": [
            {
                "ref_code": "3510",
                "description": "Structural Steel",
                "item_type": "contract_work",
                "contract_value": "1184000.00",
                "percentage": "0.00",
                "ptd": "0.00",
                "previous": "0.00",
                "current": "0.00",
                "balance": "1184000.00",
            },
            {
                "ref_code": "5410",
                "description": "Preliminary and General",
                "item_type": "contract_work",
                "contract_value": "250000.00",
                "percentage": "2.50",
                "ptd": "6250.00",
                "previous": "0.00",
                "current": "6250.00",
                "balance": "243750.00",
            },
        ],
    }, headers=headers)
    claim_id = claim_resp.json()["id"]

    # Create assessment
    assess_resp = await client.post(
        f"/api/v1/projects/{project_id}/assessments",
        json={"claim_id": claim_id},
        headers=headers,
    )
    assert assess_resp.status_code == 201
    data = assess_resp.json()
    assert data["status"] == "draft"
    assert data["version"] == 1
    assert len(data["line_items"]) == 2
    # All items start as unapproved
    assert all(li["status"] == "unapproved" for li in data["line_items"])


@pytest.mark.asyncio
async def test_approve_line_item(client: AsyncClient):
    """QS should be able to approve a line item with an adjusted amount."""
    headers = await get_auth_headers(client)

    # Setup project + claim + assessment (abbreviated)
    project_resp = await client.post("/api/v1/projects", json={
        "name": "Test2", "client_name": "C", "contractor_name": "K", "contract_sum": "100000",
    }, headers=headers)
    project_id = project_resp.json()["id"]

    claim_resp = await client.post(f"/api/v1/projects/{project_id}/claims", json={
        "claim_number": 1,
        "period_from": "2025-08-18",
        "period_to": "2025-08-31",
        "line_items": [{
            "ref_code": "3390",
            "description": "Provisional sum - Fence removal",
            "item_type": "provisional_sum",
            "contract_value": "15000.00",
            "percentage": "47.43",
            "ptd": "7114.38",
            "previous": "0.00",
            "current": "7114.38",
            "balance": "7885.62",
        }],
    }, headers=headers)
    claim_id = claim_resp.json()["id"]

    assess_resp = await client.post(
        f"/api/v1/projects/{project_id}/assessments",
        json={"claim_id": claim_id},
        headers=headers,
    )
    assessment_id = assess_resp.json()["id"]
    line_item_id = assess_resp.json()["line_items"][0]["id"]

    # Approve with adjusted amount (QS certifies 5384.38 instead of 7114.38)
    approve_resp = await client.patch(
        f"/api/v1/projects/{project_id}/assessments/{assessment_id}/line-items/{line_item_id}",
        json={
            "status": "approved",
            "total_recommended": "5384.38",
            "comments": "Certify 86.5 hours x $40/h as discussed with site QS",
        },
        headers=headers,
    )
    assert approve_resp.status_code == 200
    data = approve_resp.json()
    assert data["status"] == "approved"
    assert data["total_recommended"] == "5384.38"
    assert data["variance_to_claim"] == "-1730.00"  # 5384.38 - 7114.38
