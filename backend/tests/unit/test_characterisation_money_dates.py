"""Characterisation: money/date parsing used by create_records, after decision D6.

D6: malformed money no longer vanishes silently. It still persists as 0, but parse_money
reports a warning, and create_records turns that warning into a format_warning flag.
"""

from datetime import date
from decimal import Decimal

from app.harness.executors.create_records import money_format_warnings
from app.utils.dates import parse_ddmmyy
from app.utils.money import parse_money


def test_malformed_money_persists_zero_and_reports_a_warning():
    parsed = parse_money("1,2OO.00")
    assert parsed.value == Decimal("0")
    assert parsed.warning is not None


def test_money_parses_thousands_separators():
    assert parse_money("1,200.00").value == Decimal("1200.00")


def test_money_maps_empty_and_none_to_zero_silently():
    assert parse_money("") == parse_money(None)
    assert parse_money(None).value == Decimal("0")
    assert parse_money(None).warning is None


def test_parse_date_returns_none_on_garbage():
    assert parse_ddmmyy("31/13/2024") is None


def test_parse_date_reads_day_first_and_pivots_two_digit_years():
    assert parse_ddmmyy("05/03/24") == date(2024, 3, 5)
    assert parse_ddmmyy("2024-03-05") is None


def test_create_records_reports_one_warning_per_malformed_persisted_field():
    items = [
        {"ref_code": "1.1", "contract_value": "1,2OO.00", "ptd": "10.00", "current": "abc"},
        {"ref_code": "1.2", "contract_value": "500.00", "balance": None},
    ]
    summary = {"claimed_amount": "12x", "original_contract_total": "100.00"}

    warnings = money_format_warnings(items, summary)

    assert [(w.ref, w.field) for w in warnings] == [
        ("1.1", "contract_value"),
        ("1.1", "current"),
        (None, "claimed_amount"),
    ]
    assert all(w.description for w in warnings)


def test_create_records_reports_nothing_for_clean_input():
    assert money_format_warnings([{"ref_code": "1", "contract_value": "1.00"}], {}) == []
