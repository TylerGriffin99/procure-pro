import pytest
from httpx import AsyncClient


async def get_auth_headers(client: AsyncClient) -> dict:
    await client.post("/api/v1/auth/register", json={
        "email": "qs@dmp.co.nz", "password": "password123", "full_name": "QS User",
    })
    resp = await client.post("/api/v1/auth/login", data={
        "username": "qs@dmp.co.nz", "password": "password123",
    })
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_create_project(client: AsyncClient):
    headers = await get_auth_headers(client)
    resp = await client.post("/api/v1/projects", json={
        "name": "Gilmours Central - Seismic Upgrade",
        "project_number": "S-02314",
        "client_name": "Foodstuffs North Island",
        "contractor_name": "Kynoch Construction Ltd",
        "contract_sum": "4172492.92",
        "end_client_name": "Foodstuffs North Island",
        "end_client_representative": "Owen Sanders",
        "end_client_address": "Hope River\n251A Main Highway\nEllerslie\nAUCKLAND\n1060",
        "landlord_split_pct": "0.9978",
        "operator_split_pct": "0.0022",
        "retention_tiers": [
            {"tier_order": 1, "percentage": "0.10", "up_to_amount": "200000"},
            {"tier_order": 2, "percentage": "0.05", "up_to_amount": "800000"},
            {"tier_order": 3, "percentage": "0.0175", "up_to_amount": None},
        ],
        "wbs_codes": [
            {"code": "04-01", "description": "Demolition", "parent_code": "04", "sort_order": 1},
            {"code": "04-02", "description": "Bulk Excavation", "parent_code": "04", "sort_order": 2},
            {"code": "05-01", "description": "Substructure", "parent_code": "05", "sort_order": 10},
            {"code": "05-02", "description": "Frame", "parent_code": "05", "sort_order": 11},
        ],
    }, headers=headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Gilmours Central - Seismic Upgrade"
    assert data["contract_sum"] == "4172492.92"
    assert data["end_client_name"] == "Foodstuffs North Island"
    assert data["landlord_split_pct"] == "0.9978"
    assert data["operator_split_pct"] == "0.0022"
    assert len(data["retention_tiers"]) == 3
    assert len(data["wbs_codes"]) == 4


@pytest.mark.asyncio
async def test_list_projects(client: AsyncClient):
    headers = await get_auth_headers(client)
    await client.post("/api/v1/projects", json={
        "name": "Test Project",
        "client_name": "Client",
        "contractor_name": "Contractor",
        "contract_sum": "1000000",
    }, headers=headers)
    resp = await client.get("/api/v1/projects", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()) >= 1
