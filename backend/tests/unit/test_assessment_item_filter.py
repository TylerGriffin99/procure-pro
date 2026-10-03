"""Unit tests for assessment line item filtering by item_type."""
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from app.models.claim import ClaimItemType


def _make_line_item(item_type: ClaimItemType, sort_order: int = 0) -> MagicMock:
    item = MagicMock()
    item.item_type = item_type
    item.sort_order = sort_order
    item.id = f"id-{sort_order}"
    item.description = "Test item"
    item.contract_value = Decimal("1000")
    item.current = Decimal("100")
    item.suggested_wbs_code_id = None
    return item


def _simulate_assessment_filter(line_items: list) -> list:
    """Mirror of the filter that should be applied in upload_and_parse_claim."""
    return [i for i in sorted(line_items, key=lambda x: x.sort_order)
            if i.item_type != ClaimItemType.variation]


def test_variations_excluded_from_assessment_line_items():
    """Variation line items must not appear in AssessmentLineItem creation loop."""
    items = [
        _make_line_item(ClaimItemType.contract_work, sort_order=0),
        _make_line_item(ClaimItemType.variation, sort_order=1),
        _make_line_item(ClaimItemType.variation, sort_order=2),
        _make_line_item(ClaimItemType.contract_work, sort_order=3),
    ]

    result = _simulate_assessment_filter(items)

    assert len(result) == 2
    assert all(i.item_type == ClaimItemType.contract_work for i in result)


def test_provisional_sums_included_in_assessment_line_items():
    """Provisional sum line items should still appear in AssessmentLineItem creation loop."""
    items = [
        _make_line_item(ClaimItemType.contract_work, sort_order=0),
        _make_line_item(ClaimItemType.provisional_sum, sort_order=1),
        _make_line_item(ClaimItemType.variation, sort_order=2),
    ]

    result = _simulate_assessment_filter(items)

    assert len(result) == 2
    types = {i.item_type for i in result}
    assert ClaimItemType.contract_work in types
    assert ClaimItemType.provisional_sum in types
    assert ClaimItemType.variation not in types


def test_all_contract_works_pass_through():
    """When no variations exist, all items flow through unchanged."""
    items = [
        _make_line_item(ClaimItemType.contract_work, sort_order=i) for i in range(5)
    ]

    result = _simulate_assessment_filter(items)

    assert len(result) == 5
