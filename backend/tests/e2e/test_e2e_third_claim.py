"""
E2E integration test: third claim upload after finalised first and second claims.

Verifies that previously_paid values carry forward correctly through two
finalised assessments, and that all totals match expected PR3 values.

Requires:
  - Test DB running on localhost:6000
  - LLM_PROVIDER and matching API key set in environment
  - claim/Gilmours/claims/Gilmours Central_Progress Claim No. 1.pdf present
  - claim/Gilmours/claims/Gilmours Central_Progress Claim No. 2.pdf present
  - claim/Gilmours/claims/Gilmours Central_Progress Claim No. 3.pdf present
"""
from decimal import Decimal
from pathlib import Path

import pytest
from httpx import AsyncClient

from tests.e2e.fixtures.gilmours_claim1 import (
    EXPECTED_CLAIM_ITEM_COUNT,
    PROJECT,
)
from tests.e2e.fixtures.gilmours_claim2 import (
    ASSESSMENT_1_EXPECTED,
    EXPECTED_CLAIM_2_ITEM_COUNT,
    PR1_CONTRACT_WORK_APPROVALS,
    PR1_PS_RECOMMENDED,
    PR2_VAR3_RECOMMENDED,
)
from tests.e2e.fixtures.gilmours_claim3 import (
    ASSESSMENT_2_EXPECTED,
    ASSESSMENT_3_EXPECTED,
    EXPECTED_ASSESSMENT_3_LINE_ITEM_COUNT,
    EXPECTED_ASSESSMENT_3_LINE_ITEMS,
    EXPECTED_ASSESSMENT_3_PS_COUNT,
    EXPECTED_ASSESSMENT_3_PS_ITEMS,
    EXPECTED_ASSESSMENT_3_VAR_COUNT,
    EXPECTED_ASSESSMENT_3_VAR_ITEMS,
    EXPECTED_CLAIM_3_ITEM_COUNT,
    EXPECTED_CLAIM_3_LINE_ITEMS,
    PR3_VAR11_RECOMMENDED,
    PR3_VAR12_RECOMMENDED,
    PR3_VAR15_RECOMMENDED,
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
CLAIM_3_PATH = (
    Path(__file__).parent.parent.parent.parent
    / "claim"
    / "Gilmours"
    / "claims"
    / "Gilmours Central_Progress Claim No. 3.pdf"
)


async def _approve_assessment_1(
    client: AsyncClient, project_id: str, assessment_id: str, assessment: dict, headers: dict,
):
    """Approve assessment 1 items to match PR1 values."""
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
                await client.patch(
                    f"/api/projects/{project_id}/assessments/{assessment_id}/line-items/{li['id']}",
                    json={
                        "total_recommended": li["contractor_claim_to_date"],
                        "status": "approved",
                    },
                    headers=headers,
                )

    for ps in assessment.get("provisional_sum_items", []):
        if ps["status"] == "unapproved":
            if _d(ps["contractor_claim_to_date"]) > 0:
                await client.patch(
                    f"/api/projects/{project_id}/assessments/{assessment_id}/provisional-sum-items/{ps['id']}",
                    json={
                        "total_recommended": PR1_PS_RECOMMENDED,
                        "status": "approved",
                    },
                    headers=headers,
                )

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


async def _approve_assessment_2(
    client: AsyncClient, project_id: str, assessment_id: str, assessment: dict, headers: dict,
):
    """Approve assessment 2 items to match PR2 values."""
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
            recommended = var["total_recommended"]
            if var["contractor_ref"] == "3":
                recommended = PR2_VAR3_RECOMMENDED
            await client.patch(
                f"/api/projects/{project_id}/assessments/{assessment_id}/variation-items/{var['id']}",
                json={
                    "total_recommended": recommended,
                    "status": "approved",
                },
                headers=headers,
            )


@pytest.mark.skipif(
    not (CLAIM_1_PATH.exists() and CLAIM_2_PATH.exists() and CLAIM_3_PATH.exists()),
    reason="Sample PDFs not available",
)
@pytest.mark.asyncio
async def test_third_claim_e2e(client: AsyncClient):
    """Full pipeline: claim 1 -> approve -> finalise -> claim 2 -> approve -> finalise -> claim 3 -> verify -> approve -> finalise."""
    headers = await get_auth_headers(client)

    # == 1. Create project ==================================================
    project_resp = await client.post("/api/projects", json=PROJECT, headers=headers)
    assert project_resp.status_code == 201, project_resp.text
    project_id = project_resp.json()["id"]

    # == 2. Upload claim 1 (deep mode) ======================================
    claim_1_id = await _upload_claim_deep_mode(client, project_id, CLAIM_1_PATH, headers)
    assert claim_1_id is not None

    claim_1_resp = await client.get(
        f"/api/projects/{project_id}/claims/{claim_1_id}", headers=headers,
    )
    assert claim_1_resp.status_code == 200
    assert len(claim_1_resp.json()["line_items"]) == EXPECTED_CLAIM_ITEM_COUNT

    # == 3. Approve and finalise assessment 1 ===============================
    assessment_1_resp = await client.get(
        f"/api/projects/{project_id}/assessments/by-claim/{claim_1_id}", headers=headers,
    )
    assert assessment_1_resp.status_code == 200
    assessment_1 = assessment_1_resp.json()
    assessment_1_id = assessment_1["id"]

    await _approve_assessment_1(client, project_id, assessment_1_id, assessment_1, headers)

    finalise_1_resp = await client.post(
        f"/api/projects/{project_id}/assessments/{assessment_1_id}/finalise",
        headers=headers,
    )
    assert finalise_1_resp.status_code == 200, finalise_1_resp.text
    finalised_1 = finalise_1_resp.json()
    assert finalised_1["status"] == "finalised"

    _assert_decimal_eq(
        finalised_1["total_payment_to_date"],
        ASSESSMENT_1_EXPECTED["total_payment_to_date"],
        "Assessment1.total_payment_to_date",
    )

    print(f"\n  Assessment 1 finalised: total_payment_to_date={finalised_1['total_payment_to_date']}")

    # == 4. Upload claim 2 (deep mode) ======================================
    claim_2_id = await _upload_claim_deep_mode(client, project_id, CLAIM_2_PATH, headers)
    assert claim_2_id is not None

    claim_2_resp = await client.get(
        f"/api/projects/{project_id}/claims/{claim_2_id}", headers=headers,
    )
    assert claim_2_resp.status_code == 200
    assert len(claim_2_resp.json()["line_items"]) == EXPECTED_CLAIM_2_ITEM_COUNT

    # == 5. Approve and finalise assessment 2 ===============================
    assessment_2_resp = await client.get(
        f"/api/projects/{project_id}/assessments/by-claim/{claim_2_id}", headers=headers,
    )
    assert assessment_2_resp.status_code == 200
    assessment_2 = assessment_2_resp.json()
    assessment_2_id = assessment_2["id"]

    await _approve_assessment_2(client, project_id, assessment_2_id, assessment_2, headers)

    finalise_2_resp = await client.post(
        f"/api/projects/{project_id}/assessments/{assessment_2_id}/finalise",
        headers=headers,
    )
    assert finalise_2_resp.status_code == 200, finalise_2_resp.text
    finalised_2 = finalise_2_resp.json()
    assert finalised_2["status"] == "finalised"

    _assert_decimal_eq(
        finalised_2["total_recommended"],
        ASSESSMENT_2_EXPECTED["total_recommended"],
        "Assessment2.total_recommended",
    )
    _assert_decimal_eq(
        finalised_2["total_payment_to_date"],
        ASSESSMENT_2_EXPECTED["total_payment_to_date"],
        "Assessment2.total_payment_to_date",
    )

    print(f"\n  Assessment 2 finalised: total_recommended={finalised_2['total_recommended']}, "
          f"total_payment_to_date={finalised_2['total_payment_to_date']}")

    # == 6. Upload claim 3 (deep mode) ======================================
    claim_3_id = await _upload_claim_deep_mode(client, project_id, CLAIM_3_PATH, headers)
    assert claim_3_id is not None

    claim_3_resp = await client.get(
        f"/api/projects/{project_id}/claims/{claim_3_id}", headers=headers,
    )
    assert claim_3_resp.status_code == 200
    claim_3 = claim_3_resp.json()
    claim_3_items = claim_3["line_items"]
    assert len(claim_3_items) == EXPECTED_CLAIM_3_ITEM_COUNT, (
        f"Expected {EXPECTED_CLAIM_3_ITEM_COUNT} claim 3 items, got {len(claim_3_items)}"
    )

    # == 7. Verify claim 3 line items =======================================
    actual_by_key = {}
    for li in claim_3_items:
        key = (li["item_type"], li.get("ref_code"))
        actual_by_key[key] = li

    print(f"\n  Claim 3 line items ({len(claim_3_items)}):")
    for li in sorted(claim_3_items, key=lambda x: (x["item_type"], x.get("ref_code", ""))):
        print(f"    ({li['item_type']}, {li.get('ref_code')}) {li['description']}  "
              f"value={li['contract_value']} ptd={li['ptd']} prev={li['previous']} curr={li['current']}")

    for expected in EXPECTED_CLAIM_3_LINE_ITEMS:
        key = (expected["item_type"], expected["ref_code"])
        actual = actual_by_key.get(key)
        assert actual is not None, (
            f"Missing claim 3 item: {key} ({expected['description']})"
        )
        label = f"Claim3[{key}]"
        _assert_decimal_eq(actual["contract_value"], expected["contract_value"], f"{label}.contract_value")
        _assert_decimal_eq(actual["ptd"], expected["ptd"], f"{label}.ptd")
        _assert_decimal_eq(actual["previous"], expected["previous"], f"{label}.previous")
        _assert_decimal_eq(actual["current"], expected["current"], f"{label}.current")
        _assert_decimal_eq(actual["balance"], expected["balance"], f"{label}.balance")

    # == 8. Get assessment 3 and verify auto-created values =================
    assessment_3_resp = await client.get(
        f"/api/projects/{project_id}/assessments/by-claim/{claim_3_id}", headers=headers,
    )
    assert assessment_3_resp.status_code == 200
    assessment_3 = assessment_3_resp.json()
    assessment_3_id = assessment_3["id"]

    # Verify previously_certified comes from PR2
    _assert_decimal_eq(
        assessment_3["previously_certified"],
        ASSESSMENT_2_EXPECTED["total_payment_to_date"],
        "Assessment3.previously_certified",
    )

    # == 8a. Verify assessment 3 contract work line items ===================
    assessment_3_items = assessment_3["line_items"]
    assert len(assessment_3_items) >= EXPECTED_ASSESSMENT_3_LINE_ITEM_COUNT, (
        f"Expected at least {EXPECTED_ASSESSMENT_3_LINE_ITEM_COUNT} assessment 3 items, "
        f"got {len(assessment_3_items)}"
    )

    print(f"\n  Assessment 3 line items ({len(assessment_3_items)}):")
    for ali in sorted(assessment_3_items, key=lambda x: x.get("sort_order", 0)):
        print(f"    [{ali.get('sort_order')}] {ali['description']}  "
              f"contract_sum={ali['contract_sum']} claimed={ali['contractor_claim_to_date']} "
              f"recommended={ali['total_recommended']} prev_paid={ali['previously_paid']} "
              f"this_period={ali['recommended_this_period']} status={ali['status']}")

    actual_ali_by_key = {}
    for ali in assessment_3_items:
        key = (ali["description"], ali["sort_order"])
        actual_ali_by_key[key] = ali

    for expected in EXPECTED_ASSESSMENT_3_LINE_ITEMS:
        desc = expected["description"]
        key = (desc, expected["sort_order"])
        actual = actual_ali_by_key.get(key)
        assert actual is not None, f"Missing assessment 3 item: '{desc}' (sort_order={expected['sort_order']})"
        label = f"Assessment3[{desc}@{expected['sort_order']}]"
        _assert_decimal_eq(actual["contract_sum"], expected["contract_sum"], f"{label}.contract_sum")
        _assert_decimal_eq(actual["contractor_claim_to_date"], expected["contractor_claim_to_date"], f"{label}.contractor_claim_to_date")
        _assert_decimal_eq(actual["total_recommended"], expected["total_recommended"], f"{label}.total_recommended")
        _assert_decimal_eq(actual["previously_paid"], expected["previously_paid"], f"{label}.previously_paid")
        _assert_decimal_eq(actual["recommended_this_period"], expected["recommended_this_period"], f"{label}.recommended_this_period")
        assert actual["status"] == expected["status"], f"{label}.status: expected {expected['status']}, got {actual['status']}"

    # == 8b. Verify assessment 3 provisional sum items ======================
    assessment_3_ps = assessment_3.get("provisional_sum_items", [])
    assert len(assessment_3_ps) == EXPECTED_ASSESSMENT_3_PS_COUNT, (
        f"Expected {EXPECTED_ASSESSMENT_3_PS_COUNT} PS items, got {len(assessment_3_ps)}"
    )

    actual_ps_sorted = sorted(assessment_3_ps, key=lambda x: _d(x["contractor_claim_to_date"]))
    expected_ps_sorted = sorted(EXPECTED_ASSESSMENT_3_PS_ITEMS, key=lambda x: _d(x["contractor_claim_to_date"]))

    print(f"\n  Assessment 3 PS items ({len(assessment_3_ps)}):")
    for ps in actual_ps_sorted:
        print(f"    claimed={ps['contractor_claim_to_date']} recommended={ps['total_recommended']} "
              f"prev_paid={ps['previously_paid']} this_period={ps['recommended_this_period']} "
              f"status={ps['status']}")

    for i, (actual, expected) in enumerate(zip(actual_ps_sorted, expected_ps_sorted)):
        label = f"PS3[{i}]"
        _assert_decimal_eq(actual["contractor_claim_to_date"], expected["contractor_claim_to_date"], f"{label}.contractor_claim_to_date")
        _assert_decimal_eq(actual["total_recommended"], expected["total_recommended"], f"{label}.total_recommended")
        _assert_decimal_eq(actual["previously_paid"], expected["previously_paid"], f"{label}.previously_paid")
        _assert_decimal_eq(actual["recommended_this_period"], expected["recommended_this_period"], f"{label}.recommended_this_period")
        assert actual["status"] == expected["status"], f"{label}.status: expected {expected['status']}, got {actual['status']}"

    # == 8c. Verify assessment 3 variation items ============================
    assessment_3_vars = assessment_3.get("variation_items", [])
    assert len(assessment_3_vars) == EXPECTED_ASSESSMENT_3_VAR_COUNT, (
        f"Expected {EXPECTED_ASSESSMENT_3_VAR_COUNT} variation items, got {len(assessment_3_vars)}"
    )

    actual_vars_by_ref = {v["contractor_ref"]: v for v in assessment_3_vars}

    print(f"\n  Assessment 3 variation items ({len(assessment_3_vars)}):")
    for var in sorted(assessment_3_vars, key=lambda x: x.get("contractor_ref", "")):
        print(f"    ref={var['contractor_ref']} claimed={var['contractor_claim_to_date']} "
              f"recommended={var['total_recommended']} prev_paid={var['previously_paid']} "
              f"this_period={var['recommended_this_period']} status={var['status']}")

    for expected in EXPECTED_ASSESSMENT_3_VAR_ITEMS:
        ref = expected["contractor_ref"]
        actual = actual_vars_by_ref.get(ref)
        assert actual is not None, f"Missing variation item with ref={ref}"
        label = f"Var3[ref={ref}]"
        _assert_decimal_eq(actual["contractor_claim_to_date"], expected["contractor_claim_to_date"], f"{label}.contractor_claim_to_date")
        _assert_decimal_eq(actual["total_recommended"], expected["total_recommended"], f"{label}.total_recommended")
        _assert_decimal_eq(actual["previously_paid"], expected["previously_paid"], f"{label}.previously_paid")
        _assert_decimal_eq(actual["recommended_this_period"], expected["recommended_this_period"], f"{label}.recommended_this_period")
        assert actual["status"] == expected["status"], f"{label}.status: expected {expected['status']}, got {actual['status']}"

    # == 9. Approve assessment 3 items (QS adjustments for PR3) =============
    # Contract work items: accept at auto values
    for li in assessment_3["line_items"]:
        if li["status"] == "unapproved":
            await client.patch(
                f"/api/projects/{project_id}/assessments/{assessment_3_id}/line-items/{li['id']}",
                json={
                    "total_recommended": li["total_recommended"],
                    "status": "approved",
                },
                headers=headers,
            )

    # PS items: accept at auto values
    for ps in assessment_3.get("provisional_sum_items", []):
        if ps["status"] == "unapproved":
            await client.patch(
                f"/api/projects/{project_id}/assessments/{assessment_3_id}/provisional-sum-items/{ps['id']}",
                json={
                    "total_recommended": ps["total_recommended"],
                    "status": "approved",
                },
                headers=headers,
            )

    # Variations: accept at auto values except vars 11, 12, 15 which get QS reduction
    pr3_var_reductions = {
        "11": PR3_VAR11_RECOMMENDED,
        "12": PR3_VAR12_RECOMMENDED,
        "15": PR3_VAR15_RECOMMENDED,
    }
    for var in assessment_3.get("variation_items", []):
        if var["status"] == "unapproved":
            recommended = var["total_recommended"]
            if var["contractor_ref"] in pr3_var_reductions:
                recommended = pr3_var_reductions[var["contractor_ref"]]
            await client.patch(
                f"/api/projects/{project_id}/assessments/{assessment_3_id}/variation-items/{var['id']}",
                json={
                    "total_recommended": recommended,
                    "status": "approved",
                },
                headers=headers,
            )

    # == 10. Finalise assessment 3 ==========================================
    finalise_3_resp = await client.post(
        f"/api/projects/{project_id}/assessments/{assessment_3_id}/finalise",
        headers=headers,
    )
    assert finalise_3_resp.status_code == 200, finalise_3_resp.text
    finalised_3 = finalise_3_resp.json()

    assert finalised_3["status"] == "finalised"

    # == 11. Verify finalised assessment 3 totals ===========================
    _assert_decimal_eq(
        finalised_3["contract_sum"],
        ASSESSMENT_3_EXPECTED["contract_sum"],
        "Assessment3.contract_sum",
    )
    _assert_decimal_eq(
        finalised_3["total_recommended"],
        ASSESSMENT_3_EXPECTED["total_recommended"],
        "Assessment3.total_recommended",
    )
    _assert_decimal_eq(
        finalised_3["total_retention"],
        ASSESSMENT_3_EXPECTED["total_retention"],
        "Assessment3.total_retention",
    )
    _assert_decimal_eq(
        finalised_3["total_payment_to_date"],
        ASSESSMENT_3_EXPECTED["total_payment_to_date"],
        "Assessment3.total_payment_to_date",
    )
    _assert_decimal_eq(
        finalised_3["previously_certified"],
        ASSESSMENT_3_EXPECTED["previously_certified"],
        "Assessment3.previously_certified",
    )
    _assert_decimal_eq(
        finalised_3["recommended_this_period"],
        ASSESSMENT_3_EXPECTED["recommended_this_period"],
        "Assessment3.recommended_this_period",
    )

    # == Summary ============================================================
    print(f"\n{'='*60}")
    print(f"  E2E Third Claim Test PASSED")
    print(f"  Project:          {project_id}")
    print(f"  Claim 1:          {claim_1_id}")
    print(f"  Assessment 1:     {assessment_1_id} (finalised)")
    print(f"    total_payment_to_date: {finalised_1['total_payment_to_date']}")
    print(f"  Claim 2:          {claim_2_id}")
    print(f"  Assessment 2:     {assessment_2_id} (finalised)")
    print(f"    total_recommended:   {finalised_2['total_recommended']}")
    print(f"    total_payment_to_date: {finalised_2['total_payment_to_date']}")
    print(f"  Claim 3:          {claim_3_id} ({len(claim_3_items)} items)")
    print(f"  Assessment 3:     {assessment_3_id} (finalised)")
    print(f"    total_recommended:     {finalised_3['total_recommended']}")
    print(f"    total_retention:       {finalised_3['total_retention']}")
    print(f"    total_payment_to_date: {finalised_3['total_payment_to_date']}")
    print(f"    previously_certified:  {finalised_3['previously_certified']}")
    print(f"    recommended_this_period: {finalised_3['recommended_this_period']}")
    print(f"{'='*60}")
