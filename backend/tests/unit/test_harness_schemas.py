"""Unit tests for harness structured-output schemas."""
import json

import pytest
from pydantic import TypeAdapter, ValidationError

from app.harness.schemas import GenericExtraction, VpsMatch, WbsMatch


class TestWbsMatch:
    def test_has_fields_create_records_consumes(self):
        m = WbsMatch(
            item_index=0,
            wbs_code_id="11111111-1111-1111-1111-111111111111",
            wbs_code="DM-01",
            wbs_description="Demolition Works",
            parent_code="DM",
            is_new=False,
            confidence=0.95,
        )
        dumped = m.model_dump()
        assert set(dumped) == {
            "item_index", "wbs_code_id", "wbs_code", "wbs_description",
            "parent_code", "is_new", "confidence",
        }

    def test_wbs_code_id_nullable_for_new_proposals(self):
        m = WbsMatch(item_index=1, wbs_code_id=None, wbs_code="DM-03", is_new=True, confidence=0.6)
        assert m.wbs_code_id is None

    def test_list_serializes_to_bare_json_array(self):
        matches = [WbsMatch(item_index=0, wbs_code="DM-01", is_new=False, confidence=0.9)]
        raw = TypeAdapter(list[WbsMatch]).dump_json(matches).decode()
        parsed = json.loads(raw)
        assert isinstance(parsed, list)
        assert parsed[0]["item_index"] == 0

    def test_confidence_is_required(self):
        """An omitted confidence must fail loudly, not silently read as 0.0."""
        with pytest.raises(ValidationError):
            WbsMatch(item_index=0, wbs_code="DM-01")

    def test_confidence_out_of_range_rejected(self):
        with pytest.raises(ValidationError):
            WbsMatch(item_index=0, wbs_code="DM-01", confidence=1.5)

    def test_negative_item_index_rejected(self):
        with pytest.raises(ValidationError):
            WbsMatch(item_index=-1, wbs_code="DM-01", confidence=0.9)


class TestVpsMatch:
    def test_valid_item_types(self):
        assert VpsMatch(item_index=1, item_type="variation", confidence=0.8).item_type == "variation"
        assert VpsMatch(item_index=2, item_type="provisional_sum", confidence=0.8).item_type == "provisional_sum"

    def test_rejects_invalid_item_type(self):
        with pytest.raises(ValidationError):
            VpsMatch(item_index=1, item_type="contract_work", confidence=0.8)

    def test_matched_id_nullable(self):
        assert VpsMatch(item_index=1, item_type="variation", matched_id=None, confidence=0.5).matched_id is None


class TestGenericExtraction:
    def test_model_dump_shape_matches_validate_and_normalise_input(self):
        extraction = GenericExtraction(
            metadata={"claim_number": "5"},
            line_items=[{"ref_code": "A1", "description": "x", "item_type": "contract_work"}],
            summary={"claimed_amount": "50.00"},
        )
        dumped = extraction.model_dump()
        assert set(dumped) == {"metadata", "line_items", "summary"}
        assert dumped["line_items"][0]["ref_code"] == "A1"

    def test_requires_line_items(self):
        with pytest.raises(ValidationError):
            GenericExtraction(metadata={}, summary={})
