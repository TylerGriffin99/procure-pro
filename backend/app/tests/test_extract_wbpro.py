"""Tests for the deterministic WBPRO table parser."""
import pytest

from app.harness.executors.extract_wbpro import parse_decimal, is_skip_row
from app.harness.executors.extract_wbpro import detect_sections, SECTION_CONTRACT, SECTION_VARIATION, SECTION_PS
from app.harness.executors.extract_wbpro import extract_metadata
from app.harness.executors.extract_wbpro import parse_wbpro


class TestParseWbpro:
    def _make_raw_extraction(self) -> dict:
        """Build a minimal raw_extraction.json structure with known data."""
        return {
            "metadata": {},
            "pages": [
                {
                    "page_num": 1,
                    "text": "CONTRACTOR PROGRESS CLAIM\nClaim No. 3\nPeriod From: 01/09/2025\nPeriod To: 30/09/2025\nPayment Due: 15/10/2025\nCONTRACT WORKS",
                    "tables": [
                        [
                            ["1.0", "Preliminaries", "100,000.00", "50.00", "50,000.00", "30,000.00", "20,000.00", "50,000.00"],
                            ["2.0", "Excavation", "200,000.00", "25.00", "50,000.00", "30,000.00", "20,000.00", "150,000.00"],
                            ["", "Total Contract Works", "", "", "100,000.00", "60,000.00", "40,000.00", "200,000.00"],
                        ],
                    ],
                },
                {
                    "page_num": 2,
                    "text": "VARIATION WORKS",
                    "tables": [
                        [
                            ["CI-01", "Extra piling", "CR-01", "5,000.00", "100.00", "5,000.00", "5,000.00", "0.00", "0.00"],
                            ["CI-02", "Retaining wall", "", "10,000.00", "0.00", "0.00", "0.00", "0.00", "10,000.00"],
                        ],
                    ],
                },
                {
                    "page_num": 3,
                    "text": "PROVISIONAL SUMS",
                    "tables": [
                        [
                            ["PS-01", "Allowance for unforeseen", "15,000.00", "0.00", "0.00", "0.00", "0.00", "15,000.00"],
                        ],
                    ],
                },
            ],
        }

    def test_line_item_count(self):
        result = parse_wbpro(self._make_raw_extraction())
        assert len(result["line_items"]) == 5  # 2 contract + 2 variation + 1 PS

    def test_item_indexes_sequential(self):
        result = parse_wbpro(self._make_raw_extraction())
        indexes = [item["item_index"] for item in result["line_items"]]
        assert indexes == [0, 1, 2, 3, 4]

    def test_item_types(self):
        result = parse_wbpro(self._make_raw_extraction())
        types = [item["item_type"] for item in result["line_items"]]
        assert types == ["contract_work", "contract_work", "variation", "variation", "provisional_sum"]

    def test_total_row_skipped(self):
        result = parse_wbpro(self._make_raw_extraction())
        descs = [item["description"] for item in result["line_items"]]
        assert "Total Contract Works" not in descs

    def test_contract_value_parsed(self):
        result = parse_wbpro(self._make_raw_extraction())
        assert result["line_items"][0]["contract_value"] == "100000.00"

    def test_variation_value_parsed(self):
        result = parse_wbpro(self._make_raw_extraction())
        assert result["line_items"][2]["contract_value"] == "5000.00"
        assert result["line_items"][2]["ref_code"] == "CI-01"

    def test_metadata_extracted(self):
        result = parse_wbpro(self._make_raw_extraction())
        assert result["metadata"]["claim_number"] == "3"
        assert result["metadata"]["period_from"] == "01/09/2025"

    def test_summary_totals(self):
        result = parse_wbpro(self._make_raw_extraction())
        # original = sum of contract_work values = 100000 + 200000 = 300000
        assert result["summary"]["original_contract_total"] == "300000.00"
        # revised = all items = 300000 + 5000 + 10000 + 15000 = 330000
        assert result["summary"]["revised_contract_total"] == "330000.00"
        # claimed = sum of all ptd values = 50000 + 50000 + 5000 + 0 + 0 = 105000
        assert result["summary"]["claimed_amount"] == "105000.00"

    def test_mixed_tables_on_variation_page(self):
        """A page with VARIATION WORKS header can have an 8-col contract table followed by 9-col variations."""
        raw = {
            "metadata": {},
            "pages": [
                {
                    "page_num": 1,
                    "text": "CONTRACT WORKS",
                    "tables": [[
                        ["1.0", "Prelims", "100000.00", "0.00", "0.00", "0.00", "0.00", "100000.00"],
                    ]],
                },
                {
                    "page_num": 2,
                    "text": "VARIATION WORKS",
                    "tables": [
                        # Table 0: 8-col overflow from contract works
                        [["2.0", "Scaffolding", "50000.00", "0.00", "0.00", "0.00", "0.00", "50000.00"]],
                        # Table 1: 9-col variations
                        [["CI-01", "Extra piling", "", "5000.00", "0.00", "0.00", "0.00", "0.00", "5000.00"]],
                    ],
                },
            ],
        }
        result = parse_wbpro(raw)
        assert len(result["line_items"]) == 3
        assert result["line_items"][0]["item_type"] == "contract_work"
        assert result["line_items"][1]["item_type"] == "contract_work"  # 8-col on variation page
        assert result["line_items"][2]["item_type"] == "variation"  # 9-col


