"""
E2E integration test: real PDF upload → real LLM calls → real DB verification.

Uses deep_mode (harness pipeline) to parse Gilmours Central Progress Claim No. 1,
then verifies all created records against strict expected fixtures.

Requires:
  - Test DB running on localhost:6000
  - LLM_PROVIDER and matching API key set in environment
  - claim/Gilmours/claims/Gilmours Central_Progress Claim No. 1.pdf present
"""
import json
from pathlib import Path

import pytest
from httpx import AsyncClient

from tests.e2e.fixtures.gilmours_claim1 import (
    EXPECTED_ASSESSMENT_LINE_ITEM_COUNT,
    EXPECTED_ASSESSMENT_LINE_ITEMS,
    EXPECTED_ASSESSMENT_PS_COUNT,
    EXPECTED_ASSESSMENT_PS_ITEMS,
    EXPECTED_ASSESSMENT_VAR_COUNT,
    EXPECTED_ASSESSMENT_VAR_ITEMS,
    EXPECTED_CLAIM_ITEM_COUNT,
    EXPECTED_CLAIM_LINE_ITEMS,
    PROJECT,
)
from tests.e2e.helpers import _assert_decimal_eq, _d, get_auth_headers

CLAIM_1_PATH = (
    Path(__file__).parent.parent.parent.parent
    / "claim"
    / "Gilmours"
    / "claims"
    / "Gilmours Central_Progress Claim No. 1.pdf"
)


