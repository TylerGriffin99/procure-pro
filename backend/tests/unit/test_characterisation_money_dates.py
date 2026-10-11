"""Characterisation: pins today's money/date parsing in create_records, defects included."""

from datetime import date
from decimal import Decimal

from app.harness.executors.create_records import _dec, _parse_date


def test_dec_today_swallows_garbage_to_zero():
    assert _dec("1,2OO.00") == Decimal("0")  # D6 flips this to a flag + warning


def test_dec_today_parses_thousands_separators():
    assert _dec("1,200.00") == Decimal("1200.00")


def test_dec_today_maps_empty_and_none_to_zero():
    assert _dec("") == Decimal("0")
    assert _dec(None) == Decimal("0")


def test_parse_date_today_returns_none_on_garbage():
    assert _parse_date("31/13/2024") is None


def test_parse_date_today_reads_day_first_and_pivots_two_digit_years():
    assert _parse_date("05/03/24") == date(2024, 3, 5)
    assert _parse_date("2024-03-05") is None
