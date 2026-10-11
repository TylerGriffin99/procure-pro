import uuid
from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.constants.enums import AdjustmentType, AssessmentStatus
from app.schemas.assessment import AggregatedAssessmentResponse, AggregatedWBSGroupResponse, AssessmentLineItemResponse
from app.schemas.assessment_aggregate import AggregatedWBSGroup, AssessmentAggregate


def fake_assessment() -> SimpleNamespace:
    money = Decimal("10.00")
    return SimpleNamespace(
        id=uuid.uuid4(),
        claim_id=uuid.uuid4(),
        project_id=uuid.uuid4(),
        version=1,
        status="draft",
        previously_certified=money,
        contract_sum=money,
        approved_variation_orders=money,
        adjustment_to_provisional_sums=money,
        adjusted_contract_sum=money,
        value_claimed_to_date=money,
        adjustments=money,
        total_recommended=money,
        total_retention=money,
        total_payment_to_date=money,
        recommended_this_period=money,
        gst_amount=money,
        total_including_gst=money,
        finalised_at=datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC),
        line_items=[],
        variation_items=[],
        provisional_sum_items=[],
    )


def test_from_aggregate_maps_fields_and_formats_finalised_at():
    agg = AssessmentAggregate(assessment=fake_assessment(), wbs_groups=[], variation_groups=[], ps_groups=[])
    dto = AggregatedAssessmentResponse.from_aggregate(agg)
    assert dto.id == agg.assessment.id
    assert dto.status == "draft"
    assert dto.finalised_at == "2026-01-02T03:04:05+00:00"
    assert dto.wbs_groups == [] and dto.variation_groups == [] and dto.ps_groups == []


def test_from_aggregate_null_finalised_at():
    a = fake_assessment()
    a.finalised_at = None
    dto = AggregatedAssessmentResponse.from_aggregate(
        AssessmentAggregate(assessment=a, wbs_groups=[], variation_groups=[], ps_groups=[])
    )
    assert dto.finalised_at is None


def fake_line_item(**overrides) -> SimpleNamespace:
    money = Decimal("5.00")
    fields = {
        "id": uuid.uuid4(),
        "claim_line_item_id": uuid.uuid4(),
        "wbs_code_id": uuid.uuid4(),
        "description": "Demolition",
        "contractor_claim_to_date": money,
        "total_recommended": money,
        "percentage": Decimal("50.00"),
        "variance_to_claim": Decimal(0),
        "previously_paid": Decimal(0),
        "recommended_this_period": money,
        "status": "approved",
        "comments": None,
        "is_closed_out": False,
        "sort_order": 0,
        "adjustment_type": "interim_adjustment",
        "source_assessment_id": None,
    }
    return SimpleNamespace(**(fields | overrides))


def populated_aggregate() -> AssessmentAggregate:
    row = fake_line_item()
    a = fake_assessment()
    a.line_items = [row]
    money = Decimal("5.00")
    group = AggregatedWBSGroup(
        wbs_code_id=row.wbs_code_id,
        description="Demolition",
        contract_sum=money,
        previously_paid=Decimal(0),
        recommended_this_period=money,
        total_recommended=money,
        contractor_claim_to_date=money,
        variance_to_claim=Decimal(0),
        percentage=Decimal("50.00"),
        history_row=None,
        child_rows=[row],
    )
    return AssessmentAggregate(assessment=a, wbs_groups=[group], variation_groups=[], ps_groups=[])


def field_by_field(agg: AssessmentAggregate) -> AggregatedAssessmentResponse:
    a = agg.assessment
    return AggregatedAssessmentResponse(
        id=a.id,
        claim_id=a.claim_id,
        project_id=a.project_id,
        version=a.version,
        status=a.status,
        previously_certified=a.previously_certified,
        contract_sum=a.contract_sum,
        approved_variation_orders=a.approved_variation_orders,
        adjustment_to_provisional_sums=a.adjustment_to_provisional_sums,
        adjusted_contract_sum=a.adjusted_contract_sum,
        value_claimed_to_date=a.value_claimed_to_date,
        adjustments=a.adjustments,
        total_recommended=a.total_recommended,
        total_retention=a.total_retention,
        total_payment_to_date=a.total_payment_to_date,
        recommended_this_period=a.recommended_this_period,
        gst_amount=a.gst_amount,
        total_including_gst=a.total_including_gst,
        finalised_at=a.finalised_at.isoformat() if a.finalised_at else None,
        wbs_groups=agg.wbs_groups,
        variation_groups=agg.variation_groups,
        ps_groups=agg.ps_groups,
        line_items=a.line_items,
        variation_items=a.variation_items,
        provisional_sum_items=a.provisional_sum_items,
    )


def test_from_aggregate_wire_equals_the_field_by_field_mapping():
    agg = populated_aggregate()
    dto = AggregatedAssessmentResponse.from_aggregate(agg)
    assert dto.model_dump(mode="json") == field_by_field(agg).model_dump(mode="json")
    assert isinstance(dto.wbs_groups[0], AggregatedWBSGroupResponse)
    assert isinstance(dto.wbs_groups[0].child_rows[0], AssessmentLineItemResponse)


def test_status_and_adjustment_type_are_enums_with_unchanged_wire_values():
    dto = AggregatedAssessmentResponse.from_aggregate(populated_aggregate())
    assert dto.status is AssessmentStatus.draft
    assert dto.line_items[0].adjustment_type is AdjustmentType.interim_adjustment
    wire = dto.model_dump(mode="json")
    assert wire["status"] == "draft"
    assert wire["line_items"][0]["adjustment_type"] == "interim_adjustment"


def test_unknown_adjustment_type_is_rejected():
    with pytest.raises(ValidationError, match="adjustment_type"):
        AssessmentLineItemResponse.model_validate(fake_line_item(adjustment_type="bogus"), from_attributes=True)
