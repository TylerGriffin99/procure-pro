"""Tests for interim adjustment and close-out logic."""
import uuid
from decimal import Decimal

import pytest

from app.models.assessment import AdjustmentType, LineItemStatus
from app.models.assessment_line_item import AssessmentLineItem
from app.models.wbs_code import WBSCode


def _line_item(**kwargs) -> AssessmentLineItem:
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
    return AssessmentLineItem(**defaults)


def _wbs(id, description="WBS", contract_sum=Decimal("100000")) -> WBSCode:
    return WBSCode(id=id, description=description, contract_sum=contract_sum)


def test_adjustment_type_enum_values():
    assert AdjustmentType.interim_adjustment == "interim_adjustment"


def test_adjustment_row_aggregates_normally():
    """An adjustment row should be included in group aggregation."""
    from app.utils.assessment_aggregator import aggregate_line_items

    wbs_id = uuid.uuid4()
    wbs = _wbs(id=wbs_id)

    history = _line_item(
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


def test_close_out_comment_prefix_replacement():
    comment = "Interim - Paid on account"
    if comment.startswith("Interim"):
        comment = "Closed Out" + comment[len("Interim"):]
    assert comment == "Closed Out - Paid on account"


def test_close_out_comment_no_existing():
    comment = None
    if not comment:
        comment = "Closed Out"
    assert comment == "Closed Out"


def test_close_out_comment_non_interim_prefix():
    comment = "Some other note"
    if comment.startswith("Interim"):
        comment = "Closed Out" + comment[len("Interim"):]
    else:
        comment = f"Closed Out - {comment}"
    assert comment == "Closed Out - Some other note"


def test_interim_adjustment_difference_positive():
    previously_paid = Decimal("80000")
    agreed_total = Decimal("95000")
    difference = agreed_total - previously_paid
    assert difference == Decimal("15000")


def test_interim_adjustment_difference_negative():
    previously_paid = Decimal("80000")
    agreed_total = Decimal("70000")
    difference = agreed_total - previously_paid
    assert difference == Decimal("-10000")


def test_interim_adjustment_difference_zero():
    previously_paid = Decimal("80000")
    agreed_total = Decimal("80000")
    difference = agreed_total - previously_paid
    assert difference == Decimal("0")
