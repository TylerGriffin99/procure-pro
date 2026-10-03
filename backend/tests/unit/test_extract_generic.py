"""Unit tests for the generic LLM-based line-item extractor."""
import pytest
from pydantic_ai.models.test import TestModel

from app.harness.executors.extract_generic import (
    _normalise_decimal,
    parse_generic,
    validate_and_normalise,
)


# ---------------------------------------------------------------------------
# _normalise_decimal
# ---------------------------------------------------------------------------

class TestNormaliseDecimal:
    def test_normal_value(self):
        assert _normalise_decimal("1234.56") == "1234.56"

    def test_comma_thousands(self):
        assert _normalise_decimal("1,234,567.89") == "1234567.89"

    def test_parenthesised_negative(self):
        assert _normalise_decimal("(1,234.56)") == "-1234.56"

    def test_none(self):
        assert _normalise_decimal(None) == "0.00"

    def test_empty_string(self):
        assert _normalise_decimal("") == "0.00"

    def test_dash(self):
        assert _normalise_decimal("-") == "0.00"

    def test_dollar_sign(self):
        assert _normalise_decimal("$1,234.56") == "1234.56"

    def test_integer(self):
        assert _normalise_decimal(100) == "100.00"

    def test_float(self):
        assert _normalise_decimal(99.9) == "99.90"

    def test_rounds_to_2dp(self):
        assert _normalise_decimal("1234.567") == "1234.57"


# ---------------------------------------------------------------------------
# validate_and_normalise
# ---------------------------------------------------------------------------

def _make_item(**overrides):
    """Helper: build a minimal valid line item dict with overrides."""
    base = {
        "item_index": 0,
        "ref_code": "A1",
        "description": "Test item",
        "item_type": "contract_work",
        "contract_value": "100.00",
        "percentage": "50.00",
        "ptd": "50.00",
        "previous": "30.00",
        "current": "20.00",
        "balance": "50.00",
    }
    base.update(overrides)
    return base


_SENTINEL = object()


def _make_response(items=None, metadata=_SENTINEL, summary=_SENTINEL):
    """Helper: build a minimal valid LLM response dict."""
    return {
        "metadata": {"claim_number": "5", "period_from": "01/01/25", "period_to": "31/01/25", "payment_due": "15/02/25"} if metadata is _SENTINEL else metadata,
        "line_items": items if items is not None else [_make_item()],
        "summary": {"original_contract_total": "100.00", "revised_contract_total": "100.00", "claimed_amount": "50.00"} if summary is _SENTINEL else summary,
    }


class TestValidateAndNormalise:
    def test_valid_response_passes(self):
        result = validate_and_normalise(_make_response())
        assert result["metadata"]["claim_number"] == "5"
        assert len(result["line_items"]) == 1
        assert result["line_items"][0]["item_index"] == 0

    def test_reindexes_items(self):
        """LLM may return wrong item_index values — must be overwritten to 0,1,2,..."""
        items = [
            _make_item(item_index=99, description="First"),
            _make_item(item_index=5, description="Second"),
            _make_item(item_index=42, description="Third"),
        ]
        result = validate_and_normalise(_make_response(items=items))
        indices = [i["item_index"] for i in result["line_items"]]
        assert indices == [0, 1, 2]

    def test_normalises_decimal_fields(self):
        items = [_make_item(contract_value="$1,234.56", ptd="(500.00)")]
        result = validate_and_normalise(_make_response(items=items))
        item = result["line_items"][0]
        assert item["contract_value"] == "1234.56"
        assert item["ptd"] == "-500.00"

    def test_invalid_item_type_defaults_to_contract_work(self):
        items = [_make_item(item_type="bogus_type")]
        result = validate_and_normalise(_make_response(items=items))
        assert result["line_items"][0]["item_type"] == "contract_work"

    def test_missing_decimal_fields_default_to_zero(self):
        items = [{"description": "Bare item"}]  # no decimal fields at all
        result = validate_and_normalise(_make_response(items=items))
        item = result["line_items"][0]
        for field in ("contract_value", "percentage", "ptd", "previous", "current", "balance"):
            assert item[field] == "0.00"

    def test_empty_line_items_raises(self):
        with pytest.raises(ValueError, match="line_items is empty"):
            validate_and_normalise(_make_response(items=[]))

    def test_missing_metadata_uses_defaults(self):
        result = validate_and_normalise(_make_response(metadata={}))
        for key in ("claim_number", "period_from", "period_to", "payment_due"):
            assert result["metadata"][key] == ""

    def test_summary_recomputed_when_missing(self):
        items = [
            _make_item(item_type="contract_work", contract_value="1000.00", ptd="500.00"),
            _make_item(item_type="variation", contract_value="200.00", ptd="100.00"),
        ]
        result = validate_and_normalise(_make_response(items=items, summary=None))
        assert result["summary"]["original_contract_total"] == "1000.00"
        assert result["summary"]["revised_contract_total"] == "1200.00"
        assert result["summary"]["claimed_amount"] == "600.00"

    def test_mixed_item_types_summary(self):
        """original_contract_total only counts contract_work items."""
        items = [
            _make_item(item_type="contract_work", contract_value="500.00", ptd="200.00"),
            _make_item(item_type="variation", contract_value="100.00", ptd="50.00"),
            _make_item(item_type="provisional_sum", contract_value="75.00", ptd="25.00"),
        ]
        result = validate_and_normalise(_make_response(items=items, summary=None))
        assert result["summary"]["original_contract_total"] == "500.00"
        assert result["summary"]["revised_contract_total"] == "675.00"
        assert result["summary"]["claimed_amount"] == "275.00"


# ---------------------------------------------------------------------------
# parse_generic (agent-backed extraction)
# ---------------------------------------------------------------------------

class TestParseGeneric:
    @pytest.mark.asyncio
    async def test_runs_agent_and_normalises_output(self):
        """parse_generic runs the structured agent, then normalises its typed output."""
        model = TestModel(
            custom_output_args={
                "metadata": {"claim_number": "7"},
                "line_items": [
                    {
                        "ref_code": "A1",
                        "description": "Excavation",
                        "item_type": "contract_work",
                        "contract_value": "$1,234.56",
                        "ptd": "(500.00)",
                    }
                ],
                "summary": {},
            }
        )

        result = await parse_generic({"pages": []}, model=model)

        assert result["metadata"]["claim_number"] == "7"
        assert len(result["line_items"]) == 1
        item = result["line_items"][0]
        assert item["item_index"] == 0
        assert item["contract_value"] == "1234.56"
        assert item["ptd"] == "-500.00"

    @pytest.mark.asyncio
    async def test_empty_line_items_raises(self):
        model = TestModel(custom_output_args={"metadata": {}, "line_items": [], "summary": {}})
        with pytest.raises(ValueError, match="line_items is empty"):
            await parse_generic({"pages": []}, model=model)