class TestParseDecimal:
    def test_plain_number(self):
        assert parse_decimal("1234.56") == "1234.56"

    def test_with_commas(self):
        assert parse_decimal("1,234,567.89") == "1234567.89"

    def test_parentheses_negative(self):
        assert parse_decimal("(1,234.56)") == "-1234.56"

    def test_none_returns_zero(self):
        assert parse_decimal(None) == "0.00"

    def test_empty_string_returns_zero(self):
        assert parse_decimal("") == "0.00"

    def test_whitespace_returns_zero(self):
        assert parse_decimal("  ") == "0.00"

    def test_dash_returns_zero(self):
        assert parse_decimal("-") == "0.00"

    def test_integer(self):
        assert parse_decimal("5000") == "5000.00"

    def test_negative_plain(self):
        assert parse_decimal("-500.00") == "-500.00"


class TestIsSkipRow:
    def test_all_empty(self):
        assert is_skip_row(["", "", None, "", "", "", "", ""]) is True

    def test_all_none(self):
        assert is_skip_row([None, None, None, None, None, None, None, None]) is True

    def test_total_row(self):
        assert is_skip_row(["", "Total Contract Works", "", "100000", "", "", "", ""]) is True

    def test_subtotal_row(self):
        assert is_skip_row(["", "Sub-Total", "", "50000", "", "", "", ""]) is True

    def test_normal_row(self):
        assert is_skip_row(["1.0", "Excavation", "100000", "50", "50000", "30000", "20000", "50000"]) is False

    def test_total_in_ref_is_not_skipped(self):
        """A row with 'Total' in the ref col but also a description is NOT a total row."""
        assert is_skip_row(["Total", "Something specific", "100000", "50", "50000", "30000", "20000", "50000"]) is False