@pytest.mark.skipif(not CLAIM_1_PATH.exists(), reason="Sample PDF not available")
@pytest.mark.asyncio
async def test_deep_mode_e2e(client: AsyncClient):
    """Full pipeline: project → deep-mode upload → harness stream → strict DB verification."""
    headers = await get_auth_headers(client)

    # ── 1. Create project ───────────────────────────────────────────────────
    project_resp = await client.post("/api/projects", json=PROJECT, headers=headers)
    assert project_resp.status_code == 201, project_resp.text
    project = project_resp.json()
    project_id = project["id"]

    assert project["name"] == PROJECT["name"]
    assert project["contract_sum"] == PROJECT["contract_sum"]
    assert len(project["retention_tiers"]) == 3

    wbs_categories = project["wbs_codes"]
    assert len(wbs_categories) >= 14
    total_subcats = sum(len(cat.get("children", [])) for cat in wbs_categories)
    assert total_subcats >= 28

    # ── 2. Upload claim PDF in deep_mode ────────────────────────────────────
    with open(CLAIM_1_PATH, "rb") as f:
        upload_resp = await client.post(
            f"/api/projects/{project_id}/claims/upload",
            params={"mode": "deep_mode"},
            files={"file": ("Gilmours Central_Progress Claim No. 1.pdf", f, "application/pdf")},
            headers=headers,
        )
    assert upload_resp.status_code == 201, upload_resp.text
    harness_session_id = upload_resp.json()["harness_session_id"]

    # ── 3. Stream harness execution (real LLM calls) ────────────────────────
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
    assert "harness_start" in event_types, f"Missing harness_start. Events: {event_types}"
    assert "harness_error" not in event_types, (
        f"Harness errored: {[e for e in collected_events if 'error' in e]}"
    )
    assert "harness_complete" in event_types, f"Harness did not complete. Events: {event_types}"

    phase_starts = [e for e in collected_events if e["type"] == "harness_phase_start"]
    phase_results = [e for e in collected_events if e["type"] == "harness_phase_result"]
    assert len(phase_starts) == 7, f"Expected 7 phase starts, got {len(phase_starts)}"
    assert len(phase_results) == 7, f"Expected 7 phase results, got {len(phase_results)}"

    complete_event = next(e for e in collected_events if e["type"] == "harness_complete")
    claim_id = complete_event["claim_id"]
    assert claim_id is not None

    # ── 4. Verify harness session record ────────────────────────────────────
    session_resp = await client.get(
        f"/api/harness/sessions/{harness_session_id}", headers=headers,
    )
    assert session_resp.status_code == 200
    session = session_resp.json()
    assert session["status"] == "completed"
    assert session["claim_id"] == claim_id

    # ── 5. Verify workspace files ───────────────────────────────────────────
    workspace_resp = await client.get(
        f"/api/harness/sessions/{harness_session_id}/workspace", headers=headers,
    )
    assert workspace_resp.status_code == 200
    workspace_paths = {f["file_path"] for f in workspace_resp.json()}
    expected_files = {
        "raw_extraction.json", "format_detection.json", "parsed_claim.json",
        "validation_summary.json", "wbs_matches.json", "vps_matches.json",
        "creation_summary.json",
    }
    assert expected_files.issubset(workspace_paths), (
        f"Missing workspace files: {expected_files - workspace_paths}"
    )

    # ── 6. Verify claim line items (strict) ─────────────────────────────────
    claim_resp = await client.get(
        f"/api/projects/{project_id}/claims/{claim_id}", headers=headers,
    )
    assert claim_resp.status_code == 200
    claim = claim_resp.json()
    assert claim["claim_number"] == 1

    claim_line_items = claim["line_items"]
    assert len(claim_line_items) == EXPECTED_CLAIM_ITEM_COUNT, (
        f"Expected {EXPECTED_CLAIM_ITEM_COUNT} claim items, got {len(claim_line_items)}"
    )

    # Build lookup by (item_type, ref_code)
    actual_by_key = {}
    for li in claim_line_items:
        key = (li["item_type"], li.get("ref_code"))
        actual_by_key[key] = li

    # Log actual claim line items for debugging
    print(f"\n  Actual claim line items ({len(claim_line_items)}):")
    for li in sorted(claim_line_items, key=lambda x: (x["item_type"], x.get("ref_code", ""))):
        print(f"    ({li['item_type']}, {li.get('ref_code')}) {li['description']}  "
              f"value={li['contract_value']} ptd={li['ptd']} %={li['percentage']}")

    for expected in EXPECTED_CLAIM_LINE_ITEMS:
        key = (expected["item_type"], expected["ref_code"])
        actual = actual_by_key.get(key)
        assert actual is not None, (
            f"Missing claim item: {key} ({expected['description']})"
        )
        label = f"Claim[{key}]"
        _assert_decimal_eq(actual["contract_value"], expected["contract_value"], f"{label}.contract_value")
        _assert_decimal_eq(actual["percentage"], expected["percentage"], f"{label}.percentage")
        _assert_decimal_eq(actual["ptd"], expected["ptd"], f"{label}.ptd")
        _assert_decimal_eq(actual["previous"], expected["previous"], f"{label}.previous")
        _assert_decimal_eq(actual["current"], expected["current"], f"{label}.current")
        _assert_decimal_eq(actual["balance"], expected["balance"], f"{label}.balance")

    # ── 7. Verify assessment line items (strict) ────────────────────────────
    assessment_resp = await client.get(
        f"/api/projects/{project_id}/assessments/by-claim/{claim_id}", headers=headers,
    )
    assert assessment_resp.status_code == 200
    assessment = assessment_resp.json()
    assessment_id = assessment["id"]

    assessment_line_items = assessment["line_items"]
    assert len(assessment_line_items) >= EXPECTED_ASSESSMENT_LINE_ITEM_COUNT, (
        f"Expected at least {EXPECTED_ASSESSMENT_LINE_ITEM_COUNT} assessment items, "
        f"got {len(assessment_line_items)}"
    )

    # Log actual assessment line items for debugging
    print(f"\n  Actual assessment line items ({len(assessment_line_items)}):")
    for ali in sorted(assessment_line_items, key=lambda x: x.get("sort_order", 0)):
        print(f"    [{ali.get('sort_order')}] {ali['description']}  "
              f"contract_sum={ali['contract_sum']} claimed={ali['contractor_claim_to_date']} "
              f"recommended={ali['total_recommended']} status={ali['status']}")

    # Build lookup by (description, sort_order) to handle duplicate descriptions
    actual_ali_by_key = {}
    for ali in assessment_line_items:
        key = (ali["description"], ali["sort_order"])
        actual_ali_by_key[key] = ali

    for expected in EXPECTED_ASSESSMENT_LINE_ITEMS:
        desc = expected["description"]
        key = (desc, expected["sort_order"])
        actual = actual_ali_by_key.get(key)
        assert actual is not None, f"Missing assessment item: '{desc}' (sort_order={expected['sort_order']})"
        label = f"Assessment[{desc}@{expected['sort_order']}]"
        _assert_decimal_eq(actual["contract_sum"], expected["contract_sum"], f"{label}.contract_sum")
        _assert_decimal_eq(actual["contractor_claim_to_date"], expected["contractor_claim_to_date"], f"{label}.contractor_claim_to_date")
        _assert_decimal_eq(actual["total_recommended"], expected["total_recommended"], f"{label}.total_recommended")
        _assert_decimal_eq(actual["percentage"], expected["percentage"], f"{label}.percentage")
        _assert_decimal_eq(actual["previously_paid"], expected["previously_paid"], f"{label}.previously_paid")
        _assert_decimal_eq(actual["recommended_this_period"], expected["recommended_this_period"], f"{label}.recommended_this_period")
        assert actual["status"] == expected["status"], f"{label}.status: expected {expected['status']}, got {actual['status']}"
        assert actual["sort_order"] == expected["sort_order"], f"{label}.sort_order: expected {expected['sort_order']}, got {actual['sort_order']}"

    # ── 8. Verify assessment provisional sums (strict) ──────────────────────
    assessment_ps = assessment.get("provisional_sum_items", [])
    assert len(assessment_ps) == EXPECTED_ASSESSMENT_PS_COUNT, (
        f"Expected {EXPECTED_ASSESSMENT_PS_COUNT} PS items, got {len(assessment_ps)}"
    )

    # Sort by contractor_claim_to_date for stable comparison
    actual_ps_sorted = sorted(assessment_ps, key=lambda x: _d(x["contractor_claim_to_date"]))
    expected_ps_sorted = sorted(EXPECTED_ASSESSMENT_PS_ITEMS, key=lambda x: _d(x["contractor_claim_to_date"]))

    for i, (actual, expected) in enumerate(zip(actual_ps_sorted, expected_ps_sorted)):
        label = f"PS[{i}]"
        _assert_decimal_eq(actual["contractor_claim_to_date"], expected["contractor_claim_to_date"], f"{label}.contractor_claim_to_date")
        _assert_decimal_eq(actual["total_recommended"], expected["total_recommended"], f"{label}.total_recommended")
        _assert_decimal_eq(actual["previously_paid"], expected["previously_paid"], f"{label}.previously_paid")
        _assert_decimal_eq(actual["recommended_this_period"], expected["recommended_this_period"], f"{label}.recommended_this_period")
        assert actual["status"] == expected["status"], f"{label}.status: expected {expected['status']}, got {actual['status']}"

    # ── 9. Verify assessment variations (strict) ────────────────────────────
    assessment_vars = assessment.get("variation_items", [])
    assert len(assessment_vars) == EXPECTED_ASSESSMENT_VAR_COUNT, (
        f"Expected {EXPECTED_ASSESSMENT_VAR_COUNT} variation items, got {len(assessment_vars)}"
    )

    actual_vars_sorted = sorted(assessment_vars, key=lambda x: _d(x["contractor_claim_to_date"]))
    expected_vars_sorted = sorted(EXPECTED_ASSESSMENT_VAR_ITEMS, key=lambda x: _d(x["contractor_claim_to_date"]))

    for i, (actual, expected) in enumerate(zip(actual_vars_sorted, expected_vars_sorted)):
        label = f"Var[{i}]"
        _assert_decimal_eq(actual["contractor_claim_to_date"], expected["contractor_claim_to_date"], f"{label}.contractor_claim_to_date")
        _assert_decimal_eq(actual["total_recommended"], expected["total_recommended"], f"{label}.total_recommended")
        _assert_decimal_eq(actual["previously_paid"], expected["previously_paid"], f"{label}.previously_paid")
        _assert_decimal_eq(actual["recommended_this_period"], expected["recommended_this_period"], f"{label}.recommended_this_period")
        assert actual["status"] == expected["status"], f"{label}.status: expected {expected['status']}, got {actual['status']}"

    # ── 10. Verify assessment financial totals ──────────────────────────────
    assert assessment["contract_sum"] is not None
    assert assessment["total_recommended"] is not None

    # ── Summary ─────────────────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print(f"  E2E Deep Mode Test PASSED (strict fixtures)")
    print(f"  Project:      {project_id}")
    print(f"  Claim:        {claim_id} ({len(claim_line_items)} items)")
    print(f"  Assessment:   {assessment_id} ({len(assessment_line_items)} items)")
    print(f"  PS items:     {len(assessment_ps)}")
    print(f"  Var items:    {len(assessment_vars)}")
    print(f"  Session:      {harness_session_id}")
    print(f"{'='*60}")
