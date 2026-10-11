from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.schemas.retention import RetentionDetail, RetentionTier
from app.utils.assessment_engine import calculate_retention_per_tier


def test_retention_tier_rejects_unknown_fields():
    with pytest.raises(ValidationError):
        RetentionTier(percentage=Decimal("0.1"), up_to_amount=None, tier_order=1)  # ty: ignore[unknown-argument]


def test_retention_per_tier_reports_each_bracket():
    tiers = [
        RetentionTier(percentage=Decimal("0.05"), up_to_amount=None),
        RetentionTier(percentage=Decimal("0.10"), up_to_amount=Decimal("100")),
    ]
    assert calculate_retention_per_tier(Decimal("150"), tiers) == [
        RetentionDetail(percentage="10.0%", base=Decimal("100"), amount=Decimal("10.00")),
        RetentionDetail(percentage="5.0%", base=Decimal("50"), amount=Decimal("2.50")),
    ]
