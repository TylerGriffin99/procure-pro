"""Tests for interim adjustment and close-out logic."""

import uuid
from decimal import Decimal

from app.models.assessment import AdjustmentType, LineItemStatus


class FakeLineItem:
    def __init__(self, **kwargs):
        defaults = dict(
            id=uuid.uuid4(),
            wbs_code_id=None,
            claim_line_item_id=None,
            description="Test",
            contract_sum=Decimal("0"),
            contractor_claim_to_date=Decimal("0"),
            total_recommended=Decimal("0"),
            previously_paid=Decimal("0"),
            recommended_this_period=Decimal("0"),
            variance_to_claim=Decimal("0"),
            percentage=Decimal("0"),
            status=LineItemStatus.unapproved,
            sort_order=0,
            comments=None,
            adjustment_type=None,
        )
        defaults.update(kwargs)
        for k, v in defaults.items():
            setattr(self, k, v)


class FakeWBS:
    def __init__(self, id, description="WBS", contract_sum=Decimal("100000")):
        self.id = id
        self.description = description
        self.contract_sum = contract_sum


def test_adjustment_type_enum_values():
    assert AdjustmentType.interim_adjustment == "interim_adjustment"


def test_adjustment_row_aggregates_normally():
    """An adjustment row should be included in group aggregation."""
    from app.utils.assessment_aggregator import aggregate_line_items

    wbs_id = uuid.uuid4()
    wbs = FakeWBS(id=wbs_id)

    history = FakeLineItem(
        wbs_code_id=wbs_id,
        claim_line_item_id=None,
        total_recommended=Decimal("80000"),
        previously_paid=Decimal("80000"),
        recommended_this_period=Decimal("0"),
        contractor_claim_to_date=Decimal("100000"),
        status=LineItemStatus.interim,
        description="Concrete works",
    )

    groups = aggregate_line_items([history], [wbs])
    assert len(groups) == 1
    assert groups[0].total_recommended == Decimal("80000")
    assert groups[0].history_row is not None
