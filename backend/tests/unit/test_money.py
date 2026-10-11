from decimal import Decimal

import pytest

from app.utils.money import format_money, parse_money


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("1,234.50", Decimal("1234.50")),
        ("(12.00)", Decimal("-12.00")),
        ("(1,234.56)", Decimal("-1234.56")),
        ("$1,234.56", Decimal("1234.56")),
        ("  1234.56  ", Decimal("1234.56")),
        ("-500.00", Decimal("-500.00")),
        (100, Decimal("100")),
        (99.9, Decimal("99.9")),
        (Decimal("7.25"), Decimal("7.25")),
    ],
)
def test_parse_money_reads_well_formed_input(raw, expected):
    parsed = parse_money(raw)
    assert parsed.value == expected
    assert parsed.warning is None


@pytest.mark.parametrize("raw", [None, "", "   ", "-"])
def test_parse_money_blank_is_zero_without_warning(raw):
    parsed = parse_money(raw)
    assert parsed.value == Decimal("0")
    assert parsed.warning is None


def test_parse_money_blank_marker_is_configurable():
    assert parse_money("n/a", blank="n/a").warning is None
    assert parse_money("-", blank="n/a").warning is not None


@pytest.mark.parametrize("raw", ["1,2OO", "1,2OO.00", "abc", "NaN", "Infinity"])
def test_parse_money_malformed_is_zero_with_warning(raw):
    parsed = parse_money(raw)
    assert parsed.value == Decimal("0")
    assert parsed.warning is not None
    assert repr(raw) in parsed.warning


def test_parse_money_keeps_full_precision():
    assert parse_money("1234.567").value == Decimal("1234.567")


@pytest.mark.parametrize(
    ("value", "expected"), [(Decimal("1234.567"), "1234.57"), (Decimal("5000"), "5000.00"), (Decimal("0"), "0.00")]
)
def test_format_money_rounds_to_cents(value, expected):
    assert format_money(value) == expected
