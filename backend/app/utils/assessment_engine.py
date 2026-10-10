"""Deterministic assessment calculations — no AI needed here."""
from decimal import ROUND_HALF_UP, Decimal


def calculate_retention(total_recommended: Decimal, tiers: list[dict]) -> Decimal:
    """Calculate tiered retention.

    Args:
        total_recommended: Total value of works recommended for payment
        tiers: List of dicts with 'percentage' and 'up_to_amount' (None = remainder)

    Returns:
        Total retention amount (positive number)
    """
    remaining = total_recommended
    total_retention = Decimal("0")

    for tier in sorted(tiers, key=lambda t: t.get("up_to_amount") or Decimal("999999999")):
        if remaining <= 0:
            break

        up_to = tier.get("up_to_amount")
        pct = tier["percentage"]

        if up_to is None:
            # Remainder tier
            retention = (remaining * pct).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            total_retention += retention
            remaining = Decimal("0")
        else:
            applicable = min(remaining, up_to)
            retention = (applicable * pct).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            total_retention += retention
            remaining -= applicable

    return total_retention


def calculate_retention_per_tier(total_recommended: Decimal, tiers: list[dict]) -> list[dict]:
    """Calculate retention per tier for display in the PDF.

    Returns list of dicts with 'percentage', 'base' (amount in this tier's bracket),
    and 'amount' (retention for this tier).
    """
    remaining = total_recommended
    details = []

    for tier in sorted(tiers, key=lambda t: t.get("up_to_amount") or Decimal("999999999")):
        pct = tier["percentage"]
        up_to = tier.get("up_to_amount")

        if remaining <= 0:
            details.append({
                "percentage": f"{float(pct)*100:.1f}%",
                "base": Decimal("0"),
                "amount": Decimal("0"),
            })
            continue

        if up_to is None:
            applicable = remaining
            remaining = Decimal("0")
        else:
            applicable = min(remaining, up_to)
            remaining -= applicable

        retention = (applicable * pct).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        details.append({
            "percentage": f"{float(pct)*100:.1f}%",
            "base": applicable,
            "amount": retention,
        })

    return details


def calculate_assessment_totals(
    contract_sum: Decimal,
    sub_total_contract_works: Decimal,
    sub_total_provisional_sums: Decimal,
    sub_total_variations_recommended: Decimal,
    variations_claimed: Decimal,
    retention_tiers: list[dict],
    previously_certified: Decimal,
    gst_rate: Decimal,
) -> dict:
    """Calculate all assessment summary totals.

    Returns dict with all summary fields matching the payment recommendation format.
    """
    # Adjusted contract sum = base + approved variations only
    approved_variation_orders = sub_total_variations_recommended
    adjusted_contract_sum = contract_sum + approved_variation_orders

    # Value claimed to date = contract works + provisional sums + variations (claimed amounts)
    value_claimed = sub_total_contract_works + sub_total_provisional_sums + variations_claimed

    # Adjustments = recommended variations - claimed variations (the variance)
    adjustments = sub_total_variations_recommended - variations_claimed

    # Total recommended = contract works + provisional sums + recommended variations
    total_recommended = sub_total_contract_works + sub_total_provisional_sums + sub_total_variations_recommended

    # Retention
    total_retention = calculate_retention(total_recommended, retention_tiers)

    # Total payment to date (after retention)
    total_payment_to_date = total_recommended - total_retention

    # This period
    recommended_this_period = total_payment_to_date - previously_certified

    # GST
    gst_amount = (recommended_this_period * gst_rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    total_including_gst = recommended_this_period + gst_amount

    return {
        "contract_sum": contract_sum,
        "approved_variation_orders": approved_variation_orders,
        "adjusted_contract_sum": adjusted_contract_sum,
        "value_claimed_to_date": value_claimed,
        "adjustments": adjustments,
        "total_recommended": total_recommended,
        "total_retention": total_retention,
        "total_payment_to_date": total_payment_to_date,
        "previously_certified": previously_certified,
        "recommended_this_period": recommended_this_period,
        "gst_amount": gst_amount,
        "total_including_gst": total_including_gst,
    }
