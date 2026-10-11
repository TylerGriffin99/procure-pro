import uuid
from datetime import UTC, date, datetime
from types import SimpleNamespace

import pytest

from app.schemas.payment_recommendation import ClaimDates
from app.services.assessment_service import closed_out_comment
from app.utils.dates import format_long_date


def claim(received=None, created=None, provisional=None, schedule=None, payment=None):
    return SimpleNamespace(
        claim_received=received,
        created_at=created,
        provisional_payment_schedule_due=provisional,
        payment_schedule_due=schedule,
        payment_due=payment,
    )


def test_no_claim_has_blank_dates():
    assert ClaimDates.from_claim(None) == ClaimDates()


def test_missing_received_derives_every_date_from_created_at():
    dates = ClaimDates.from_claim(claim(created=datetime(2025, 8, 29, 9, tzinfo=UTC), payment=date(2030, 1, 1)))
    assert dates == ClaimDates(
        claim_received="29 August 2025",
        provisional_payment_schedule_due="5 September 2025",
        payment_schedule_due="12 September 2025",
        payment_due="20 October 2025",
    )


def test_explicit_dates_win_and_gaps_are_auto_filled():
    dates = ClaimDates.from_claim(claim(received=date(2025, 8, 29), schedule=date(2025, 9, 15)))
    assert dates.claim_received == "29 August 2025"
    assert dates.provisional_payment_schedule_due == "5 September 2025"
    assert dates.payment_schedule_due == "15 September 2025"
    assert dates.payment_due == "20 October 2025"


def test_format_long_date_accepts_dates_datetimes_and_none():
    assert format_long_date(None) == ""
    assert format_long_date(date(2025, 1, 5)) == "5 January 2025"
    assert format_long_date(datetime(2025, 1, 5, 23, tzinfo=UTC)) == "5 January 2025"


@pytest.mark.parametrize(
    ("claim_line_item_id", "comments", "expected"),
    [
        (None, None, "Closed Out"),
        (None, "Interim - pending", "Closed Out - pending"),
        (None, "note", "Closed Out - note"),
        (None, "Closed Out - done", "Closed Out - done"),
        (uuid.uuid4(), "keep", "keep"),
        (uuid.uuid4(), None, None),
    ],
)
def test_closed_out_comment(claim_line_item_id, comments, expected):
    row = SimpleNamespace(claim_line_item_id=claim_line_item_id, comments=comments)
    assert closed_out_comment(row) == expected
