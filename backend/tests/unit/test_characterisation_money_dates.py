"""Characterisation: money/date parsing used by create_records, after decision D6.

D6: malformed money no longer vanishes silently. It still persists as 0, but parse_money
reports a warning, and create_records turns that warning into a format_warning flag.
"""

from datetime import date
from decimal import Decimal

from app.harness.executors.create_records.claim import money_format_warnings
from app.harness.executors.extract_generic import validate_and_normalise
from app.harness.executors.extract_wbpro import parse_wbpro
from app.harness.schemas import GenericExtraction, ParsedClaimItem, ParsedClaimSummary, RawExtraction, RawPage
from app.schemas.claim_extraction import MoneyFormatWarning
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
        ParsedClaimItem(item_index=0, ref_code="1.1", contract_value="1,2OO.00", ptd="10.00", current="abc"),
        ParsedClaimItem(item_index=1, ref_code="1.2", contract_value="500.00", balance=None),
    ]
    summary = ParsedClaimSummary(claimed_amount="12x", original_contract_total="100.00")

    warnings = money_format_warnings(items, summary)

    assert [(w.ref, w.field) for w in warnings] == [
        ("1.1", "contract_value"),
        ("1.1", "current"),
        (None, "claimed_amount"),
    ]
    assert all(w.description for w in warnings)


def test_create_records_reports_nothing_for_clean_input():
    clean = [ParsedClaimItem(item_index=0, ref_code="1", contract_value="1.00")]
    assert money_format_warnings(clean, ParsedClaimSummary()) == []


MALFORMED_WBPRO_ROW = ["1.1", "Excavation", "12,3O0.00", "50.00", "100.00", "0.00", "100.00", "0.00"]


def test_wbpro_extraction_reports_malformed_cell_before_normalising_it():
    raw = RawExtraction(pages=[RawPage(page_num=1, text="CONTRACT WORKS", tables=[[MALFORMED_WBPRO_ROW]])])

    parsed = parse_wbpro(raw)

    assert parsed.line_items[0].contract_value == "0.00"
    assert parsed.format_warnings == [
        MoneyFormatWarning(
            ref="1.1",
            field="contract_value",
            description="contract_value: unparseable money value '12,3O0.00'; recorded as 0",
        )
    ]


def test_generic_extraction_reports_malformed_item_and_summary_cells():
    extraction = GenericExtraction.model_validate(
        {
            "line_items": [{"ref_code": "A1", "contract_value": "12,3O0.00", "ptd": "5.00"}],
            "summary": {"original_contract_total": "1.00", "revised_contract_total": "1.00", "claimed_amount": "9x"},
        }
    )

    parsed = validate_and_normalise(extraction)

    assert parsed.line_items[0].contract_value == "0.00"
    assert [(w.ref, w.field) for w in parsed.format_warnings] == [("A1", "contract_value"), (None, "claimed_amount")]


def test_generic_extraction_ignores_unused_summary_cells():
    extraction = GenericExtraction.model_validate(
        {"line_items": [{"ref_code": "A1", "contract_value": "1.00"}], "summary": {"claimed_amount": "9x"}}
    )

    assert validate_and_normalise(extraction).format_warnings == []
