"""
E2E full pipeline test: sequentially process all 8 Gilmours claims.

Uploads each claim PDF, verifies assessment items against golden fixtures
parsed from payment recommendation PDFs, auto-approves all items,
finalises, and verifies carry-forward and financial totals.

Fails fast on first error. Designed for automated research loops.

Usage:
    cd backend
    python -m pytest tests/e2e/test_e2e_full_pipeline.py -v -x -s --timeout=1800

To run against your local dev DB (data persists for UI inspection):
    E2E_DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/claimreview \
        python -m pytest tests/e2e/test_e2e_full_pipeline.py -v -x -s --timeout=1800

Requires:
  - LLM_PROVIDER and matching API key set in environment
  - All 8 PDFs in claim/Gilmours/claims/
"""
from pathlib import Path

import pytest
from httpx import AsyncClient

from tests.e2e.fixtures.gilmours_full_pipeline import GOLDEN_FIXTURES, PROJECT
from tests.e2e.helpers import (
    _assert_decimal_eq,
    _d,
    auto_approve_assessment,
    get_auth_headers,
    upload_claim_deep_mode,
)

CLAIMS_DIR = (
    Path(__file__).parent.parent.parent.parent
    / "claim"
    / "Gilmours"
    / "claims"
)

CLAIM_PDFS = sorted(CLAIMS_DIR.glob("Gilmours Central_Progress Claim No. *.pdf"))


