"""
E2E integration test: second claim upload after a finalised first claim.

Verifies that previously_paid values carry forward correctly from a finalised
assessment, and that all totals match expected PR2 values.

Requires:
  - Test DB running on localhost:6000
  - LLM_PROVIDER and matching API key set in environment
  - claim/Gilmours/claims/Gilmours Central_Progress Claim No. 1.pdf present
  - claim/Gilmours/claims/Gilmours Central_Progress Claim No. 2.pdf present
"""
from decimal import Decimal
from pathlib import Path

import pytest
from httpx import AsyncClient

from tests.e2e.fixtures.gilmours_claim1 import (
    EXPECTED_ASSESSMENT_LINE_ITEMS as EXPECTED_ASSESSMENT_1_LINE_ITEMS,
    EXPECTED_ASSESSMENT_PS_ITEMS as EXPECTED_ASSESSMENT_1_PS_ITEMS,
    EXPECTED_ASSESSMENT_VAR_ITEMS as EXPECTED_ASSESSMENT_1_VAR_ITEMS,
    EXPECTED_CLAIM_ITEM_COUNT,
    PROJECT,
)
from tests.e2e.fixtures.gilmours_claim2 import (
    ASSESSMENT_1_EXPECTED,
    ASSESSMENT_2_EXPECTED,
    EXPECTED_ASSESSMENT_2_LINE_ITEM_COUNT,
    EXPECTED_ASSESSMENT_2_HISTORY_ROWS,
    EXPECTED_ASSESSMENT_2_PS_COUNT,
    EXPECTED_ASSESSMENT_2_PS_HISTORY,
    EXPECTED_ASSESSMENT_2_VAR_COUNT,
    EXPECTED_ASSESSMENT_2_VAR_HISTORY,
    EXPECTED_CLAIM_2_ITEM_COUNT,
    EXPECTED_CLAIM_2_LINE_ITEMS,
    EXPECTED_HISTORY_ROW_COUNT,
    PR1_CONTRACT_WORK_APPROVALS,
    PR1_PS_RECOMMENDED,
    PR2_VAR3_RECOMMENDED,
)
from tests.e2e.helpers import (
    _assert_decimal_eq,
    _d,
    get_auth_headers,
    upload_claim_deep_mode as _upload_claim_deep_mode,
)

CLAIM_1_PATH = (
    Path(__file__).parent.parent.parent.parent
    / "claim"
    / "Gilmours"
    / "claims"
    / "Gilmours Central_Progress Claim No. 1.pdf"
)
CLAIM_2_PATH = (
    Path(__file__).parent.parent.parent.parent
    / "claim"
    / "Gilmours"
    / "claims"
    / "Gilmours Central_Progress Claim No. 2.pdf"
)


async def _approve_assessment_1(
    client: AsyncClient, project_id: str, assessment_id: str, assessment: dict, headers: dict,
):
    """Approve assessment 1 items to match PR1 values."""
    # Approve contract work items that are unapproved (General, Temp driveway, General Margin)
    for li in assessment["line_items"]:
        if li["status"] == "unapproved":
            desc = li["description"]
            if desc in PR1_CONTRACT_WORK_APPROVALS:
                await client.patch(
                    f"/api/projects/{project_id}/assessments/{assessment_id}/line-items/{li['id']}",
                    json={
                        "total_recommended": PR1_CONTRACT_WORK_APPROVALS[desc],
                        "status": "approved",
                    },
                    headers=headers,
                )
            else:
                # Auto-approve at claimed amount
                await client.patch(
                    f"/api/projects/{project_id}/assessments/{assessment_id}/line-items/{li['id']}",
                    json={
                        "total_recommended": li["contractor_claim_to_date"],
                        "status": "approved",
                    },
                    headers=headers,
                )

    # Approve PS items - PS1 (fence) gets QS reduction
    for ps in assessment.get("provisional_sum_items", []):
        if ps["status"] == "unapproved":
            if _d(ps["contractor_claim_to_date"]) > 0:
                # This is PS1 (fence removal) - QS reduces it
                await client.patch(
                    f"/api/projects/{project_id}/assessments/{assessment_id}/provisional-sum-items/{ps['id']}",
                    json={
                        "total_recommended": PR1_PS_RECOMMENDED,
                        "status": "approved",
                    },
                    headers=headers,
                )

    # Approve variation items at their auto values
    for var in assessment.get("variation_items", []):
        if var["status"] == "unapproved":
            await client.patch(
                f"/api/projects/{project_id}/assessments/{assessment_id}/variation-items/{var['id']}",
                json={
                    "total_recommended": var["contractor_claim_to_date"],
                    "status": "approved",
                },
                headers=headers,
            )


