import uuid
from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace

from app.schemas.assessment import AggregatedAssessmentResponse
from app.schemas.assessment_aggregate import AssessmentAggregate


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
    agg = AssessmentAggregate(
        assessment=fake_assessment(), wbs_groups=[], variation_groups=[], ps_groups=[]
    )
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
