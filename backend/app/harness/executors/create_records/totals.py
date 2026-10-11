from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.assessment import Assessment
from app.models.project import Project
from app.repos import assessment_repo
from app.schemas.retention import RetentionTier
from app.services.assessment_aggregate import aggregate_assessment
from app.utils.assessment_aggregator import compute_assessment_totals
from app.utils.assessment_engine import assessment_summary

ZERO = Decimal("0")


async def apply_totals(db: AsyncSession, *, assessment: Assessment, project: Project) -> Assessment:
    aggregate = (await aggregate_assessment(db, project.id, assessment)).aggregate
    summary = assessment_summary(
        compute_assessment_totals(aggregate.wbs_groups, aggregate.variation_groups, aggregate.ps_groups),
        contract_sum=project.contract_sum,
        retention_tiers=[
            RetentionTier(percentage=t.percentage, up_to_amount=t.up_to_amount) for t in project.retention_tiers
        ],
        previously_certified=assessment.previously_certified or ZERO,
        gst_rate=project.gst_rate,
    )
    return await assessment_repo.update(db, assessment, **summary.model_dump())
