"""Unit tests for the AssessmentAggregator utility."""
import uuid
from dataclasses import dataclass
from decimal import Decimal

import pytest

ZERO = Decimal("0.00")


# Lightweight stand-ins for ORM models so tests stay pure (no DB)
@dataclass
class FakeLineItem:
    id: uuid.UUID
    wbs_code_id: uuid.UUID
    claim_line_item_id: uuid.UUID | None
    description: str
    contract_sum: Decimal
    contractor_claim_to_date: Decimal
    total_recommended: Decimal
    previously_paid: Decimal
    recommended_this_period: Decimal
    variance_to_claim: Decimal
    percentage: Decimal
    status: str
    sort_order: int
    comments: str | None = None
    adjustment_type: str | None = None


@dataclass
class FakeWBS:
    id: uuid.UUID
    description: str
    contract_sum: Decimal | None


@dataclass
class FakeVariationItem:
    id: uuid.UUID
    variation_id: uuid.UUID
    claim_line_item_id: uuid.UUID | None
    contractor_claim_to_date: Decimal
    total_recommended: Decimal
    previously_paid: Decimal
    recommended_this_period: Decimal
    variance_to_claim: Decimal
    percentage: Decimal
    status: str
    adjustment_type: str | None = None


@dataclass
class FakeVariation:
    id: uuid.UUID
    contractor_ref: str
    description: str
    contractor_submission: Decimal
    ci_number: int = 1


@dataclass
class FakePSItem:
    id: uuid.UUID
    provisional_sum_id: uuid.UUID
    claim_line_item_id: uuid.UUID | None
    contractor_claim_to_date: Decimal
    total_recommended: Decimal
    previously_paid: Decimal
    recommended_this_period: Decimal
    variance_to_claim: Decimal
    percentage: Decimal
    status: str
    adjustment_type: str | None = None


@dataclass
class FakePS:
    id: uuid.UUID
    ps_number: int
    description: str
    contract_sum: Decimal


# ── Helpers ──────────────────────────────────────────────────────────────
WBS_A_ID = uuid.uuid4()
WBS_B_ID = uuid.uuid4()
VAR_A_ID = uuid.uuid4()
PS_A_ID = uuid.uuid4()


def _wbs(wbs_id: uuid.UUID = WBS_A_ID, desc: str = "Earthworks", cs: str = "100000.00") -> FakeWBS:
    return FakeWBS(id=wbs_id, description=desc, contract_sum=Decimal(cs))


def _history_row(
    wbs_id: uuid.UUID = WBS_A_ID,
    prev_paid: str = "20000.00",
    prev_claim: str = "25000.00",
) -> FakeLineItem:
    return FakeLineItem(
        id=uuid.uuid4(),
        wbs_code_id=wbs_id,
        claim_line_item_id=None,
        description="Earthworks",
        contract_sum=Decimal("100000.00"),
        contractor_claim_to_date=Decimal(prev_claim),
        total_recommended=Decimal(prev_paid),
        previously_paid=Decimal(prev_paid),
        recommended_this_period=ZERO,
        variance_to_claim=Decimal(prev_paid) - Decimal(prev_claim),
        percentage=ZERO,
        status="approved",
        sort_order=0,
    )


def _child_row(
    wbs_id: uuid.UUID = WBS_A_ID,
    current: str = "5000.00",
    sort_order: int = 10,
) -> FakeLineItem:
    return FakeLineItem(
        id=uuid.uuid4(),
        wbs_code_id=wbs_id,
        claim_line_item_id=uuid.uuid4(),
        description="Excavation work",
        contract_sum=ZERO,
        contractor_claim_to_date=Decimal(current),
        total_recommended=Decimal(current),
        previously_paid=ZERO,
        recommended_this_period=Decimal(current),
        variance_to_claim=ZERO,
        percentage=ZERO,
        status="unapproved",
        sort_order=sort_order,
    )


# ── Tests ────────────────────────────────────────────────────────────────

