import uuid
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_list_flags_empty(client: AsyncClient, test_project, auth_headers):
    resp = await client.get(
        f"/api/v1/projects/{test_project.id}/claims/{uuid.uuid4()}/flags",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json() == []
