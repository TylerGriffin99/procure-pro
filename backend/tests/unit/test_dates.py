from datetime import date

import pytest

from app.utils.dates import add_working_days, auto_fill_dates, parse_ddmmyy, payment_due_20th


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("05/03/2024", date(2024, 3, 5)), ("05/03/24", date(2024, 3, 5)), ("31/12/99", date(2099, 12, 31))],
)
def test_parse_ddmmyy_reads_day_first(raw, expected):
    assert parse_ddmmyy(raw) == expected


@pytest.mark.parametrize("raw", ["", "31/13/2024", "2024-03-05", "aa/bb/cc", "1/2"])
def test_parse_ddmmyy_returns_none_when_unreadable(raw):
    assert parse_ddmmyy(raw) is None


def test_add_working_days_skips_weekends():
    friday = date(2025, 10, 3)
    assert add_working_days(friday, 1) == date(2025, 10, 6)
    assert add_working_days(friday, 5) == date(2025, 10, 10)


def test_add_working_days_zero_is_identity():
    assert add_working_days(date(2025, 10, 4), 0) == date(2025, 10, 4)


def test_payment_due_20th_is_next_month():
    assert payment_due_20th(date(2025, 10, 31)) == date(2025, 11, 20)


def test_payment_due_20th_rolls_the_year_in_december():
    assert payment_due_20th(date(2025, 12, 5)) == date(2026, 1, 20)


def test_auto_fill_dates_chains_two_offsets_then_the_20th():
    assert auto_fill_dates(date(2025, 10, 1)) == {
        "provisional_payment_schedule_due": date(2025, 10, 8),
        "payment_schedule_due": date(2025, 10, 15),
        "payment_due": date(2025, 11, 20),
    }


def test_auto_fill_dates_without_a_received_date_is_empty():
    assert auto_fill_dates(None) == {}


def test_parse_ddmmyy_accepts_none():
    assert parse_ddmmyy(None) is None