class TestAggregateLineItems:
    """Tests for aggregate_line_items()."""

    def test_history_plus_children(self):
        """History row + 2 children aggregated correctly."""
        from app.utils.assessment_aggregator import aggregate_line_items

        history = _history_row(prev_paid="20000.00", prev_claim="25000.00")
        child1 = _child_row(current="5000.00", sort_order=10)
        child2 = _child_row(current="3000.00", sort_order=11)
        wbs = [_wbs(cs="100000.00")]

        groups = aggregate_line_items([history, child1, child2], wbs)

        assert len(groups) == 1
        g = groups[0]
        assert g.wbs_code_id == WBS_A_ID
        assert g.contract_sum == Decimal("100000.00")
        assert g.previously_paid == Decimal("20000.00")
        assert g.recommended_this_period == Decimal("8000.00")
        assert g.total_recommended == Decimal("28000.00")
        assert g.contractor_claim_to_date == Decimal("33000.00")  # 25000 + 5000 + 3000
        assert g.variance_to_claim == Decimal("-5000.00")  # 28000 - 33000
        assert g.percentage == Decimal("28.00")  # 28000/100000*100
        assert g.history_row is history
        assert g.child_rows == [child1, child2]

    def test_history_only_no_children(self):
        """Group with only a history row (no current claim items)."""
        from app.utils.assessment_aggregator import aggregate_line_items

        history = _history_row(prev_paid="50000.00", prev_claim="50000.00")
        wbs = [_wbs(cs="100000.00")]

        groups = aggregate_line_items([history], wbs)

        assert len(groups) == 1
        g = groups[0]
        assert g.previously_paid == Decimal("50000.00")
        assert g.recommended_this_period == ZERO
        assert g.total_recommended == Decimal("50000.00")
        assert g.contractor_claim_to_date == Decimal("50000.00")
        assert g.variance_to_claim == ZERO
        assert g.child_rows == []

    def test_children_only_first_claim(self):
        """First claim — no history row, only child rows."""
        from app.utils.assessment_aggregator import aggregate_line_items

        child1 = _child_row(current="10000.00", sort_order=0)
        child2 = _child_row(current="5000.00", sort_order=1)
        wbs = [_wbs(cs="100000.00")]

        groups = aggregate_line_items([child1, child2], wbs)

        assert len(groups) == 1
        g = groups[0]
        assert g.history_row is None
        assert g.previously_paid == ZERO
        assert g.recommended_this_period == Decimal("15000.00")
        assert g.total_recommended == Decimal("15000.00")
        assert g.contract_sum == Decimal("100000.00")  # from WBS master

    def test_contract_sum_from_master_not_rows(self):
        """contract_sum is sourced from WBS master record, not from row data."""
        from app.utils.assessment_aggregator import aggregate_line_items

        history = _history_row()
        # Row has contract_sum=100000 but master says 150000
        wbs = [_wbs(cs="150000.00")]

        groups = aggregate_line_items([history], wbs)

        assert groups[0].contract_sum == Decimal("150000.00")

    def test_multiple_wbs_groups(self):
        """Multiple WBS groups separated correctly."""
        from app.utils.assessment_aggregator import aggregate_line_items

        h_a = _history_row(wbs_id=WBS_A_ID, prev_paid="10000.00", prev_claim="10000.00")
        c_a = _child_row(wbs_id=WBS_A_ID, current="5000.00")
        h_b = _history_row(wbs_id=WBS_B_ID, prev_paid="30000.00", prev_claim="30000.00")
        h_b.description = "Concrete"

        wbs_a = _wbs(wbs_id=WBS_A_ID, desc="Earthworks", cs="100000.00")
        wbs_b = _wbs(wbs_id=WBS_B_ID, desc="Concrete", cs="200000.00")

        groups = aggregate_line_items([h_a, c_a, h_b], [wbs_a, wbs_b])

        assert len(groups) == 2
        ga = next(g for g in groups if g.wbs_code_id == WBS_A_ID)
        gb = next(g for g in groups if g.wbs_code_id == WBS_B_ID)
        assert ga.total_recommended == Decimal("15000.00")
        assert gb.total_recommended == Decimal("30000.00")
        assert gb.contract_sum == Decimal("200000.00")

    def test_zero_contract_sum_percentage(self):
        """Percentage is ZERO when contract_sum is zero or None."""
        from app.utils.assessment_aggregator import aggregate_line_items

        child = _child_row(current="5000.00")
        wbs = FakeWBS(id=WBS_A_ID, description="Misc", contract_sum=None)

        groups = aggregate_line_items([child], [wbs])

        assert groups[0].percentage == ZERO

    def test_description_from_history_row(self):
        """Group description comes from history row when present."""
        from app.utils.assessment_aggregator import aggregate_line_items

        history = _history_row()
        history.description = "Earthworks (QS adjusted)"
        child = _child_row()
        child.description = "Excavation subitem"
        wbs = [_wbs()]

        groups = aggregate_line_items([history, child], wbs)

        assert groups[0].description == "Earthworks (QS adjusted)"

    def test_history_with_nonzero_rtp_no_children(self):
        """History row with its own recommended_this_period (e.g. Claim 1 finalised assessment)."""
        from app.utils.assessment_aggregator import aggregate_line_items

        # Claim 1 scenario: history-style row has prev_paid=0, rtp=15000
        history = FakeLineItem(
            id=uuid.uuid4(),
            wbs_code_id=WBS_A_ID,
            claim_line_item_id=None,
            description="Earthworks",
            contract_sum=Decimal("100000.00"),
            contractor_claim_to_date=Decimal("18000.00"),
            total_recommended=Decimal("15000.00"),
            previously_paid=ZERO,
            recommended_this_period=Decimal("15000.00"),
            variance_to_claim=Decimal("-3000.00"),
            percentage=ZERO,
            status="approved",
            sort_order=0,
        )
        wbs = [_wbs(cs="100000.00")]

        groups = aggregate_line_items([history], wbs)

        assert len(groups) == 1
        g = groups[0]
        assert g.previously_paid == ZERO
        assert g.recommended_this_period == Decimal("15000.00")
        assert g.total_recommended == Decimal("15000.00")
        assert g.contractor_claim_to_date == Decimal("18000.00")
        assert g.variance_to_claim == Decimal("-3000.00")

    def test_description_from_wbs_when_no_history(self):
        """Group description comes from WBS master when no history row."""
        from app.utils.assessment_aggregator import aggregate_line_items

        child = _child_row()
        child.description = "Excavation subitem"
        wbs = [_wbs(desc="Earthworks")]

        groups = aggregate_line_items([child], wbs)

        assert groups[0].description == "Earthworks"


