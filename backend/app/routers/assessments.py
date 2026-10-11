import uuid

from fastapi import APIRouter
from fastapi.responses import Response

from app.constants import ExportFormat
from app.dependencies import CurrentUser, DbSession
from app.schemas.assessment import (
    AggregatedAssessmentResponse,
    AssessmentCreate,
    AssessmentLineItemResponse,
    AssessmentLineItemUpdate,
    AssessmentProvisionalSumResponse,
    AssessmentProvisionalSumUpdate,
    AssessmentResponse,
    AssessmentVariationResponse,
    AssessmentVariationUpdate,
    CloseOutRequest,
    InterimAdjustRequest,
    PriorInterimsResponse,
    ReclassifyRequest,
)
from app.services import assessment_service

router = APIRouter(prefix="/projects/{project_id}/assessments", tags=["assessments"])


@router.post("", response_model=AssessmentResponse, status_code=201)
async def create_assessment(project_id: uuid.UUID, body: AssessmentCreate, db: DbSession, user: CurrentUser):
    return await assessment_service.create_assessment(db, project_id, body, user)


@router.get("/by-claim/{claim_id}", response_model=AggregatedAssessmentResponse)
async def get_assessment_by_claim(project_id: uuid.UUID, claim_id: uuid.UUID, db: DbSession, user: CurrentUser):
    result = await assessment_service.get_aggregated_by_claim(db, project_id, claim_id)
    return AggregatedAssessmentResponse.from_aggregate(result)


@router.patch("/{assessment_id}/line-items/{line_item_id}", response_model=AssessmentLineItemResponse)
async def update_line_item(
    project_id: uuid.UUID,
    assessment_id: uuid.UUID,
    line_item_id: uuid.UUID,
    body: AssessmentLineItemUpdate,
    db: DbSession,
    user: CurrentUser,
):
    return await assessment_service.update_line_item(db, assessment_id, line_item_id, body, user)


@router.patch("/{assessment_id}/variation-items/{item_id}", response_model=AssessmentVariationResponse)
async def update_variation_item(
    project_id: uuid.UUID,
    assessment_id: uuid.UUID,
    item_id: uuid.UUID,
    body: AssessmentVariationUpdate,
    db: DbSession,
    user: CurrentUser,
):
    return await assessment_service.update_variation_item(db, assessment_id, item_id, body, user)


@router.patch("/{assessment_id}/provisional-sum-items/{item_id}", response_model=AssessmentProvisionalSumResponse)
async def update_provisional_sum_item(
    project_id: uuid.UUID,
    assessment_id: uuid.UUID,
    item_id: uuid.UUID,
    body: AssessmentProvisionalSumUpdate,
    db: DbSession,
    user: CurrentUser,
):
    return await assessment_service.update_provisional_sum_item(db, assessment_id, item_id, body, user)


@router.post("/{assessment_id}/reclassify", response_model=AggregatedAssessmentResponse)
async def reclassify_item(
    project_id: uuid.UUID, assessment_id: uuid.UUID, body: ReclassifyRequest, db: DbSession, user: CurrentUser
):
    result = await assessment_service.reclassify_item(db, project_id, assessment_id, body, user)
    return AggregatedAssessmentResponse.from_aggregate(result)


@router.post("/{assessment_id}/finalise", response_model=AssessmentResponse)
async def finalise_assessment(project_id: uuid.UUID, assessment_id: uuid.UUID, db: DbSession, user: CurrentUser):
    return await assessment_service.finalise_assessment(db, project_id, assessment_id, user)


@router.post("/{assessment_id}/revert-to-draft", response_model=AssessmentResponse)
async def revert_to_draft(project_id: uuid.UUID, assessment_id: uuid.UUID, db: DbSession, user: CurrentUser):
    return await assessment_service.revert_to_draft(db, project_id, assessment_id, user)


@router.get("/{assessment_id}", response_model=AggregatedAssessmentResponse)
async def get_assessment(project_id: uuid.UUID, assessment_id: uuid.UUID, db: DbSession, user: CurrentUser):
    result = await assessment_service.get_aggregated_assessment(db, project_id, assessment_id)
    return AggregatedAssessmentResponse.from_aggregate(result)


@router.get("/{assessment_id}/export")
async def download_pr_export(
    project_id: uuid.UUID,
    assessment_id: uuid.UUID,
    db: DbSession,
    user: CurrentUser,
    format: ExportFormat = ExportFormat.pdf,
):
    export = await assessment_service.generate_assessment_export(db, project_id, assessment_id, format)
    return Response(content=export.content, media_type=export.media_type)


@router.get("/{assessment_id}/prior-interims", response_model=PriorInterimsResponse)
async def get_prior_interims(project_id: uuid.UUID, assessment_id: uuid.UUID, db: DbSession, user: CurrentUser):
    return await assessment_service.get_prior_interims(db, project_id, assessment_id)


@router.post("/{assessment_id}/interim-adjust", response_model=AggregatedAssessmentResponse)
async def create_interim_adjustment(
    project_id: uuid.UUID, assessment_id: uuid.UUID, body: InterimAdjustRequest, db: DbSession, user: CurrentUser
):
    result = await assessment_service.create_interim_adjustment(db, project_id, assessment_id, body, user)
    return AggregatedAssessmentResponse.from_aggregate(result)


@router.post("/{assessment_id}/close-out", response_model=AggregatedAssessmentResponse)
async def close_out_item(
    project_id: uuid.UUID, assessment_id: uuid.UUID, body: CloseOutRequest, db: DbSession, user: CurrentUser
):
    result = await assessment_service.close_out_item(db, project_id, assessment_id, body, user)
    return AggregatedAssessmentResponse.from_aggregate(result)
