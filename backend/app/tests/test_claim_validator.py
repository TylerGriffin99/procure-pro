import uuid
from decimal import Decimal

import pytest

from app.utils.pdf_parser import ParsedClaim, ParsedLineItem, ParsedSummary
from app.utils.claim_validator import (
    validate_parsed_claim,
    validate_provisional_sum_discrepancies,
    validate_variation_status_warnings,
    ValidationResult,
)


def _make_item(
    ref_code="1000",
    description="Test Item",
    item_type="contract_work",
    contract_value=Decimal("100000"),
    percentage=Decimal("50"),
    ptd=Decimal("50000"),
    previous=Decimal("30000"),
    current=Decimal("20000"),
    balance=Decimal("50000"),
    section_title="Contract Works",
) -> ParsedLineItem:
    return ParsedLineItem(
        ref_code=ref_code,
        description=description,
        item_type=item_type,
        contract_value=contract_value,
        percentage=percentage,
        ptd=ptd,
        previous=previous,
        current=current,
        balance=balance,
        section_title=section_title,
    )


def _make_claim(
    line_items: list[ParsedLineItem] | None = None,
    summary: ParsedSummary | None = None,
) -> ParsedClaim:
    items = line_items if line_items is not None else [_make_item()]
    return ParsedClaim(
        claim_number=1,
        project_name="Test Project",
        contractor_name="Test Contractor",
        job_number="J001",
        period_from="01/01/26",
        period_to="31/01/26",
        payment_due=None,
        line_items=items,
        summary=summary or ParsedSummary(
            original_contract_total=sum(
                i.contract_value for i in items if i.item_type == "contract_work"
            ),
            variations_total=sum(
                i.contract_value for i in items if i.item_type == "variation"
            ),
        ),
    )


def _make_claim_line_item(
    item_type="contract_work",
    provisional_sum_id=None,
    variation_id=None,
    contract_value=Decimal("100000"),
    description="Test Item",
    ref_code="1000",
):
    """Lightweight stand-in for ClaimLineItem (no DB needed)."""
    class FakeClaimLineItem:
        pass
    item = FakeClaimLineItem()
    item.item_type = item_type
    item.provisional_sum_id = provisional_sum_id
    item.variation_id = variation_id
    item.contract_value = contract_value
    item.description = description
    item.ref_code = ref_code
    item.warnings = []
    return item


def _make_provisional_sum(id=None, contract_sum=Decimal("25000")):
    """Lightweight stand-in for ProvisionalSum."""
    class FakePS:
        pass
    ps = FakePS()
    ps.id = id or uuid.uuid4()
    ps.contract_sum = contract_sum
    return ps


def _make_variation(id=None, status="unapproved"):
    """Lightweight stand-in for Variation."""
    class FakeVariation:
        pass
    v = FakeVariation()
    v.id = id or uuid.uuid4()
    v.status = status
    return v