class TestAggregateVariations:
    """Tests for aggregate_variations()."""

    def test_history_plus_child(self):
        from app.utils.assessment_aggregator import aggregate_variations

        history = FakeVariationItem(
            id=uuid.uuid4(), variation_id=VAR_A_ID, claim_line_item_id=None,
            contractor_claim_to_date=Decimal("10000.00"), total_recommended=Decimal("8000.00"),
            previously_paid=Decimal("8000.00"), recommended_this_period=ZERO,
            variance_to_claim=Decimal("-2000.00"), percentage=ZERO, status="approved",
        )
        child = FakeVariationItem(
            id=uuid.uuid4(), variation_id=VAR_A_ID, claim_line_item_id=uuid.uuid4(),
            contractor_claim_to_date=Decimal("5000.00"), total_recommended=Decimal("5000.00"),
            previously_paid=ZERO, recommended_this_period=Decimal("5000.00"),
            variance_to_claim=ZERO, percentage=ZERO, status="unapproved",
        )
        master = FakeVariation(
            id=VAR_A_ID, contractor_ref="CI-001", description="Extra steel",
            contractor_submission=Decimal("20000.00"),
        )

        groups = aggregate_variations([history, child], [master])

        assert len(groups) == 1
        g = groups[0]
        assert g.variation_id == VAR_A_ID
        assert g.contractor_ref == "CI-001"
        assert g.contractor_submission == Decimal("20000.00")
        assert g.previously_paid == Decimal("8000.00")
        assert g.recommended_this_period == Decimal("5000.00")
        assert g.total_recommended == Decimal("13000.00")
        assert g.contractor_claim_to_date == Decimal("15000.00")
        assert g.variance_to_claim == Decimal("-2000.00")
        assert g.percentage == Decimal("65.00")  # 13000/20000*100

    def test_child_only_first_claim(self):
        from app.utils.assessment_aggregator import aggregate_variations

        child = FakeVariationItem(
            id=uuid.uuid4(), variation_id=VAR_A_ID, claim_line_item_id=uuid.uuid4(),
            contractor_claim_to_date=Decimal("5000.00"), total_recommended=Decimal("5000.00"),
            previously_paid=ZERO, recommended_this_period=Decimal("5000.00"),
            variance_to_claim=ZERO, percentage=ZERO, status="unapproved",
        )
        master = FakeVariation(
            id=VAR_A_ID, contractor_ref="CI-001", description="Extra steel",
            contractor_submission=Decimal("20000.00"),
        )

        groups = aggregate_variations([child], [master])

        assert len(groups) == 1
        g = groups[0]
        assert g.history_row is None
        assert g.previously_paid == ZERO
        assert g.total_recommended == Decimal("5000.00")


