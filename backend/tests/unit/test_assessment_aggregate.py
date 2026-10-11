from decimal import Decimal

import pytest

from app.constants.enums import LineItemStatus, VariationStatus
from app.models.assessment_line_item import AssessmentLineItem
from app.models.assessment_variation import AssessmentVariation
from app.schemas.payment_recommendation import export_display
from app.services.assessment_aggregate import recompute_item, rollup_status


def _row(status: LineItemStatus, comments: str | None = None, closed: bool = False) -> AssessmentVariation:
    return AssessmentVariation(status=status, comments=comments, is_closed_out=closed)


A, I, U = LineItemStatus.approved, LineItemStatus.interim, LineItemStatus.unapproved


@pytest.mark.parametrize(
    ("statuses", "expected"),
    [
        ([A, A], VariationStatus.approved),
        ([A, I], VariationStatus.in_review),
        ([I, U], VariationStatus.in_review),
        ([A, U], VariationStatus.unapproved),
        ([U], VariationStatus.unapproved),
        ([], VariationStatus.approved),
    ],
)
def test_rollup_status_table(statuses, expected):
    assert rollup_status([_row(s) for s in statuses]) == expected


def test_recompute_item_derives_variance_percentage_and_this_period():
    row = AssessmentLineItem(
        total_recommended=Decimal("600"),
        contractor_claim_to_date=Decimal("1000"),
        previously_paid=Decimal("250"),
        percentage=Decimal("0"),
    )
    recompute_item(row, denominator=Decimal("3000"))
    assert row.variance_to_claim == Decimal("-400")
    assert row.percentage == Decimal("20.00")
    assert row.recommended_this_period == Decimal("350")


@pytest.mark.parametrize("denominator", [None, Decimal("0"), Decimal("-5")])
def test_recompute_item_leaves_percentage_without_a_positive_denominator(denominator):
    row = AssessmentLineItem(
        total_recommended=Decimal("600"),
        contractor_claim_to_date=Decimal("0"),
        previously_paid=Decimal("0"),
        percentage=Decimal("12.34"),
    )
    recompute_item(row, denominator=denominator)
    assert row.percentage == Decimal("12.34")


def test_export_display_closed_out_wins_and_prefix_is_stripped():
    history = _row(A, "Closed Out - agreed on site", closed=True)
    assert export_display(history, [_row(U, "second")]) == ("agreed on site; second", "Closed Out")


def test_export_display_status_prefers_first_child_then_history():
    history = _row(A, "Interim - x")
    assert export_display(history, [_row(I), _row(U)]) == ("x", "Interim")
    assert export_display(history, []) == ("x", "Approved")
    assert export_display(None, [_row(U, "  y  ")]) == ("y", "Unapproved")


def test_export_display_empty_group():
    assert export_display(None, []) == ("", "")