class TestPerItemValidation:
    def test_clean_item_no_warnings(self):
        result = validate_parsed_claim(_make_claim())
        assert result.item_warnings == {}

    def test_percentage_over_100(self):
        item = _make_item(percentage=Decimal("145"))
        result = validate_parsed_claim(_make_claim([item]))
        assert any("145" in w and "100%" in w for w in result.item_warnings["1000"])

    def test_percentage_negative(self):
        item = _make_item(percentage=Decimal("-5"))
        result = validate_parsed_claim(_make_claim([item]))
        assert any("-5" in w for w in result.item_warnings["1000"])

    def test_current_exceeds_balance_is_not_a_warning(self):
        """In WBPRO, balance = contract_value - ptd. When >50% is claimed in one
        period, current naturally exceeds balance. This is not an error."""
        item = _make_item(
            contract_value=Decimal("50565"),
            percentage=Decimal("70"),
            ptd=Decimal("35395.50"),
            previous=Decimal("0"),
            current=Decimal("35395.50"),
            balance=Decimal("15169.50"),
        )
        result = validate_parsed_claim(_make_claim([item]))
        assert "1000" not in result.item_warnings

    def test_current_exceeds_contract_value(self):
        item = _make_item(current=Decimal("150000"), contract_value=Decimal("100000"))
        result = validate_parsed_claim(_make_claim([item]))
        assert any("exceeds contract value" in w for w in result.item_warnings["1000"])

    def test_ptd_exceeds_contract_value(self):
        item = _make_item(ptd=Decimal("120000"), contract_value=Decimal("100000"))
        result = validate_parsed_claim(_make_claim([item]))
        assert any("Paid to date" in w for w in result.item_warnings["1000"])

    def test_negative_contract_value(self):
        item = _make_item(contract_value=Decimal("-5000"))
        result = validate_parsed_claim(_make_claim([item]))
        assert any("Negative contract value" in w for w in result.item_warnings["1000"])

    def test_all_zero_values(self):
        item = _make_item(
            contract_value=Decimal("0"),
            percentage=Decimal("0"),
            ptd=Decimal("0"),
            previous=Decimal("0"),
            current=Decimal("0"),
            balance=Decimal("0"),
        )
        result = validate_parsed_claim(_make_claim([item]))
        assert any("zero" in w for w in result.item_warnings["1000"])

    def test_multiple_warnings_on_same_item(self):
        item = _make_item(percentage=Decimal("200"), contract_value=Decimal("-1000"))
        result = validate_parsed_claim(_make_claim([item]))
        assert len(result.item_warnings["1000"]) >= 2

    def test_item_without_ref_code_uses_description(self):
        item = _make_item(ref_code=None, description="Special Item")
        item.contract_value = Decimal("-500")
        result = validate_parsed_claim(_make_claim([item]))
        assert "Special Item" in result.item_warnings


class TestClaimLevelValidation:
    def test_no_line_items(self):
        result = validate_parsed_claim(_make_claim(line_items=[]))
        assert any("No line items" in w for w in result.claim_warnings)

    def test_contract_works_sum_mismatch(self):
        items = [_make_item(contract_value=Decimal("100000"))]
        summary = ParsedSummary(original_contract_total=Decimal("200000"))
        result = validate_parsed_claim(_make_claim(items, summary))
        assert any("Contract work items sum" in w for w in result.claim_warnings)

    def test_contract_works_sum_within_tolerance(self):
        items = [_make_item(contract_value=Decimal("100000.01"))]
        summary = ParsedSummary(original_contract_total=Decimal("100000"))
        result = validate_parsed_claim(_make_claim(items, summary))
        assert not any("Contract work items sum" in w for w in result.claim_warnings)

    def test_variations_sum_mismatch(self):
        items = [
            _make_item(ref_code="1", item_type="variation", contract_value=Decimal("50000")),
        ]
        summary = ParsedSummary(
            original_contract_total=Decimal("0"),
            variations_total=Decimal("80000"),
        )
        result = validate_parsed_claim(_make_claim(items, summary))
        assert any("Variation items sum" in w for w in result.claim_warnings)

    def test_revised_total_inconsistency(self):
        items = [_make_item(contract_value=Decimal("100000"))]
        summary = ParsedSummary(
            original_contract_total=Decimal("100000"),
            variations_total=Decimal("20000"),
            revised_contract_total=Decimal("150000"),  # should be 120000
        )
        result = validate_parsed_claim(_make_claim(items, summary))
        assert any("revised_contract_total" in w for w in result.claim_warnings)

    def test_clean_claim_no_warnings(self):
        items = [
            _make_item(ref_code="1000", contract_value=Decimal("80000")),
            _make_item(ref_code="2000", contract_value=Decimal("20000"), ptd=Decimal("10000"), previous=Decimal("5000"), current=Decimal("5000"), balance=Decimal("10000")),
        ]
        summary = ParsedSummary(
            original_contract_total=Decimal("100000"),
            variations_total=Decimal("0"),
            revised_contract_total=Decimal("100000"),
        )
        result = validate_parsed_claim(_make_claim(items, summary))
        assert result.claim_warnings == []
        assert result.item_warnings == {}


