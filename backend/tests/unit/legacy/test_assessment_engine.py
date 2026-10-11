from decimal import Decimal

from app.schemas.retention import RetentionTier
from app.utils.assessment_engine import calculate_retention


def test_retention_tiered():
    """Test the 10/5/1.75 tiered retention from Gilmours project."""
    tiers = [
        RetentionTier(percentage=Decimal("0.10"), up_to_amount=Decimal("200000")),
        RetentionTier(percentage=Decimal("0.05"), up_to_amount=Decimal("800000")),
        RetentionTier(percentage=Decimal("0.0175"), up_to_amount=None),  # remainder
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
        RetentionTier(percentage=Decimal("0.10"), up_to_amount=Decimal("200000")),
        RetentionTier(percentage=Decimal("0.05"), up_to_amount=Decimal("800000")),
        RetentionTier(percentage=Decimal("0.0175"), up_to_amount=None),
    ]
    # PR1: total recommended = 68,587.39
    # 10% of 68,587.39 = 6,858.74
    result = calculate_retention(Decimal("68587.39"), tiers)
    assert result == Decimal("6858.74")
