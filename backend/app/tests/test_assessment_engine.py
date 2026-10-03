from decimal import Decimal

import pytest

from app.utils.assessment_engine import calculate_retention, calculate_assessment_totals


def test_retention_tiered():
    """Test the 10/5/1.75 tiered retention from Gilmours project."""
    tiers = [
        {"percentage": Decimal("0.10"), "up_to_amount": Decimal("200000")},
        {"percentage": Decimal("0.05"), "up_to_amount": Decimal("800000")},
        {"percentage": Decimal("0.0175"), "up_to_amount": None},  # remainder
    ]
    # PR8: total recommended = 2,322,651.70, retention = 83,146.40
    # 10% of first 200K = 20,000
    # 5% of next 800K = 40,000
    # 1.75% of remaining 1,322,651.70 = 23,146.40
    # Total = 83,146.40
    result = calculate_retention(Decimal("2322651.70"), tiers)
    assert result == Decimal("83146.40")


def test_retention_small_amount():
    """When total is less than first tier."""
    tiers = [
        {"percentage": Decimal("0.10"), "up_to_amount": Decimal("200000")},
        {"percentage": Decimal("0.05"), "up_to_amount": Decimal("800000")},
        {"percentage": Decimal("0.0175"), "up_to_amount": None},
    ]
    # PR1: total recommended = 68,587.39
    # 10% of 68,587.39 = 6,858.74
    result = calculate_retention(Decimal("68587.39"), tiers)
    assert result == Decimal("6858.74")


def test_assessment_totals():
    """Test full assessment total calculation matching PR8."""
    result = calculate_assessment_totals(
        contract_sum=Decimal("4172492.92"),
        sub_total_contract_works=Decimal("2047173.24"),
        sub_total_provisional_sums=Decimal("54201.48"),
        sub_total_variations_recommended=Decimal("221276.98"),
        variations_claimed=Decimal("229189.67"),
        retention_tiers=[
            {"percentage": Decimal("0.10"), "up_to_amount": Decimal("200000")},
            {"percentage": Decimal("0.05"), "up_to_amount": Decimal("800000")},
            {"percentage": Decimal("0.0175"), "up_to_amount": None},
        ],
        previously_certified=Decimal("1877003.99"),
        gst_rate=Decimal("0.15"),
    )
    assert result["adjusted_contract_sum"] == Decimal("4393769.90")
    assert result["total_recommended"] == Decimal("2322651.70")
    assert result["adjustments"] == Decimal("-7912.69")
    assert result["total_retention"] == Decimal("83146.40")
    assert result["total_payment_to_date"] == Decimal("2239505.30")
    assert result["recommended_this_period"] == Decimal("362501.31")  # May differ by rounding