@pytest.mark.skipif(
    not (CLAIM_1_PATH.exists() and CLAIM_2_PATH.exists()),
    reason="Sample PDFs not available",
)
@pytest.mark.asyncio
async def test_second_claim_e2e(client: AsyncClient):
    """Full pipeline: claim 1 → approve → finalise → claim 2 → verify carry-forward → approve → finalise."""
    headers = await get_auth_headers(client)

    # ── 1. Create project ───────────────────────────────────────────────────
    project_resp = await client.post("/api/projects", json=PROJECT, headers=headers)
    assert project_resp.status_code == 201, project_resp.text
    project_id = project_resp.json()["id"]

    # ── 2. Upload claim 1 (deep mode) ──────────────────────────────────────
    claim_1_id = await _upload_claim_deep_mode(client, project_id, CLAIM_1_PATH, headers)
    assert claim_1_id is not None

    # Verify claim 1 item count
    claim_1_resp = await client.get(
        f"/api/projects/{project_id}/claims/{claim_1_id}", headers=headers,
    )
    assert claim_1_resp.status_code == 200
    assert len(claim_1_resp.json()["line_items"]) == EXPECTED_CLAIM_ITEM_COUNT

    # ── 3. Get assessment 1 and approve items to match PR1 ─────────────────
    assessment_1_resp = await client.get(
        f"/api/projects/{project_id}/assessments/by-claim/{claim_1_id}", headers=headers,
    )
    assert assessment_1_resp.status_code == 200
    assessment_1 = assessment_1_resp.json()
    assessment_1_id = assessment_1["id"]

    await _approve_assessment_1(client, project_id, assessment_1_id, assessment_1, headers)

    # ── 4. Finalise assessment 1 ───────────────────────────────────────────
    finalise_resp = await client.post(
        f"/api/projects/{project_id}/assessments/{assessment_1_id}/finalise",
        headers=headers,
    )
    assert finalise_resp.status_code == 200, finalise_resp.text
    finalised_1 = finalise_resp.json()

    # Verify finalised assessment 1 totals
    _assert_decimal_eq(
        finalised_1["total_recommended"],
        ASSESSMENT_1_EXPECTED["total_recommended"],
        "Assessment1.total_recommended",
    )
    _assert_decimal_eq(
        finalised_1["total_retention"],
        ASSESSMENT_1_EXPECTED["total_retention"],
        "Assessment1.total_retention",
    )
    _assert_decimal_eq(
        finalised_1["total_payment_to_date"],
        ASSESSMENT_1_EXPECTED["total_payment_to_date"],
        "Assessment1.total_payment_to_date",
    )
    _assert_decimal_eq(
        finalised_1["recommended_this_period"],
        ASSESSMENT_1_EXPECTED["recommended_this_period"],
        "Assessment1.recommended_this_period",
    )
    assert finalised_1["status"] == "finalised"

    print(f"\n  Assessment 1 finalised: total_recommended={finalised_1['total_recommended']}, "
          f"total_payment_to_date={finalised_1['total_payment_to_date']}")

    # ── 5. Upload claim 2 (deep mode) ──────────────────────────────────────
    claim_2_id = await _upload_claim_deep_mode(client, project_id, CLAIM_2_PATH, headers)
    assert claim_2_id is not None

    # Verify claim 2 item count
    claim_2_resp = await client.get(
        f"/api/projects/{project_id}/claims/{claim_2_id}", headers=headers,
    )
    assert claim_2_resp.status_code == 200
    claim_2 = claim_2_resp.json()
    claim_2_items = claim_2["line_items"]
    assert len(claim_2_items) == EXPECTED_CLAIM_2_ITEM_COUNT, (
        f"Expected {EXPECTED_CLAIM_2_ITEM_COUNT} claim 2 items, got {len(claim_2_items)}"
    )

    # ── 6. Verify claim 2 line items ───────────────────────────────────────
    actual_by_key = {}
    for li in claim_2_items:
        key = (li["item_type"], li.get("ref_code"))
        actual_by_key[key] = li

    print(f"\n  Claim 2 line items ({len(claim_2_items)}):")
    for li in sorted(claim_2_items, key=lambda x: (x["item_type"], x.get("ref_code", ""))):
        print(f"    ({li['item_type']}, {li.get('ref_code')}) {li['description']}  "
              f"value={li['contract_value']} ptd={li['ptd']} prev={li['previous']} curr={li['current']}")

    for expected in EXPECTED_CLAIM_2_LINE_ITEMS:
        key = (expected["item_type"], expected["ref_code"])
        actual = actual_by_key.get(key)
        assert actual is not None, (
            f"Missing claim 2 item: {key} ({expected['description']})"
        )
        label = f"Claim2[{key}]"
        _assert_decimal_eq(actual["contract_value"], expected["contract_value"], f"{label}.contract_value")
        _assert_decimal_eq(actual["ptd"], expected["ptd"], f"{label}.ptd")
        _assert_decimal_eq(actual["previous"], expected["previous"], f"{label}.previous")
        _assert_decimal_eq(actual["current"], expected["current"], f"{label}.current")
        _assert_decimal_eq(actual["balance"], expected["balance"], f"{label}.balance")

    # ── 7. Get assessment 2 and verify auto-created values ─────────────────
    assessment_2_resp = await client.get(
        f"/api/projects/{project_id}/assessments/by-claim/{claim_2_id}", headers=headers,
    )
    assert assessment_2_resp.status_code == 200
    assessment_2 = assessment_2_resp.json()
    assessment_2_id = assessment_2["id"]

    # Verify previously_certified comes from PR1
    _assert_decimal_eq(
        assessment_2["previously_certified"],
        ASSESSMENT_1_EXPECTED["total_payment_to_date"],
        "Assessment2.previously_certified",
    )

    # ── 7a. Verify assessment 2 line items (history + per-item) ────────────
    assessment_2_items = assessment_2["line_items"]
    assert len(assessment_2_items) == EXPECTED_ASSESSMENT_2_LINE_ITEM_COUNT, (
        f"Expected {EXPECTED_ASSESSMENT_2_LINE_ITEM_COUNT} assessment 2 items, "
        f"got {len(assessment_2_items)}"
    )

    # Separate history carrier rows from per-claim-item rows
    history_rows = [li for li in assessment_2_items if li.get("claim_line_item_id") is None]
    per_item_rows = [li for li in assessment_2_items if li.get("claim_line_item_id") is not None]

    print(f"\n  Assessment 2 line items ({len(assessment_2_items)}):")
    for ali in sorted(assessment_2_items, key=lambda x: x.get("sort_order", 0)):
        cli_tag = "H" if ali.get("claim_line_item_id") is None else "I"
        print(f"    [{ali.get('sort_order')}:{cli_tag}] {ali['description']}  "
              f"claimed={ali['contractor_claim_to_date']} "
              f"recommended={ali['total_recommended']} prev_paid={ali['previously_paid']} "
              f"this_period={ali['recommended_this_period']} status={ali['status']}")

    # -- Check history carrier rows (deterministic, exact values) --
    assert len(history_rows) == EXPECTED_HISTORY_ROW_COUNT, (
        f"Expected {EXPECTED_HISTORY_ROW_COUNT} history rows, got {len(history_rows)}"
    )

    actual_history_by_key = {}
    for ali in history_rows:
        key = (ali["description"], ali["sort_order"])
        actual_history_by_key[key] = ali

    for expected in EXPECTED_ASSESSMENT_2_HISTORY_ROWS:
        desc = expected["description"]
        key = (desc, expected["sort_order"])
        actual = actual_history_by_key.get(key)
        assert actual is not None, f"Missing history row: '{desc}' (sort_order={expected['sort_order']})"
        label = f"History[{desc}@{expected['sort_order']}]"
        _assert_decimal_eq(actual["contractor_claim_to_date"], expected["contractor_claim_to_date"], f"{label}.contractor_claim_to_date")
        _assert_decimal_eq(actual["total_recommended"], expected["total_recommended"], f"{label}.total_recommended")
        _assert_decimal_eq(actual["previously_paid"], expected["previously_paid"], f"{label}.previously_paid")
        _assert_decimal_eq(actual["recommended_this_period"], expected["recommended_this_period"], f"{label}.recommended_this_period")
        assert actual["status"] == expected["status"], f"{label}.status: expected {expected['status']}, got {actual['status']}"
        assert actual.get("claim_line_item_id") is None, f"{label}: history row should have claim_line_item_id=null"

    # -- Check per-claim-item rows (self-consistent with claim line items) --
    contract_work_items = [li for li in claim_2_items if li["item_type"] == "contract_work"]
    assert len(per_item_rows) == len(contract_work_items), (
        f"Expected {len(contract_work_items)} per-item rows, got {len(per_item_rows)}"
    )

    # Build claim line item lookup by ID
    cli_by_id = {li["id"]: li for li in claim_2_items}

    for row in per_item_rows:
        cli_id = row["claim_line_item_id"]
        cli = cli_by_id.get(cli_id)
        assert cli is not None, f"Per-item row references unknown claim_line_item_id={cli_id}"
        label = f"PerItem[{row['description']}@{row['sort_order']}]"
        # Per-item rows have previously_paid=0
        _assert_decimal_eq(row["previously_paid"], "0.00", f"{label}.previously_paid")
        # Values must match the linked claim line item's current amount
        expected_current = cli["current"]
        _assert_decimal_eq(row["contractor_claim_to_date"], expected_current, f"{label}.contractor_claim_to_date vs cli.current")
        _assert_decimal_eq(row["recommended_this_period"], expected_current, f"{label}.recommended_this_period vs cli.current")
        # Status: unapproved if current > 0, approved if current = 0
        if _d(expected_current) > 0:
            assert row["status"] == "unapproved", f"{label}.status: expected unapproved for current={expected_current}"
        else:
            assert row["status"] == "approved", f"{label}.status: expected approved for current=0"

    # ── 7b. Verify assessment 2 provisional sum items ─────────────────────
    assessment_2_ps = assessment_2.get("provisional_sum_items", [])
    assert len(assessment_2_ps) == EXPECTED_ASSESSMENT_2_PS_COUNT, (
        f"Expected {EXPECTED_ASSESSMENT_2_PS_COUNT} PS items, got {len(assessment_2_ps)}"
    )

    ps_history = [ps for ps in assessment_2_ps if ps.get("claim_line_item_id") is None]
    ps_per_item = [ps for ps in assessment_2_ps if ps.get("claim_line_item_id") is not None]

    print(f"\n  Assessment 2 PS items ({len(assessment_2_ps)}):")
    for ps in assessment_2_ps:
        cli_tag = "H" if ps.get("claim_line_item_id") is None else "I"
        print(f"    [{cli_tag}] claimed={ps['contractor_claim_to_date']} recommended={ps['total_recommended']} "
              f"prev_paid={ps['previously_paid']} this_period={ps['recommended_this_period']} "
              f"status={ps['status']}")

    # -- Check PS history rows (exact) --
    assert len(ps_history) == len(EXPECTED_ASSESSMENT_2_PS_HISTORY), (
        f"Expected {len(EXPECTED_ASSESSMENT_2_PS_HISTORY)} PS history rows, got {len(ps_history)}"
    )

    for expected in EXPECTED_ASSESSMENT_2_PS_HISTORY:
        # Match by contractor_claim_to_date (unique among history rows)
        actual = next(
            (ps for ps in ps_history
             if _d(ps["contractor_claim_to_date"]) == _d(expected["contractor_claim_to_date"])),
            None,
        )
        assert actual is not None, f"Missing PS history row with claimed={expected['contractor_claim_to_date']}"
        label = f"PSHistory[claimed={expected['contractor_claim_to_date']}]"
        _assert_decimal_eq(actual["total_recommended"], expected["total_recommended"], f"{label}.total_recommended")
        _assert_decimal_eq(actual["previously_paid"], expected["previously_paid"], f"{label}.previously_paid")
        _assert_decimal_eq(actual["recommended_this_period"], expected["recommended_this_period"], f"{label}.recommended_this_period")
        assert actual["status"] == expected["status"], f"{label}.status: expected {expected['status']}, got {actual['status']}"

    # -- Check PS per-item rows (self-consistent) --
    ps_claim_items = [li for li in claim_2_items if li["item_type"] == "provisional_sum"]
    assert len(ps_per_item) == len(ps_claim_items), (
        f"Expected {len(ps_claim_items)} PS per-item rows, got {len(ps_per_item)}"
    )

    for row in ps_per_item:
        cli = cli_by_id.get(row["claim_line_item_id"])
        assert cli is not None, f"PS per-item row references unknown claim_line_item_id={row['claim_line_item_id']}"
        label = f"PSItem[cli={row['claim_line_item_id'][:8]}]"
        _assert_decimal_eq(row["previously_paid"], "0.00", f"{label}.previously_paid")
        _assert_decimal_eq(row["contractor_claim_to_date"], cli["current"], f"{label}.contractor_claim_to_date vs cli.current")
        _assert_decimal_eq(row["recommended_this_period"], cli["current"], f"{label}.recommended_this_period vs cli.current")

    # ── 7c. Verify assessment 2 variation items ──────────────────────────
    assessment_2_vars = assessment_2.get("variation_items", [])
    assert len(assessment_2_vars) == EXPECTED_ASSESSMENT_2_VAR_COUNT, (
        f"Expected {EXPECTED_ASSESSMENT_2_VAR_COUNT} variation items, got {len(assessment_2_vars)}"
    )

    var_history = [v for v in assessment_2_vars if v.get("claim_line_item_id") is None]
    var_per_item = [v for v in assessment_2_vars if v.get("claim_line_item_id") is not None]

    print(f"\n  Assessment 2 variation items ({len(assessment_2_vars)}):")
    for var in sorted(assessment_2_vars, key=lambda x: x.get("contractor_ref", "")):
        cli_tag = "H" if var.get("claim_line_item_id") is None else "I"
        print(f"    [{cli_tag}] ref={var['contractor_ref']} claimed={var['contractor_claim_to_date']} "
              f"recommended={var['total_recommended']} prev_paid={var['previously_paid']} "
              f"this_period={var['recommended_this_period']} status={var['status']}")

    # -- Check variation history rows (exact) --
    assert len(var_history) == len(EXPECTED_ASSESSMENT_2_VAR_HISTORY), (
        f"Expected {len(EXPECTED_ASSESSMENT_2_VAR_HISTORY)} variation history rows, got {len(var_history)}"
    )

    actual_var_history_by_ref = {v["contractor_ref"]: v for v in var_history}
    for expected in EXPECTED_ASSESSMENT_2_VAR_HISTORY:
        ref = expected["contractor_ref"]
        actual = actual_var_history_by_ref.get(ref)
        assert actual is not None, f"Missing variation history row for ref={ref}"
        label = f"VarHistory[ref={ref}]"
        _assert_decimal_eq(actual["contractor_claim_to_date"], expected["contractor_claim_to_date"], f"{label}.contractor_claim_to_date")
        _assert_decimal_eq(actual["total_recommended"], expected["total_recommended"], f"{label}.total_recommended")
        _assert_decimal_eq(actual["previously_paid"], expected["previously_paid"], f"{label}.previously_paid")
        _assert_decimal_eq(actual["recommended_this_period"], expected["recommended_this_period"], f"{label}.recommended_this_period")
        assert actual["status"] == expected["status"], f"{label}.status: expected {expected['status']}, got {actual['status']}"

    # -- Check variation per-item rows (self-consistent) --
    var_claim_items = [li for li in claim_2_items if li["item_type"] == "variation"]
    assert len(var_per_item) == len(var_claim_items), (
        f"Expected {len(var_claim_items)} variation per-item rows, got {len(var_per_item)}"
    )

    for row in var_per_item:
        cli = cli_by_id.get(row["claim_line_item_id"])
        assert cli is not None, f"Var per-item row references unknown claim_line_item_id={row['claim_line_item_id']}"
        label = f"VarItem[ref={row['contractor_ref']}]"
        _assert_decimal_eq(row["previously_paid"], "0.00", f"{label}.previously_paid")
        _assert_decimal_eq(row["contractor_claim_to_date"], cli["current"], f"{label}.contractor_claim_to_date vs cli.current")
        _assert_decimal_eq(row["recommended_this_period"], cli["current"], f"{label}.recommended_this_period vs cli.current")
        if _d(cli["current"]) > 0:
            assert row["status"] == "unapproved", f"{label}.status: expected unapproved for current={cli['current']}"
        else:
            assert row["status"] == "approved", f"{label}.status: expected approved for current=0"

    # ── 7d. Verify aggregated groups are present ──────────────────────────────
    wbs_groups = assessment_2.get("wbs_groups", [])
    assert len(wbs_groups) > 0, "Expected wbs_groups in response"

    # Each WBS group should have contract_sum from master record
    for wg in wbs_groups:
        assert "contract_sum" in wg, "WBS group missing contract_sum"
        assert "total_recommended" in wg, "WBS group missing total_recommended"
        assert "history_row" in wg or "child_rows" in wg, "WBS group missing row data"

    var_groups = assessment_2.get("variation_groups", [])
    ps_groups_resp = assessment_2.get("ps_groups", [])

    # ── 8. Approve assessment 2 items (QS adjustments for PR2) ─────────────
    # Contract work and PS items: accept at auto values (approve unapproved ones)
    for li in assessment_2["line_items"]:
        if li["status"] == "unapproved":
            await client.patch(
                f"/api/projects/{project_id}/assessments/{assessment_2_id}/line-items/{li['id']}",
                json={
                    "total_recommended": li["total_recommended"],
                    "status": "approved",
                },
                headers=headers,
            )

    for ps in assessment_2.get("provisional_sum_items", []):
        if ps["status"] == "unapproved":
            await client.patch(
                f"/api/projects/{project_id}/assessments/{assessment_2_id}/provisional-sum-items/{ps['id']}",
                json={
                    "total_recommended": ps["total_recommended"],
                    "status": "approved",
                },
                headers=headers,
            )

    # Variations: approve at auto values except var 3 which gets QS reduction.
    # PR2_VAR3_RECOMMENDED is the cumulative total (34434.17). The history row
    # already holds previously_paid=5238.02, so the per-item row gets the remainder.
    var3_history_prev = next(
        (_d(v["previously_paid"]) for v in assessment_2.get("variation_items", [])
         if v["contractor_ref"] == "3" and v.get("claim_line_item_id") is None),
        Decimal("0"),
    )
    var3_per_item_recommended = str(_d(PR2_VAR3_RECOMMENDED) - var3_history_prev)

    for var in assessment_2.get("variation_items", []):
        if var["status"] == "unapproved":
            recommended = var["total_recommended"]
            if var["contractor_ref"] == "3":
                recommended = var3_per_item_recommended
            await client.patch(
                f"/api/projects/{project_id}/assessments/{assessment_2_id}/variation-items/{var['id']}",
                json={
                    "total_recommended": recommended,
                    "status": "approved",
                },
                headers=headers,
            )

    # ── 9. Finalise assessment 2 ───────────────────────────────────────────
    finalise_2_resp = await client.post(
        f"/api/projects/{project_id}/assessments/{assessment_2_id}/finalise",
        headers=headers,
    )
    assert finalise_2_resp.status_code == 200, finalise_2_resp.text
    finalised_2 = finalise_2_resp.json()

    assert finalised_2["status"] == "finalised"

    # ── 10. Verify finalised assessment 2 totals ───────────────────────────
    _assert_decimal_eq(
        finalised_2["contract_sum"],
        ASSESSMENT_2_EXPECTED["contract_sum"],
        "Assessment2.contract_sum",
    )
    _assert_decimal_eq(
        finalised_2["total_recommended"],
        ASSESSMENT_2_EXPECTED["total_recommended"],
        "Assessment2.total_recommended",
    )
    _assert_decimal_eq(
        finalised_2["total_retention"],
        ASSESSMENT_2_EXPECTED["total_retention"],
        "Assessment2.total_retention",
    )
    _assert_decimal_eq(
        finalised_2["total_payment_to_date"],
        ASSESSMENT_2_EXPECTED["total_payment_to_date"],
        "Assessment2.total_payment_to_date",
    )
    _assert_decimal_eq(
        finalised_2["previously_certified"],
        ASSESSMENT_2_EXPECTED["previously_certified"],
        "Assessment2.previously_certified",
    )
    _assert_decimal_eq(
        finalised_2["recommended_this_period"],
        ASSESSMENT_2_EXPECTED["recommended_this_period"],
        "Assessment2.recommended_this_period",
    )

    # ── Summary ─────────────────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print(f"  E2E Second Claim Test PASSED")
    print(f"  Project:          {project_id}")
    print(f"  Claim 1:          {claim_1_id}")
    print(f"  Assessment 1:     {assessment_1_id} (finalised)")
    print(f"    total_recommended:   {finalised_1['total_recommended']}")
    print(f"    total_payment_to_date: {finalised_1['total_payment_to_date']}")
    print(f"  Claim 2:          {claim_2_id} ({len(claim_2_items)} items)")
    print(f"  Assessment 2:     {assessment_2_id} (finalised)")
    print(f"    total_recommended:   {finalised_2['total_recommended']}")
    print(f"    total_retention:     {finalised_2['total_retention']}")
    print(f"    total_payment_to_date: {finalised_2['total_payment_to_date']}")
    print(f"    previously_certified:  {finalised_2['previously_certified']}")
    print(f"    recommended_this_period: {finalised_2['recommended_this_period']}")
    print(f"{'='*60}")
