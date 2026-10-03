"""
Unit tests for contractor acceptance detection in history row creation.

Tests that when a contractor's `previous` value on a new claim is lower than
the stored `contractor_claim_to_date` from the previous assessment, the history
row uses the contractor's accepted value.
"""
from decimal import Decimal

import pytest

ZERO = Decimal("0.00")


def apply_acceptance(
    prev_contractor_claim: Decimal,
    claim_prev: Decimal | None,
) -> Decimal:
    """
    Replicate the acceptance logic from create_records.py.

    If the contractor's `previous` (from the new claim) is lower than our
    stored contractor_claim_to_date, the contractor accepted the QS valuation.
    """
    if claim_prev is not None and claim_prev < prev_contractor_claim:
        return claim_prev
    return prev_contractor_claim


class TestContractorAcceptance:
    """Tests for the acceptance detection rule."""

    def test_acceptance_lower_value(self):
        """Contractor accepted QS valuation: previous < stored."""
        result = apply_acceptance(
            prev_contractor_claim=Decimal("7114.38"),
            claim_prev=Decimal("5384.38"),
        )
        assert result == Decimal("5384.38")

    def test_no_acceptance_equal(self):
        """No acceptance: contractor's previous equals stored value."""
        result = apply_acceptance(
            prev_contractor_claim=Decimal("5000.00"),
            claim_prev=Decimal("5000.00"),
        )
        assert result == Decimal("5000.00")

    def test_no_acceptance_higher(self):
        """No acceptance: contractor's previous is higher than stored."""
        result = apply_acceptance(
            prev_contractor_claim=Decimal("5000.00"),
            claim_prev=Decimal("6000.00"),
        )
        assert result == Decimal("5000.00")

    def test_no_claim_items_this_period(self):
        """No claim items for this WBS/var/PS: claim_prev is None."""
        result = apply_acceptance(
            prev_contractor_claim=Decimal("7114.38"),
            claim_prev=None,
        )
        assert result == Decimal("7114.38")

    def test_acceptance_to_zero(self):
        """Contractor accepted down to zero."""
        result = apply_acceptance(
            prev_contractor_claim=Decimal("1000.00"),
            claim_prev=ZERO,
        )
        assert result == ZERO

    def test_no_previous_assessment(self):
        """First claim: no previous assessment means stored is zero."""
        result = apply_acceptance(
            prev_contractor_claim=ZERO,
            claim_prev=ZERO,
        )
        assert result == ZERO


class TestClaimPreviousAggregation:
    """Tests for summing `previous` across multiple claim items per group."""

    def test_multiple_items_sum_below_stored(self):
        """Two claim items mapped to same parent, sum of previous < stored."""
        claim_prev_by_parent: dict[str, Decimal] = {}
        items = [
            {"parent_id": "wbs-1", "previous": Decimal("1000.00")},
            {"parent_id": "wbs-1", "previous": Decimal("2000.00")},
        ]
        for item in items:
            pid = item["parent_id"]
            claim_prev_by_parent[pid] = claim_prev_by_parent.get(pid, ZERO) + item["previous"]

        assert claim_prev_by_parent["wbs-1"] == Decimal("3000.00")

        result = apply_acceptance(
            prev_contractor_claim=Decimal("5000.00"),
            claim_prev=claim_prev_by_parent["wbs-1"],
        )
        assert result == Decimal("3000.00")

    def test_multiple_items_sum_above_stored(self):
        """Two claim items mapped to same parent, sum of previous > stored."""
        claim_prev_by_parent: dict[str, Decimal] = {}
        items = [
            {"parent_id": "wbs-1", "previous": Decimal("3000.00")},
            {"parent_id": "wbs-1", "previous": Decimal("4000.00")},
        ]
        for item in items:
            pid = item["parent_id"]
            claim_prev_by_parent[pid] = claim_prev_by_parent.get(pid, ZERO) + item["previous"]

        assert claim_prev_by_parent["wbs-1"] == Decimal("7000.00")

        result = apply_acceptance(
            prev_contractor_claim=Decimal("5000.00"),
            claim_prev=claim_prev_by_parent["wbs-1"],
        )
        assert result == Decimal("5000.00")