class TestDetectSections:
    def test_single_page_contract_works(self):
        pages = [{"page_num": 1, "text": "Some header\nCONTRACT WORKS\nmore text", "tables": []}]
        result = detect_sections(pages)
        assert result == {1: SECTION_CONTRACT}

    def test_variation_on_page_2(self):
        pages = [
            {"page_num": 1, "text": "CONTRACT WORKS\nstuff", "tables": []},
            {"page_num": 2, "text": "VARIATION WORKS\nstuff", "tables": []},
        ]
        result = detect_sections(pages)
        assert result[1] == SECTION_CONTRACT
        assert result[2] == SECTION_VARIATION

    def test_provisional_sums(self):
        pages = [{"page_num": 1, "text": "PROVISIONAL SUMS\nstuff", "tables": []}]
        result = detect_sections(pages)
        assert result[1] == SECTION_PS

    def test_inherit_previous_section(self):
        """A page with no header inherits the previous page's section."""
        pages = [
            {"page_num": 1, "text": "CONTRACT WORKS\nstuff", "tables": []},
            {"page_num": 2, "text": "more items no header", "tables": []},
        ]
        result = detect_sections(pages)
        assert result[1] == SECTION_CONTRACT
        assert result[2] == SECTION_CONTRACT

    def test_multiple_sections_same_page(self):
        """When multiple section headers appear, the LAST one wins for that page."""
        pages = [{"page_num": 1, "text": "CONTRACT WORKS\nstuff\nVARIATION WORKS\nmore", "tables": []}]
        result = detect_sections(pages)
        assert result[1] == SECTION_VARIATION

    def test_no_section_header_defaults_to_contract(self):
        """First page with no header defaults to contract works."""
        pages = [{"page_num": 1, "text": "some random text", "tables": []}]
        result = detect_sections(pages)
        assert result[1] == SECTION_CONTRACT


class TestColumnMapping:
    """Verify column counts are validated per section type."""
    def test_contract_works_8_cols(self):
        from app.harness.executors.extract_wbpro import map_row_to_item
        row = ["1.0", "Excavation", "100000.00", "50.00", "50000.00", "30000.00", "20000.00", "50000.00"]
        item = map_row_to_item(row, SECTION_CONTRACT, item_index=0)
        assert item is not None
        assert item["ref_code"] == "1.0"
        assert item["description"] == "Excavation"
        assert item["contract_value"] == "100000.00"
        assert item["item_type"] == "contract_work"
        assert item["item_index"] == 0

    def test_variation_9_cols(self):
        from app.harness.executors.extract_wbpro import map_row_to_item
        row = ["CI-01", "Variation desc", "ClientRef", "5000.00", "0.00", "0.00", "0.00", "0.00", "5000.00"]
        item = map_row_to_item(row, SECTION_VARIATION, item_index=5)
        assert item is not None
        assert item["ref_code"] == "CI-01"
        assert item["description"] == "Variation desc"
        assert item["contract_value"] == "5000.00"
        assert item["item_type"] == "variation"
        assert item["item_index"] == 5

    def test_provisional_sum_8_cols(self):
        from app.harness.executors.extract_wbpro import map_row_to_item
        row = ["PS-01", "Provisional Sum Item", "25000.00", "0.00", "0.00", "0.00", "0.00", "25000.00"]
        item = map_row_to_item(row, SECTION_PS, item_index=10)
        assert item is not None
        assert item["item_type"] == "provisional_sum"

    def test_wrong_col_count_returns_none(self):
        from app.harness.executors.extract_wbpro import map_row_to_item
        row = ["1.0", "Too few cols", "100000.00"]
        item = map_row_to_item(row, SECTION_CONTRACT, item_index=0)
        assert item is None


class TestExtractMetadata:
    def test_claim_number(self):
        text = "CONTRACTOR PROGRESS CLAIM\nClaim No. 5\nPeriod From: 01/10/2025"
        result = extract_metadata(text)
        assert result["claim_number"] == "5"

    def test_claim_number_alt_format(self):
        text = "Claim Number: 12"
        result = extract_metadata(text)
        assert result["claim_number"] == "12"

    def test_period_dates(self):
        text = "Period From: 01/10/2025\nPeriod To: 31/10/2025"
        result = extract_metadata(text)
        assert result["period_from"] == "01/10/2025"
        assert result["period_to"] == "31/10/2025"

    def test_payment_due(self):
        text = "Payment Due: 18/12/2025"
        result = extract_metadata(text)
        assert result["payment_due"] == "18/12/2025"

    def test_missing_fields_return_empty_strings(self):
        text = "Nothing useful here"
        result = extract_metadata(text)
        assert result["claim_number"] == ""
        assert result["period_from"] == ""
        assert result["period_to"] == ""
        assert result["payment_due"] == ""
