from decimal import Decimal

from app.schemas.payment_recommendation import PaymentRecommendation

ZERO = Decimal("0")
DEFAULTS = {
    "project_name": "",
    "project_number": "",
    "pr_number": 1,
    "issue_date": "",
    "principal": "",
    "end_client_name": "",
    "end_client_address_lines": [],
    "end_client_representative_first_name": "",
    "landlord_split_pct": None,
    "operator_split_pct": None,
    "landlord_amount": ZERO,
    "operator_amount": ZERO,
    "engineer": "",
    "contractor": "",
    "claim_number": 1,
    "claim_received": "",
    "provisional_payment_schedule_due": "",
    "payment_schedule_due": "",
    "payment_due": "",
    "contract_sum": ZERO,
    "adjustment_to_provisional_sums": ZERO,
    "approved_variation_orders": ZERO,
    "adjusted_contract_sum": ZERO,
    "value_claimed": ZERO,
    "adjustments": ZERO,
    "total_recommended": ZERO,
    "retention_details": [],
    "total_retention": ZERO,
    "total_payment_to_date": ZERO,
    "previously_certified": ZERO,
    "recommended_this_period": ZERO,
    "gst_rate": Decimal("0.15"),
    "gst_amount": ZERO,
    "total_including_gst": ZERO,
    "contract_works": [],
    "variation_works": [],
    "provisional_sums": [],
    "is_draft": False,
}
LINE_DEFAULTS = {
    "contract_works": {"comments": ""},
    "variation_works": {"comments": ""},
    "provisional_sums": {"comments": ""},
}


def payment_recommendation(data: dict) -> PaymentRecommendation:
    merged = DEFAULTS | data
    for key, defaults in LINE_DEFAULTS.items():
        merged[key] = [defaults | item for item in merged[key]]
    return PaymentRecommendation.model_validate(merged)