class TestAggregateProvisionalSums:
    """Tests for aggregate_provisional_sums()."""

    def test_history_plus_child(self):
        from app.utils.assessment_aggregator import aggregate_provisional_sums

        history = FakePSItem(
            id=uuid.uuid4(), provisional_sum_id=PS_A_ID, claim_line_item_id=None,
            contractor_claim_to_date=Decimal("15000.00"), total_recommended=Decimal("12000.00"),
            previously_paid=Decimal("12000.00"), recommended_this_period=ZERO,
            variance_to_claim=Decimal("-3000.00"), percentage=ZERO, status="approved",
        )
        child = FakePSItem(
            id=uuid.uuid4(), provisional_sum_id=PS_A_ID, claim_line_item_id=uuid.uuid4(),
            contractor_claim_to_date=Decimal("3000.00"), total_recommended=Decimal("3000.00"),
            previously_paid=ZERO, recommended_this_period=Decimal("3000.00"),
            variance_to_claim=ZERO, percentage=ZERO, status="unapproved",
        )
        master = FakePS(
            id=PS_A_ID, ps_number=1, description="Fence removal",
            contract_sum=Decimal("25000.00"),
        )

        groups = aggregate_provisional_sums([history, child], [master])

        assert len(groups) == 1
        g = groups[0]
        assert g.provisional_sum_id == PS_A_ID
        assert g.ps_number == 1
        assert g.contract_sum == Decimal("25000.00")
        assert g.previously_paid == Decimal("12000.00")
        assert g.recommended_this_period == Decimal("3000.00")
        assert g.total_recommended == Decimal("15000.00")
        assert g.contractor_claim_to_date == Decimal("18000.00")
        assert g.percentage == Decimal("60.00")  # 15000/25000*100


    def test_variation_history_with_nonzero_rtp_no_children(self):
        """Variation history row with its own recommended_this_period (Claim 1 finalised)."""
        from app.utils.assessment_aggregator import aggregate_variations

        history = FakeVariationItem(
            id=uuid.uuid4(), variation_id=VAR_A_ID, claim_line_item_id=None,
            contractor_claim_to_date=Decimal("10069.49"), total_recommended=Decimal("10069.49"),
            previously_paid=ZERO, recommended_this_period=Decimal("10069.49"),
            variance_to_claim=ZERO, percentage=ZERO, status="approved",
        )
        master = FakeVariation(
            id=VAR_A_ID, contractor_ref="CI-002", description="Extra steel",
            contractor_submission=Decimal("20000.00"),
        )

        groups = aggregate_variations([history], [master])

        assert len(groups) == 1
        g = groups[0]
        assert g.previously_paid == ZERO
        assert g.recommended_this_period == Decimal("10069.49")
        assert g.total_recommended == Decimal("10069.49")


    def test_ps_history_with_nonzero_rtp_no_children(self):
        """PS history row with its own recommended_this_period (Claim 1 finalised)."""
        from app.utils.assessment_aggregator import aggregate_provisional_sums

        history = FakePSItem(
            id=uuid.uuid4(), provisional_sum_id=PS_A_ID, claim_line_item_id=None,
            contractor_claim_to_date=Decimal("7114.38"), total_recommended=Decimal("5384.38"),
            previously_paid=ZERO, recommended_this_period=Decimal("5384.38"),
            variance_to_claim=Decimal("-1730.00"), percentage=ZERO, status="approved",
        )
        master = FakePS(
            id=PS_A_ID, ps_number=1, description="Fence removal",
            contract_sum=Decimal("25000.00"),
        )

        groups = aggregate_provisional_sums([history], [master])

        assert len(groups) == 1
        g = groups[0]
        assert g.previously_paid == ZERO
        assert g.recommended_this_period == Decimal("5384.38")
        assert g.total_recommended == Decimal("5384.38")


