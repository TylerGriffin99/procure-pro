"""
E2E test: Paparoa Fire Station — non-WBPRO (generic format) single claim.

Uploads the Paparoa Fire Station PC01 claim PDF (generic format),
verifies it flows through the full 7-phase harness pipeline including
LLM-based extraction, auto-approves all items, finalises, and verifies
financial consistency.

Usage:
    cd backend
    python -m pytest tests/e2e/test_e2e_paparoa.py -v -x -s --timeout=600

Requires:
  - LLM_PROVIDER and matching API key set in environment
  - Paparoa PDF in claim/Paparoa/
"""
from decimal import Decimal
from pathlib import Path

import pytest
from httpx import AsyncClient

from tests.e2e.fixtures.paparoa_claim1 import (
    PROJECT,
    EXPECTED_CLAIM_NUMBER,
    EXPECTED_CONTRACT_WORK_MIN,
    EXPECTED_PROVISIONAL_SUM_MIN,
    EXPECTED_VARIATION_MIN,
)
from tests.e2e.helpers import (
    _d,
    auto_approve_assessment,
    get_auth_headers,
    upload_claim_deep_mode,
)

CLAIM_PDF = (
    Path(__file__).parent.parent.parent.parent
    / "claim"
    / "Paparoa"
    / "Paparoa Fire Station PC01 AUG25.pdf"
)

ZERO = Decimal("0")


@pytest.mark.paparoa
@pytest.mark.skipif(
    not CLAIM_PDF.exists(),
    reason="Paparoa claim PDF not available",
)
@pytest.mark.asyncio
async def test_paparoa_generic_format_single_claim(client: AsyncClient):
    """Process a non-WBPRO claim through the full pipeline."""
    headers = await get_auth_headers(client)

    # ── 1. Create project ──────────────────────────────────────────────────
    project_resp = await client.post("/api/projects", json=PROJECT, headers=headers)
    assert project_resp.status_code == 201, project_resp.text
    project_id = project_resp.json()["id"]
    print(f"\n  Project created: {project_id}")

    # ── 2. Upload and parse (triggers full 7-phase harness) ────────────────
    claim_id = await upload_claim_deep_mode(client, project_id, CLAIM_PDF, headers)
    assert claim_id is not None, "Upload returned no claim_id"
    print(f"  Claim parsed: {claim_id}")

    # ── 3. Verify claim number ─────────────────────────────────────────────
    claim_resp = await client.get(
        f"/api/projects/{project_id}/claims/{claim_id}", headers=headers,
    )
    assert claim_resp.status_code == 200
    claim = claim_resp.json()
    assert claim["claim_number"] == EXPECTED_CLAIM_NUMBER, (
        f"Expected claim_number={EXPECTED_CLAIM_NUMBER}, got {claim['claim_number']}"
    )

    # ── 4. Get assessment ──────────────────────────────────────────────────
    assessment_resp = await client.get(
        f"/api/projects/{project_id}/assessments/by-claim/{claim_id}", headers=headers,
    )
    assert assessment_resp.status_code == 200
    assessment = assessment_resp.json()
    assessment_id = assessment["id"]

    # First claim — previously_certified must be zero
    assert _d(assessment["previously_certified"]) == ZERO, (
        f"First claim: previously_certified should be 0, got {assessment['previously_certified']}"
    )

    # ── 5. Verify assessment line items (contract works) ───────────────────
    actual_lis = assessment["line_items"]
    assert len(actual_lis) >= EXPECTED_CONTRACT_WORK_MIN, (
        f"Expected at least {EXPECTED_CONTRACT_WORK_MIN} assessment LIs, got {len(actual_lis)}"
    )

    # Verify some items have non-zero claims (LLM should extract claimed values)
    nonzero_lis = [li for li in actual_lis if _d(li["contractor_claim_to_date"]) != ZERO]
    assert len(nonzero_lis) >= 1, (
        "Expected at least 1 assessment LI with non-zero contractor_claim_to_date"
    )
    print(f"  Assessment LIs: {len(actual_lis)} total, {len(nonzero_lis)} with claims")

    # ── 6. Verify provisional sums and variations exist ────────────────────
    actual_ps = assessment.get("provisional_sum_items", [])
    actual_vars = assessment.get("variation_items", [])

    assert len(actual_ps) >= EXPECTED_PROVISIONAL_SUM_MIN, (
        f"Expected at least {EXPECTED_PROVISIONAL_SUM_MIN} PS items, got {len(actual_ps)}"
    )
    assert len(actual_vars) >= EXPECTED_VARIATION_MIN, (
        f"Expected at least {EXPECTED_VARIATION_MIN} variation items, got {len(actual_vars)}"
    )
    print(f"  PS items: {len(actual_ps)}, Variation items: {len(actual_vars)}")

    # ── 7. Auto-approve all items ──────────────────────────────────────────
    await auto_approve_assessment(client, project_id, assessment_id, assessment, headers)
    print("  All items auto-approved")

    # ── 8. Finalise ────────────────────────────────────────────────────────
    finalise_resp = await client.post(
        f"/api/projects/{project_id}/assessments/{assessment_id}/finalise",
        headers=headers,
    )
    assert finalise_resp.status_code == 200, f"Finalise failed: {finalise_resp.text}"
    finalised = finalise_resp.json()
    assert finalised["status"] == "finalised", (
        f"Expected status=finalised, got {finalised['status']}"
    )

    # ── 9. Verify contract_sum matches project ─────────────────────────────
    assert _d(finalised["contract_sum"]) == _d(PROJECT["contract_sum"]), (
        f"contract_sum: expected {PROJECT['contract_sum']}, got {finalised['contract_sum']}"
    )

    # ── 10. Verify internal financial consistency ──────────────────────────
    # total_payment_to_date = total_recommended - total_retention
    computed_ptd = _d(finalised["total_recommended"]) - _d(finalised["total_retention"])
    assert computed_ptd == _d(finalised["total_payment_to_date"]), (
        f"total_recommended({finalised['total_recommended']}) "
        f"- total_retention({finalised['total_retention']}) "
        f"= {computed_ptd}, but total_payment_to_date={finalised['total_payment_to_date']}"
    )

    # recommended_this_period = total_payment_to_date - previously_certified
    computed_rtp = _d(finalised["total_payment_to_date"]) - _d(finalised["previously_certified"])
    assert computed_rtp == _d(finalised["recommended_this_period"]), (
        f"total_payment_to_date({finalised['total_payment_to_date']}) "
        f"- previously_certified({finalised['previously_certified']}) "
        f"= {computed_rtp}, but recommended_this_period={finalised['recommended_this_period']}"
    )

    # total_recommended must be positive (contractor claimed non-zero amounts)
    assert _d(finalised["total_recommended"]) > ZERO, (
        f"total_recommended should be positive, got {finalised['total_recommended']}"
    )

    # total_retention must be non-negative
    assert _d(finalised["total_retention"]) >= ZERO, (
        f"total_retention should be non-negative, got {finalised['total_retention']}"
    )

    print(f"\n{'='*60}")
    print(f"  PAPAROA E2E TEST PASSED (generic format)")
    print(f"  Finalised: total_recommended={finalised['total_recommended']}, "
          f"payment_to_date={finalised['total_payment_to_date']}, "
          f"this_period={finalised['recommended_this_period']}")
    print(f"{'='*60}")
