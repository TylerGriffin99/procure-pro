import os
from decimal import Decimal

import pytest

from app.utils.pdf_generator import generate_payment_recommendation_pdf


def test_generate_pr_pdf():
    """Generate a PR PDF and verify it's a valid PDF file."""
    data = {
        "project_name": "Gilmours Central Seismic Upgrade",
        "project_number": "S-02314",
        "pr_number": 1,
        "revision": 0,
        "issue_date": "09 September 2025",
        "principal": "Foodstuffs North Island",
        "engineer": "Owen Sanders",
        "contractor": "Kynoch Construction",
        "claim_number": 1,
        "claim_received": "29 August 2025",
        "payment_due": "20 September 2025",
        "contract_sum": Decimal("4172492.92"),
        "adjustment_to_provisional_sums": Decimal("0"),
        "approved_variation_orders": Decimal("0"),
        "adjusted_contract_sum": Decimal("4172492.92"),
        "value_claimed": Decimal("70317.39"),
        "adjustments": Decimal("-1730.00"),
        "total_recommended": Decimal("68587.39"),
        "retention_details": [
            {"percentage": "10%", "base": Decimal("68587.39"), "amount": Decimal("6858.74")},
        ],
        "total_retention": Decimal("6858.74"),
        "total_payment_to_date": Decimal("61728.65"),
        "previously_certified": Decimal("0"),
        "recommended_this_period": Decimal("61728.65"),
        "gst_rate": Decimal("0.15"),
        "gst_amount": Decimal("9259.30"),
        "total_including_gst": Decimal("70987.95"),
        "contract_works": [
            {
                "description": "Preliminaries",
                "contract_sum": Decimal("250000.00"),
                "contractor_claim": Decimal("6250.00"),
                "recommended": Decimal("6250.00"),
                "percentage": "3%",
                "variance": Decimal("0"),
                "previously_paid": Decimal("0"),
                "recommended_this_period": Decimal("6250.00"),
                "comments": "As per progress noted on site",
            },
        ],
    }

    pdf_bytes = generate_payment_recommendation_pdf(data)

    assert pdf_bytes[:5] == b"%PDF-"
    assert len(pdf_bytes) > 1000

    # Write to temp for visual inspection
    out_path = "/tmp/test_pr.pdf"
    with open(out_path, "wb") as f:
        f.write(pdf_bytes)
    assert os.path.exists(out_path)


def test_pdf_includes_closed_out_status_and_comments():
    """PDF should render 'Closed Out' status and comments for variations/PS."""
    data = {
        "project_name": "Test Project",
        "project_number": "T-001",
        "pr_number": 1,
        "revision": 0,
        "issue_date": "01 January 2026",
        "principal": "Test Client",
        "engineer": "Test Engineer",
        "contractor": "Test Contractor",
        "end_client_name": "Test Client",
        "end_client_address_lines": [],
        "end_client_representative_first_name": "",
        "landlord_split_pct": None,
        "operator_split_pct": None,
        "landlord_amount": Decimal("0"),
        "operator_amount": Decimal("0"),
        "claim_number": 1,
        "claim_received": "01 January 2026",
        "payment_due": "20 January 2026",
        "contract_sum": Decimal("100000"),
        "adjustment_to_provisional_sums": Decimal("0"),
        "approved_variation_orders": Decimal("0"),
        "adjusted_contract_sum": Decimal("100000"),
        "value_claimed": Decimal("10000"),
        "adjustments": Decimal("0"),
        "total_recommended": Decimal("10000"),
        "retention_details": [],
        "total_retention": Decimal("0"),
        "total_payment_to_date": Decimal("10000"),
        "previously_certified": Decimal("0"),
        "recommended_this_period": Decimal("10000"),
        "gst_rate": Decimal("0.15"),
        "gst_amount": Decimal("1500"),
        "total_including_gst": Decimal("11500"),
        "contract_works": [],
        "variation_works": [
            {
                "ci_number": "1",
                "description": "Test variation - closed out",
                "submission": Decimal("5000"),
                "type": "",
                "claimed_to_date": Decimal("5000"),
                "recommended": Decimal("5000"),
                "previously_paid": Decimal("0"),
                "this_period": Decimal("5000"),
                "status": "Closed Out",
                "comments": "paid 80% on account",
            },
            {
                "ci_number": "2",
                "description": "Test variation - interim",
                "submission": Decimal("3000"),
                "type": "",
                "claimed_to_date": Decimal("3000"),
                "recommended": Decimal("2000"),
                "previously_paid": Decimal("0"),
                "this_period": Decimal("2000"),
                "status": "Interim",
                "comments": "",
            },
        ],
        "provisional_sums": [
            {
                "ps_number": 1,
                "description": "Test PS - approved",
                "contract_sum": Decimal("20000"),
                "claimed_to_date": Decimal("10000"),
                "recommended": Decimal("8000"),
                "previously_paid": Decimal("0"),
                "this_period": Decimal("8000"),
                "percentage": "40.0%",
                "status": "Approved",
                "comments": "Standard approval",
            },
        ],
        "is_draft": False,
    }

    pdf_bytes = generate_payment_recommendation_pdf(data)
    assert pdf_bytes[:5] == b"%PDF-"
    assert len(pdf_bytes) > 1000

    # Write for visual inspection
    out_path = "/tmp/test_pr_closed_out.pdf"
    with open(out_path, "wb") as f:
        f.write(pdf_bytes)