class TestComputeAssessmentTotals:
    """Tests for compute_assessment_totals()."""

    def test_totals_across_all_types(self):
        from app.utils.assessment_aggregator import (
            aggregate_line_items,
            aggregate_variations,
            aggregate_provisional_sums,
            compute_assessment_totals,
        )

        # WBS: 28000 total_recommended, 33000 claimed
        history = _history_row(prev_paid="20000.00", prev_claim="25000.00")
        child = _child_row(current="8000.00")
        wbs_groups = aggregate_line_items([history, child], [_wbs(cs="100000.00")])

        # Variation: 13000 total_recommended, 15000 claimed
        var_h = FakeVariationItem(
            id=uuid.uuid4(), variation_id=VAR_A_ID, claim_line_item_id=None,
            contractor_claim_to_date=Decimal("10000.00"), total_recommended=Decimal("8000.00"),
            previously_paid=Decimal("8000.00"), recommended_this_period=ZERO,
            variance_to_claim=Decimal("-2000.00"), percentage=ZERO, status="approved",
        )
        var_c = FakeVariationItem(
            id=uuid.uuid4(), variation_id=VAR_A_ID, claim_line_item_id=uuid.uuid4(),
            contractor_claim_to_date=Decimal("5000.00"), total_recommended=Decimal("5000.00"),
            previously_paid=ZERO, recommended_this_period=Decimal("5000.00"),
            variance_to_claim=ZERO, percentage=ZERO, status="unapproved",
        )
        var_master = FakeVariation(
            id=VAR_A_ID, contractor_ref="CI-001", description="Steel",
            contractor_submission=Decimal("20000.00"),
        )
        var_groups = aggregate_variations([var_h, var_c], [var_master])

        # PS: 15000 total_recommended, 18000 claimed
        ps_h = FakePSItem(
            id=uuid.uuid4(), provisional_sum_id=PS_A_ID, claim_line_item_id=None,
            contractor_claim_to_date=Decimal("15000.00"), total_recommended=Decimal("12000.00"),
            previously_paid=Decimal("12000.00"), recommended_this_period=ZERO,
            variance_to_claim=Decimal("-3000.00"), percentage=ZERO, status="approved",
        )
        ps_c = FakePSItem(
            id=uuid.uuid4(), provisional_sum_id=PS_A_ID, claim_line_item_id=uuid.uuid4(),
            contractor_claim_to_date=Decimal("3000.00"), total_recommended=Decimal("3000.00"),
            previously_paid=ZERO, recommended_this_period=Decimal("3000.00"),
            variance_to_claim=ZERO, percentage=ZERO, status="unapproved",
        )
        ps_master = FakePS(
            id=PS_A_ID, ps_number=1, description="Fence",
            contract_sum=Decimal("25000.00"),
        )
        ps_groups = aggregate_provisional_sums([ps_h, ps_c], [ps_master])

        totals = compute_assessment_totals(wbs_groups, var_groups, ps_groups)

        assert totals.sub_contract_works == Decimal("28000.00")
        assert totals.approved_variation_orders == Decimal("13000.00")
        assert totals.adjustment_to_provisional_sums == Decimal("15000.00")
        assert totals.total_recommended == Decimal("56000.00")
        assert totals.value_claimed_to_date == Decimal("66000.00")
        assert totals.adjustments == Decimal("-10000.00")
