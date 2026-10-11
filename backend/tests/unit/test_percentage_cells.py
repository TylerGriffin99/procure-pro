from decimal import Decimal

import pytest

from app.harness.executors.extract_generic import normalise_item
from app.harness.executors.extract_wbpro import money_cells
from app.harness.extract_shared import money_warnings, parse_cell
from app.harness.schemas import GenericLineItem
from app.utils.money import parse_percentage


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("0.00 %", "0.00"), ("2.50 %", "2.50"), ("2.5%", "2.5"), (" 12 % ", "12"), ("100%", "100"), ("2.50", "2.50")],
)
def test_parse_percentage_strips_the_percent_sign(raw, expected):
    parsed = parse_percentage(raw)
    assert parsed.value == Decimal(expected)
    assert parsed.warning is None


@pytest.mark.parametrize("raw", [None, "", "  ", "-", "- %"])
def test_parse_percentage_blank_is_zero_without_warning(raw):
    parsed = parse_percentage(raw)
    assert parsed.value == Decimal("0")
    assert parsed.warning is None


@pytest.mark.parametrize("raw", ["abc %", "2.5O %", "%%"])
def test_parse_percentage_malformed_is_zero_with_warning(raw):
    parsed = parse_percentage(raw)
    assert parsed.value == Decimal("0")
    assert parsed.warning == f"unparseable percentage value {raw!r}"


def test_parse_cell_routes_percentage_fields_to_the_percentage_parser():
    assert parse_cell("percentage", "2.50 %").value == Decimal("2.50")
    assert parse_cell("ptd", "2.50 %").warning is not None


def test_money_warnings_do_not_flag_percent_signs_in_the_percentage_column():
    cells = [("1.1", "percentage", "0.00 %"), ("1.2", "percentage", "2.50 %"), ("1.3", "ptd", "2.50 %")]
    warnings = money_warnings(cells)
    assert [w.ref for w in warnings] == ["1.3"]


def test_wbpro_money_cells_keep_the_percentage_value():
    cells = money_cells(["1,000.00", "2.50 %", "25.00", "0.00", "25.00", "975.00"])
    assert cells["percentage"] == "2.50"
    assert cells["contract_value"] == "1000.00"


def test_generic_normalise_item_keeps_the_percentage_value():
    raw = GenericLineItem(ref_code="1.1", description="x", item_type="contract_work", percentage="2.5%")
    assert normalise_item(0, raw).percentage == "2.50"
