from sqlalchemy.ext.asyncio import AsyncSession

from app.models.assessment import Assessment
from app.models.project import Project
from app.repos import assessment_repo
from app.services.assessment_aggregate import aggregate_assessment, summarise_assessment


async def apply_totals(db: AsyncSession, *, assessment: Assessment, project: Project) -> Assessment:
    aggregate = (await aggregate_assessment(db, project.id, assessment)).aggregate
    return await assessment_repo.update(db, assessment, **summarise_assessment(aggregate, project).model_dump())
