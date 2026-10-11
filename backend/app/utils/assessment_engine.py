"""Deterministic assessment calculations — no AI needed here."""

from collections.abc import Sequence
from decimal import ROUND_HALF_UP, Decimal

from app.constants.values import CENTS
from app.schemas.assessment_aggregate import AssessmentSummary, AssessmentTotals
from app.schemas.retention import RetentionTier


def calculate_retention(total_recommended: Decimal, tiers: Sequence[RetentionTier]) -> Decimal:
    """An ``up_to_amount`` of None is the remainder tier."""
    remaining = total_recommended
    total_retention = Decimal("0")

    for tier in sorted(tiers, key=lambda t: t.up_to_amount or Decimal("999999999")):
        if remaining <= 0:
            break

        up_to = tier.up_to_amount
        pct = tier.percentage

        if up_to is None:
            # Remainder tier
            retention = (remaining * pct).quantize(CENTS, rounding=ROUND_HALF_UP)
            total_retention += retention
            remaining = Decimal("0")
        else:
            applicable = min(remaining, up_to)
            retention = (applicable * pct).quantize(CENTS, rounding=ROUND_HALF_UP)
            total_retention += retention
            remaining -= applicable

    return total_retention


def calculate_retention_per_tier(total_recommended: Decimal, tiers: Sequence[RetentionTier]) -> list[dict]:
    """Calculate retention per tier for display in the PDF.

    Returns list of dicts with 'percentage', 'base' (amount in this tier's bracket),
    and 'amount' (retention for this tier).
    """
    remaining = total_recommended
    details = []

    for tier in sorted(tiers, key=lambda t: t.up_to_amount or Decimal("999999999")):
        pct = tier.percentage
        up_to = tier.up_to_amount

        if remaining <= 0:
            details.append({"percentage": f"{float(pct) * 100:.1f}%", "base": Decimal("0"), "amount": Decimal("0")})
            continue

        if up_to is None:
            applicable = remaining
            remaining = Decimal("0")
        else:
            applicable = min(remaining, up_to)
            remaining -= applicable

        retention = (applicable * pct).quantize(CENTS, rounding=ROUND_HALF_UP)
        details.append({"percentage": f"{float(pct) * 100:.1f}%", "base": applicable, "amount": retention})

    return details


def assessment_summary(
    totals: AssessmentTotals,
    *,
    contract_sum: Decimal,
    retention_tiers: Sequence[RetentionTier],
    previously_certified: Decimal,
    gst_rate: Decimal,
) -> AssessmentSummary:
    total_retention = calculate_retention(totals.total_recommended, retention_tiers)
    total_payment_to_date = totals.total_recommended - total_retention
    recommended_this_period = total_payment_to_date - previously_certified
    gst_amount = (recommended_this_period * gst_rate).quantize(CENTS, rounding=ROUND_HALF_UP)
    return AssessmentSummary(
        contract_sum=contract_sum,
        approved_variation_orders=totals.approved_variation_orders,
        adjustment_to_provisional_sums=totals.adjustment_to_provisional_sums,
        adjusted_contract_sum=contract_sum + totals.approved_variation_orders + totals.adjustment_to_provisional_sums,
        value_claimed_to_date=totals.value_claimed_to_date,
        adjustments=totals.adjustments,
        total_recommended=totals.total_recommended,
        total_retention=total_retention,
        total_payment_to_date=total_payment_to_date,
        recommended_this_period=recommended_this_period,
        gst_amount=gst_amount,
        total_including_gst=recommended_this_period + gst_amount,
    )
