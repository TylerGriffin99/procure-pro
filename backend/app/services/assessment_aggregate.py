import uuid
from collections.abc import Sequence
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.constants.enums import LineItemStatus, VariationStatus
from app.constants.values import CENTS
from app.models.assessment import Assessment
from app.models.assessment_line_item import AssessmentLineItem
from app.models.assessment_provisional_sum import AssessmentProvisionalSum
from app.models.assessment_variation import AssessmentVariation
from app.models.project import Project
from app.repos import provisional_sum_repo, variation_repo, wbs_code_repo
from app.schemas.assessment_aggregate import AggregatedAssessment, AssessmentAggregate, AssessmentSummary
from app.schemas.retention import RetentionTier
from app.utils.assessment_aggregator import (
    aggregate_line_items,
    aggregate_provisional_sums,
    aggregate_variations,
    compute_assessment_totals,
)
from app.utils.assessment_engine import assessment_summary

AssessmentRow = AssessmentLineItem | AssessmentVariation | AssessmentProvisionalSum
VpsItemRow = AssessmentVariation | AssessmentProvisionalSum


async def aggregate_assessment(db: AsyncSession, project_id: uuid.UUID, assessment: Assessment) -> AggregatedAssessment:
    all_wbs = await wbs_code_repo.get_by_project(db, project_id)
    all_variations = await variation_repo.get_by_project(db, project_id)
    all_ps = await provisional_sum_repo.get_by_project(db, project_id)
    aggregate = AssessmentAggregate(
        assessment=assessment,
        wbs_groups=aggregate_line_items(assessment.line_items, all_wbs),
        variation_groups=aggregate_variations(assessment.variation_items, all_variations),
        ps_groups=aggregate_provisional_sums(assessment.provisional_sum_items, all_ps),
    )
    return AggregatedAssessment(aggregate=aggregate, variations=list(all_variations), provisional_sums=list(all_ps))


def summarise_assessment(aggregate: AssessmentAggregate, project: Project) -> AssessmentSummary:
    return assessment_summary(
        compute_assessment_totals(aggregate.wbs_groups, aggregate.variation_groups, aggregate.ps_groups),
        contract_sum=project.contract_sum,
        retention_tiers=[RetentionTier.model_validate(t, from_attributes=True) for t in project.retention_tiers],
        previously_certified=aggregate.assessment.previously_certified or Decimal("0"),
        gst_rate=project.gst_rate,
    )


def rollup_status(rows: Sequence[VpsItemRow]) -> VariationStatus:
    if all(r.status == LineItemStatus.approved for r in rows):
        return VariationStatus.approved
    if any(r.status == LineItemStatus.interim for r in rows):
        return VariationStatus.in_review
    return VariationStatus.unapproved


def recompute_item(row: AssessmentRow, *, denominator: Decimal | None) -> None:
    row.variance_to_claim = row.total_recommended - row.contractor_claim_to_date
    if denominator and denominator > 0:
        row.percentage = (row.total_recommended / denominator * 100).quantize(CENTS)
    row.recommended_this_period = row.total_recommended - row.previously_paid
