import uuid
from collections.abc import Sequence
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.constants.enums import LineItemStatus, VariationStatus
from app.constants.values import CENTS, EXPORT_STRIPPED_COMMENT_PREFIXES
from app.models.assessment import Assessment
from app.models.assessment_line_item import AssessmentLineItem
from app.models.assessment_provisional_sum import AssessmentProvisionalSum
from app.models.assessment_variation import AssessmentVariation
from app.repos import provisional_sum_repo, variation_repo, wbs_code_repo
from app.schemas.assessment_aggregate import AggregatedAssessment, AssessmentAggregate
from app.utils.assessment_aggregator import aggregate_line_items, aggregate_provisional_sums, aggregate_variations

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


def rollup_status(rows: Sequence[VpsItemRow]) -> VariationStatus:
    if all(r.status == LineItemStatus.approved for r in rows):
        return VariationStatus.approved
    if any(r.status == LineItemStatus.interim for r in rows):
        return VariationStatus.in_review
    return VariationStatus.unapproved


def export_display(history_row: VpsItemRow | None, child_rows: Sequence[VpsItemRow]) -> tuple[str, str]:
    all_rows = ([history_row] if history_row else []) + list(child_rows)
    comments = "; ".join(r.comments for r in all_rows if r.comments)
    for prefix in EXPORT_STRIPPED_COMMENT_PREFIXES:
        if comments.startswith(prefix):
            comments = comments[len(prefix) :]
            break
    if any(r.is_closed_out for r in all_rows):
        status = "Closed Out"
    elif child_rows:
        status = child_rows[0].status.value.capitalize()
    elif history_row:
        status = history_row.status.value.capitalize()
    else:
        status = ""
    return comments.strip(), status


def recompute_item(row: AssessmentRow, *, denominator: Decimal | None) -> None:
    row.variance_to_claim = row.total_recommended - row.contractor_claim_to_date
    if denominator and denominator > 0:
        row.percentage = (row.total_recommended / denominator * 100).quantize(CENTS)
    row.recommended_this_period = row.total_recommended - row.previously_paid
