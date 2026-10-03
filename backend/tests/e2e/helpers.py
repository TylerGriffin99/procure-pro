"""Shared helpers for e2e tests."""
import json
from decimal import Decimal
from pathlib import Path

from httpx import AsyncClient


async def get_auth_headers(client: AsyncClient) -> dict:
    """Register + login, return Bearer header dict."""
    await client.post("/api/auth/register", json={
        "email": "qs@dmp.co.nz",
        "password": "password123",
        "first_name": "QS",
        "last_name": "User",
        "country": "NZ",
    })
    resp = await client.post("/api/auth/login", data={
        "username": "qs@dmp.co.nz", "password": "password123",
    })
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _d(v: str) -> Decimal:
    return Decimal(v)


def _assert_decimal_eq(actual: str, expected: str, label: str):
    """Compare two decimal strings with exact precision."""
    assert _d(actual) == _d(expected), f"{label}: expected {expected}, got {actual}"


async def upload_claim_deep_mode(
    client: AsyncClient, project_id: str, pdf_path: Path, headers: dict,
) -> str:
    """Upload a claim via deep_mode and stream to completion. Returns claim_id."""
    with open(pdf_path, "rb") as f:
        upload_resp = await client.post(
            f"/api/projects/{project_id}/claims/upload",
            params={"mode": "deep_mode"},
            files={"file": (pdf_path.name, f, "application/pdf")},
            headers=headers,
        )
    assert upload_resp.status_code == 201, upload_resp.text
    harness_session_id = upload_resp.json()["harness_session_id"]

    collected_events = []
    async with client.stream(
        "GET",
        f"/api/harness/sessions/{harness_session_id}/stream",
        headers=headers,
        timeout=600.0,
    ) as stream:
        async for line in stream.aiter_lines():
            if not line.startswith("data: "):
                continue
            payload = line[len("data: "):]
            if payload == "[DONE]":
                break
            collected_events.append(json.loads(payload))

    event_types = [e["type"] for e in collected_events]
    assert "harness_error" not in event_types, (
        f"Harness errored: {[e for e in collected_events if 'error' in e]}"
    )
    assert "harness_complete" in event_types, (
        f"Harness did not complete. Events: {event_types}"
    )

    complete_event = next(e for e in collected_events if e["type"] == "harness_complete")
    return complete_event["claim_id"]


async def auto_approve_assessment(
    client: AsyncClient, project_id: str, assessment_id: str, assessment: dict, headers: dict,
):
    """Approve ALL unapproved items at their auto-calculated values (no QS reductions).

    This approves every line item, PS item, and variation item at exactly the
    value the system auto-calculated. No manual adjustments.
    """
    for li in assessment["line_items"]:
        if li["status"] == "unapproved":
            await client.patch(
                f"/api/projects/{project_id}/assessments/{assessment_id}/line-items/{li['id']}",
                json={
                    "total_recommended": li["total_recommended"],
                    "status": "approved",
                },
                headers=headers,
            )

    for ps in assessment.get("provisional_sum_items", []):
        if ps["status"] == "unapproved":
            await client.patch(
                f"/api/projects/{project_id}/assessments/{assessment_id}/provisional-sum-items/{ps['id']}",
                json={
                    "total_recommended": ps["total_recommended"],
                    "status": "approved",
                },
                headers=headers,
            )

    for var in assessment.get("variation_items", []):
        if var["status"] == "unapproved":
            await client.patch(
                f"/api/projects/{project_id}/assessments/{assessment_id}/variation-items/{var['id']}",
                json={
                    "total_recommended": var["total_recommended"],
                    "status": "approved",
                },
                headers=headers,
            )