class TestProvisionalSumValidation:
    def test_ps_group_total_exceeds_allocation(self):
        """When claim items matched to a PS sum to more than PS.contract_sum, warn."""
        ps_id = uuid.uuid4()
        claim_items = [
            _make_claim_line_item(
                item_type="provisional_sum",
                provisional_sum_id=ps_id,
                contract_value=Decimal("18000"),
                description="PS - Remedial walls north",
            ),
            _make_claim_line_item(
                item_type="provisional_sum",
                provisional_sum_id=ps_id,
                contract_value=Decimal("15000"),
                description="PS - Remedial walls south",
            ),
        ]
        provisional_sums = [
            _make_provisional_sum(id=ps_id, contract_sum=Decimal("25000")),
        ]

        warnings = validate_provisional_sum_discrepancies(
            claim_items, Decimal("150000"), provisional_sums,
        )

        # Both items should have warnings since they belong to the exceeding group
        assert len(warnings.item_warnings) > 0
        all_warnings = [w for ws in warnings.item_warnings.values() for w in ws]
        assert any("33,000" in w and "25,000" in w for w in all_warnings)

    def test_ps_group_within_allocation_no_warning(self):
        """When PS group total is within allocation, no warning."""
        ps_id = uuid.uuid4()
        claim_items = [
            _make_claim_line_item(
                item_type="provisional_sum",
                provisional_sum_id=ps_id,
                contract_value=Decimal("12000"),
                description="PS - Remedial walls north",
            ),
            _make_claim_line_item(
                item_type="provisional_sum",
                provisional_sum_id=ps_id,
                contract_value=Decimal("13000"),
                description="PS - Remedial walls south",
            ),
        ]
        provisional_sums = [
            _make_provisional_sum(id=ps_id, contract_sum=Decimal("25000")),
        ]

        warnings = validate_provisional_sum_discrepancies(
            claim_items, Decimal("150000"), provisional_sums,
        )

        assert warnings.item_warnings == {}
        assert warnings.claim_warnings == []

    def test_aggregate_ps_exceeds_project_total(self):
        """When total PS claimed exceeds project.provisional_sum_total, claim-level warning."""
        ps_id_1 = uuid.uuid4()
        ps_id_2 = uuid.uuid4()
        claim_items = [
            _make_claim_line_item(
                item_type="provisional_sum",
                provisional_sum_id=ps_id_1,
                contract_value=Decimal("90000"),
                description="PS - Item A",
            ),
            _make_claim_line_item(
                item_type="provisional_sum",
                provisional_sum_id=ps_id_2,
                contract_value=Decimal("70000"),
                description="PS - Item B",
            ),
        ]
        provisional_sums = [
            _make_provisional_sum(id=ps_id_1, contract_sum=Decimal("100000")),
            _make_provisional_sum(id=ps_id_2, contract_sum=Decimal("100000")),
        ]

        warnings = validate_provisional_sum_discrepancies(
            claim_items, Decimal("150000"), provisional_sums,
        )

        assert any("160,000" in w and "150,000" in w for w in warnings.claim_warnings)

    def test_aggregate_ps_within_project_total_no_warning(self):
        """When total PS claimed is within project total, no claim-level warning."""
        ps_id = uuid.uuid4()
        claim_items = [
            _make_claim_line_item(
                item_type="provisional_sum",
                provisional_sum_id=ps_id,
                contract_value=Decimal("140000"),
                description="PS - Item A",
            ),
        ]
        provisional_sums = [
            _make_provisional_sum(id=ps_id, contract_sum=Decimal("150000")),
        ]

        warnings = validate_provisional_sum_discrepancies(
            claim_items, Decimal("150000"), provisional_sums,
        )

        assert warnings.claim_warnings == []

    def test_unmatched_ps_item_warning(self):
        """PS claim item with no matched ProvisionalSum record gets a warning."""
        claim_items = [
            _make_claim_line_item(
                item_type="provisional_sum",
                provisional_sum_id=None,
                contract_value=Decimal("20000"),
                description="PS - Unknown item",
            ),
        ]

        warnings = validate_provisional_sum_discrepancies(
            claim_items, Decimal("150000"), [],
        )

        all_warnings = [w for ws in warnings.item_warnings.values() for w in ws]
        assert any("not found in project records" in w for w in all_warnings)

    def test_no_ps_total_skips_ceiling_check(self):
        """When project has no provisional_sum_total set, skip ceiling check."""
        ps_id = uuid.uuid4()
        claim_items = [
            _make_claim_line_item(
                item_type="provisional_sum",
                provisional_sum_id=ps_id,
                contract_value=Decimal("200000"),
                description="PS - Big item",
            ),
        ]
        provisional_sums = [
            _make_provisional_sum(id=ps_id, contract_sum=Decimal("100000")),
        ]

        warnings = validate_provisional_sum_discrepancies(
            claim_items, None, provisional_sums,
        )

        # Individual group warning fires, but no claim-level ceiling warning
        all_item_warnings = [w for ws in warnings.item_warnings.values() for w in ws]
        assert any("exceeds" in w for w in all_item_warnings)
        assert not any("project allocation" in w for w in warnings.claim_warnings)

    def test_non_ps_items_ignored(self):
        """Contract work and variation items are ignored by PS validation."""
        claim_items = [
            _make_claim_line_item(
                item_type="contract_work",
                contract_value=Decimal("500000"),
                description="Main works",
            ),
            _make_claim_line_item(
                item_type="variation",
                contract_value=Decimal("50000"),
                description="Extra works",
            ),
        ]

        warnings = validate_provisional_sum_discrepancies(
            claim_items, Decimal("150000"), [],
        )

        assert warnings.item_warnings == {}
        assert warnings.claim_warnings == []