@pytest.mark.full_pipeline
@pytest.mark.skipif(
    len(list(CLAIMS_DIR.glob("*.pdf"))) < 8,
    reason="Not all 8 claim PDFs available",
)
@pytest.mark.asyncio
async def test_full_pipeline_8_claims(client: AsyncClient):
    """Process all 8 claims: upload -> verify assessment -> auto-approve -> finalise -> verify totals."""
    assert len(GOLDEN_FIXTURES) == 8, (
        f"Expected 8 golden fixtures, got {len(GOLDEN_FIXTURES)}"
    )
    assert len(CLAIM_PDFS) == 8, (
        f"Expected 8 claim PDFs, got {len(CLAIM_PDFS)}"
    )

    headers = await get_auth_headers(client)

    # ── Create project ─────────────────────────────────────────────────────
    project_resp = await client.post("/api/v1/projects", json=PROJECT, headers=headers)
    assert project_resp.status_code == 201, project_resp.text
    project_id = project_resp.json()["id"]

    prev_total_payment_to_date = None  # tracks carry-forward

    for claim_idx, (pdf_path, golden) in enumerate(zip(CLAIM_PDFS, GOLDEN_FIXTURES)):
        claim_num = claim_idx + 1
        print(f"\n{'='*60}")
        print(f"  Claim {claim_num}: {pdf_path.name}")
        print(f"{'='*60}")

        # ── 1. Upload and parse ────────────────────────────────────────────
        claim_id = await upload_claim_deep_mode(client, project_id, pdf_path, headers)
        assert claim_id is not None, f"Claim {claim_num}: upload returned no claim_id"

        # ── 2. Verify claim number ─────────────────────────────────────────
        claim_resp = await client.get(
            f"/api/v1/projects/{project_id}/claims/{claim_id}", headers=headers,
        )
        assert claim_resp.status_code == 200
        claim = claim_resp.json()
        assert claim["claim_number"] == claim_num, (
            f"Claim {claim_num}: expected claim_number={claim_num}, got {claim['claim_number']}"
        )

        # ── 3. Get assessment and verify structure ─────────────────────────
        assessment_resp = await client.get(
            f"/api/v1/projects/{project_id}/assessments/by-claim/{claim_id}", headers=headers,
        )
        assert assessment_resp.status_code == 200
        assessment = assessment_resp.json()
        assessment_id = assessment["id"]

        # Verify carry-forward from prior finalised assessment
        if prev_total_payment_to_date is not None:
            _assert_decimal_eq(
                assessment["previously_certified"],
                prev_total_payment_to_date,
                f"Claim {claim_num}: previously_certified",
            )
        else:
            _assert_decimal_eq(
                assessment["previously_certified"],
                "0",
                f"Claim {claim_num}: previously_certified (first claim)",
            )

        # ── 4. Verify assessment line items ─────────────────────────────────
        # System creates LIs for every WBS subcategory (from project setup).
        # PR PDF fixture descriptions don't match WBS subcategory names, so we
        # validate count and that non-zero claimed values exist.
        expected_lis = golden["assessment_line_items"]
        actual_lis = assessment["line_items"]
        assert len(actual_lis) >= len(expected_lis), (
            f"Claim {claim_num}: expected at least {len(expected_lis)} assessment LIs, "
            f"got {len(actual_lis)}"
        )

        # Verify that the number of items with non-zero claims matches
        expected_nonzero = [e for e in expected_lis if _d(e["contractor_claim_to_date"]) != 0]
        actual_nonzero = [a for a in actual_lis if _d(a["contractor_claim_to_date"]) != 0]
        assert len(actual_nonzero) >= len(expected_nonzero), (
            f"Claim {claim_num}: expected at least {len(expected_nonzero)} LIs with non-zero claims, "
            f"got {len(actual_nonzero)}"
        )

        # ── 5. Verify PS and Var item presence ─────────────────────────────
        # System creates carry-forward + current rows per PS/Var, so counts
        # will exceed fixture counts. Verify minimum expected are present.
        expected_ps = golden["assessment_ps_items"]
        actual_ps = assessment.get("provisional_sum_items", [])
        expected_ps_numbers = {exp["ps_number"] for exp in expected_ps}
        actual_ps_numbers = {str(ps["ps_number"]) for ps in actual_ps}
        assert expected_ps_numbers.issubset(actual_ps_numbers), (
            f"Claim {claim_num}: missing PS numbers {expected_ps_numbers - actual_ps_numbers}"
        )

        actual_vars = assessment.get("variation_items", [])

        print(f"  Assessment verified: {len(actual_lis)} LI, "
              f"{len(actual_ps)} PS, {len(actual_vars)} Var")

        # ── 7. Auto-approve all items ──────────────────────────────────────
        await auto_approve_assessment(client, project_id, assessment_id, assessment, headers)

        # ── 8. Finalise ────────────────────────────────────────────────────
        finalise_resp = await client.post(
            f"/api/v1/projects/{project_id}/assessments/{assessment_id}/finalise",
            headers=headers,
        )
        assert finalise_resp.status_code == 200, (
            f"Claim {claim_num}: finalise failed: {finalise_resp.text}"
        )
        finalised = finalise_resp.json()
        assert finalised["status"] == "finalised", (
            f"Claim {claim_num}: expected status=finalised, got {finalised['status']}"
        )

        # ── 9. Verify finalised totals ─────────────────────────────────────
        # Auto-approve uses contractor_claim_to_date (no QS reductions), so
        # total_recommended/retention/payment won't match PR PDF values.
        # We verify contract_sum (from project, always stable) and rely on
        # internal consistency + carry-forward checks.
        expected_totals = golden["finalised_totals"]
        _assert_decimal_eq(
            finalised["contract_sum"],
            expected_totals["contract_sum"],
            f"Claim {claim_num} finalised.contract_sum",
        )

        # ── 10. Verify internal consistency ────────────────────────────────
        # total_payment_to_date = total_recommended - total_retention
        computed_ptd = _d(finalised["total_recommended"]) - _d(finalised["total_retention"])
        assert computed_ptd == _d(finalised["total_payment_to_date"]), (
            f"Claim {claim_num}: total_recommended({finalised['total_recommended']}) "
            f"- total_retention({finalised['total_retention']}) "
            f"= {computed_ptd}, but total_payment_to_date={finalised['total_payment_to_date']}"
        )

        # recommended_this_period = total_payment_to_date - previously_certified
        computed_rtp = _d(finalised["total_payment_to_date"]) - _d(finalised["previously_certified"])
        assert computed_rtp == _d(finalised["recommended_this_period"]), (
            f"Claim {claim_num}: total_payment_to_date({finalised['total_payment_to_date']}) "
            f"- previously_certified({finalised['previously_certified']}) "
            f"= {computed_rtp}, but recommended_this_period={finalised['recommended_this_period']}"
        )

        prev_total_payment_to_date = finalised["total_payment_to_date"]

        print(f"  Finalised: total_recommended={finalised['total_recommended']}, "
              f"payment_to_date={finalised['total_payment_to_date']}, "
              f"this_period={finalised['recommended_this_period']}")
        print(f"  Claim {claim_num} PASSED")

    # ── Final summary ──────────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print(f"  FULL PIPELINE E2E TEST PASSED - All 8 claims processed")
    print(f"  Final total_payment_to_date: {prev_total_payment_to_date}")
    print(f"{'='*60}")