class TestVariationStatusValidation:
    def test_unapproved_variation_gets_warning(self):
        """Claim item referencing an unapproved variation gets a warning."""
        var_id = uuid.uuid4()
        claim_items = [
            _make_claim_line_item(
                item_type="variation",
                variation_id=var_id,
                contract_value=Decimal("30000"),
                description="Extra drainage",
                ref_code="V1",
            ),
        ]
        variations = [_make_variation(id=var_id, status="unapproved")]

        warnings = validate_variation_status_warnings(claim_items, variations)

        assert any("unapproved" in w.lower() for w in warnings.item_warnings.get("V1", []))

    def test_approved_variation_no_warning(self):
        """Approved variation does not get a warning."""
        var_id = uuid.uuid4()
        claim_items = [
            _make_claim_line_item(
                item_type="variation",
                variation_id=var_id,
                contract_value=Decimal("30000"),
                description="Approved extra work",
                ref_code="V2",
            ),
        ]
        variations = [_make_variation(id=var_id, status="approved")]

        warnings = validate_variation_status_warnings(claim_items, variations)

        assert warnings.item_warnings == {}

    def test_in_review_variation_no_warning(self):
        """In-review variation does not get a warning (only unapproved triggers)."""
        var_id = uuid.uuid4()
        claim_items = [
            _make_claim_line_item(
                item_type="variation",
                variation_id=var_id,
                contract_value=Decimal("30000"),
                description="Under review work",
                ref_code="V3",
            ),
        ]
        variations = [_make_variation(id=var_id, status="in_review")]

        warnings = validate_variation_status_warnings(claim_items, variations)

        assert warnings.item_warnings == {}

    def test_non_variation_items_ignored(self):
        """Contract work and PS items are ignored."""
        claim_items = [
            _make_claim_line_item(item_type="contract_work", description="Main works"),
            _make_claim_line_item(item_type="provisional_sum", description="PS item"),
        ]

        warnings = validate_variation_status_warnings(claim_items, [])

        assert warnings.item_warnings == {}
