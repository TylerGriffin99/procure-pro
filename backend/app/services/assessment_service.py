import uuid
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Final, assert_never

from sqlalchemy.ext.asyncio import AsyncSession

from app.constants.enums import (
    AdjustmentType,
    AssessmentItemKind,
    AssessmentStatus,
    ExportFormat,
    LineItemStatus,
    VariationStatus,
)
from app.constants.values import (
    COMMENT_PREFIX_CLOSED_OUT,
    COMMENT_PREFIX_INTERIM,
    COMMENT_SEPARATOR,
    PDF_MEDIA_TYPE,
    XLSX_MEDIA_TYPE,
)
from app.exceptions import BadRequestError, ConflictError, NotFoundError, reloaded, require
from app.models.assessment import Assessment
from app.models.assessment_line_item import AssessmentLineItem
from app.models.assessment_provisional_sum import AssessmentProvisionalSum
from app.models.assessment_variation import AssessmentVariation
from app.models.user import User
from app.repos import (
    assessment_line_item_repo,
    assessment_provisional_sum_repo,
    assessment_repo,
    assessment_variation_repo,
    claim_line_item_repo,
    claim_repo,
    project_repo,
    provisional_sum_repo,
    variation_repo,
)
from app.schemas.assessment import (
    AssessmentCreate,
    AssessmentLineItemUpdate,
    AssessmentProvisionalSumUpdate,
    AssessmentVariationUpdate,
    CloseOutRequest,
    InterimAdjustRequest,
    PriorInterimResponse,
    PriorInterimsResponse,
    ReclassifyRequest,
)
from app.schemas.assessment_aggregate import AggregatedAssessment, AssessmentAggregate, ReclassifyCarry
from app.schemas.payment_recommendation import ExportFile, PaymentRecommendation, RetentionDetail
from app.schemas.retention import RetentionTier
from app.services.assessment_aggregate import aggregate_assessment, recompute_item, rollup_status, summarise_assessment
from app.utils.assessment_engine import calculate_retention_per_tier
from app.utils.excel_generator import generate_payment_recommendation_excel
from app.utils.pdf_generator import generate_payment_recommendation_pdf

InterimItem = AssessmentLineItem | AssessmentVariation | AssessmentProvisionalSum

ROW_COLLECTION: Final = {
    AssessmentItemKind.line_item: "line_items",
    AssessmentItemKind.variation: "variation_items",
    AssessmentItemKind.provisional_sum: "provisional_sum_items",
}
PARENT_KEY: Final = {
    AssessmentItemKind.line_item: "wbs_code_id",
    AssessmentItemKind.variation: "variation_id",
    AssessmentItemKind.provisional_sum: "provisional_sum_id",
}
ROW_CREATE: Final = {
    AssessmentItemKind.line_item: assessment_line_item_repo.create,
    AssessmentItemKind.variation: assessment_variation_repo.create,
    AssessmentItemKind.provisional_sum: assessment_provisional_sum_repo.create,
}


def rows_of_kind(assessment: Assessment, kind: AssessmentItemKind) -> list[InterimItem]:
    return getattr(assessment, ROW_COLLECTION[kind])


def group_rows(assessment: Assessment, kind: AssessmentItemKind, parent_id: uuid.UUID) -> list[InterimItem]:
    return [row for row in rows_of_kind(assessment, kind) if getattr(row, PARENT_KEY[kind]) == parent_id]


async def draft_assessment(
    db: AsyncSession, project_id: uuid.UUID, assessment_id: uuid.UUID, action: str
) -> Assessment:
    assessment = require(await assessment_repo.get_by_id(db, assessment_id, project_id=project_id), "Assessment")
    if assessment.status != AssessmentStatus.draft:
        raise BadRequestError(f"Assessment must be in draft to {action}")
    return assessment


async def create_assessment(db: AsyncSession, project_id: uuid.UUID, data: AssessmentCreate, user: User) -> Assessment:
    # Load claim with line items
    claim = require(await claim_repo.get_by_id(db, data.claim_id), "Claim")

    # Get previously certified amount from latest finalised assessment
    prev_assessment = await assessment_repo.get_latest_finalised(db, project_id)
    previously_certified = prev_assessment.total_payment_to_date if prev_assessment else Decimal("0")

    version = await assessment_repo.next_version_number(db, data.claim_id)

    assessment = Assessment(
        claim_id=data.claim_id,
        project_id=project_id,
        version=version,
        previously_certified=previously_certified,
        created_by=user.id,
    )

    for i, cli in enumerate(sorted(claim.line_items, key=lambda x: x.sort_order)):
        assessment.line_items.append(
            AssessmentLineItem(
                claim_line_item_id=cli.id,
                description=cli.description,
                contractor_claim_to_date=cli.ptd,
                total_recommended=Decimal("0"),
                percentage=Decimal("0"),
                variance_to_claim=Decimal("0") - cli.ptd,
                previously_paid=Decimal("0"),
                recommended_this_period=Decimal("0"),
                status=LineItemStatus.approved if cli.ptd == Decimal("0") else LineItemStatus.unapproved,
                sort_order=i,
                created_by=user.id,
            )
        )

    await assessment_repo.add(db, assessment)
    await db.commit()
    await db.refresh(assessment, ["line_items"])
    return assessment


async def get_latest_by_claim(db: AsyncSession, project_id: uuid.UUID, claim_id: uuid.UUID) -> Assessment:
    return require(await assessment_repo.get_latest_by_claim(db, claim_id, project_id=project_id), "Assessment")


async def get_aggregated_by_claim(db: AsyncSession, project_id: uuid.UUID, claim_id: uuid.UUID) -> AssessmentAggregate:
    """The latest assessment for ``claim_id``, aggregated."""
    assessment = await get_latest_by_claim(db, project_id, claim_id)
    return await get_aggregated_assessment(db, project_id, assessment.id)


async def update_line_item(
    db: AsyncSession, assessment_id: uuid.UUID, line_item_id: uuid.UUID, data: AssessmentLineItemUpdate, user: User
) -> AssessmentLineItem:
    item = require(await assessment_line_item_repo.get_by_id(db, line_item_id, assessment_id), "Line item")

    if data.total_recommended is not None:
        item.total_recommended = data.total_recommended
        recompute_item(item, denominator=item.contract_sum)

    if data.status is not None:
        item.status = data.status
    if data.comments is not None:
        item.comments = data.comments
    if data.wbs_code_id is not None:
        item.wbs_code_id = data.wbs_code_id

    item.updated_by = user.id

    await db.commit()
    await db.refresh(item)
    return item


async def get_aggregated_assessment(
    db: AsyncSession, project_id: uuid.UUID, assessment_id: uuid.UUID
) -> AssessmentAggregate:
    """Fetch assessment and return it with pre-aggregated groups."""
    assessment = require(await assessment_repo.get_by_id(db, assessment_id, project_id=project_id), "Assessment")
    return (await aggregate_assessment(db, project_id, assessment)).aggregate


async def get_prior_interims(
    db: AsyncSession, project_id: uuid.UUID, assessment_id: uuid.UUID
) -> PriorInterimsResponse:
    """Find items from the previous finalised assessment that have status='interim'."""
    prev_assessment = await assessment_repo.get_latest_finalised(db, project_id)
    if not prev_assessment or prev_assessment.id == assessment_id:
        return PriorInterimsResponse()

    wbs_groups: dict[uuid.UUID, list[AssessmentLineItem]] = {}
    for item in prev_assessment.line_items:
        wbs_id = item.wbs_code_id
        if wbs_id:
            wbs_groups.setdefault(wbs_id, []).append(item)

    var_groups: dict[uuid.UUID, list[AssessmentVariation]] = {}
    for item in prev_assessment.variation_items:
        var_groups.setdefault(item.variation_id, []).append(item)

    ps_groups: dict[uuid.UUID, list[AssessmentProvisionalSum]] = {}
    for item in prev_assessment.provisional_sum_items:
        ps_groups.setdefault(item.provisional_sum_id, []).append(item)

    return PriorInterimsResponse(
        wbs_interims=interim_groups(wbs_groups),
        variation_interims=interim_groups(var_groups),
        ps_interims=interim_groups(ps_groups),
    )


def interim_groups(groups: Mapping[uuid.UUID, Sequence[InterimItem]]) -> list[PriorInterimResponse]:
    """One entry per parent whose group holds at least one interim-status item."""
    return [
        PriorInterimResponse.from_group(parent_id, items)
        for parent_id, items in groups.items()
        if any(item.status == LineItemStatus.interim for item in items)
    ]


async def create_interim_adjustment(
    db: AsyncSession, project_id: uuid.UUID, assessment_id: uuid.UUID, data: InterimAdjustRequest, user: User
) -> AssessmentAggregate:
    """Create an interim adjustment child row under the specified parent."""
    assessment = await draft_assessment(db, project_id, assessment_id, "add adjustments")
    prev_assessment = await assessment_repo.get_latest_finalised(db, project_id)
    source_id = prev_assessment.id if prev_assessment and prev_assessment.id != assessment_id else None

    history = next(
        (
            row
            for row in group_rows(assessment, data.item_type, data.parent_id)
            if row.claim_line_item_id is None and not row.adjustment_type
        ),
        None,
    )
    difference = data.agreed_total - (history.previously_paid if history else Decimal("0"))
    await ROW_CREATE[data.item_type](
        db,
        **interim_row_fields(assessment, data, history),
        assessment_id=assessment_id,
        claim_line_item_id=None,
        contractor_claim_to_date=Decimal("0"),
        total_recommended=difference,
        percentage=Decimal("0"),
        variance_to_claim=difference,
        previously_paid=Decimal("0"),
        recommended_this_period=difference,
        status=LineItemStatus.interim,
        comments=f"{COMMENT_PREFIX_INTERIM}{COMMENT_SEPARATOR}{data.comments}"
        if data.comments
        else COMMENT_PREFIX_INTERIM,
        adjustment_type=AdjustmentType.interim_adjustment,
        source_assessment_id=source_id,
        created_by=user.id,
    )
    await db.commit()
    return await get_aggregated_assessment(db, project_id, assessment_id)


def interim_row_fields(
    assessment: Assessment, data: InterimAdjustRequest, history: InterimItem | None
) -> dict[str, Any]:
    match data.item_type:
        case AssessmentItemKind.line_item:
            return {
                "wbs_code_id": data.parent_id,
                "description": history.description if isinstance(history, AssessmentLineItem) else "Interim adjustment",
                "sort_order": max((li.sort_order for li in assessment.line_items), default=-1) + 1,
            }
        case AssessmentItemKind.variation:
            return {"variation_id": data.parent_id}
        case AssessmentItemKind.provisional_sum:
            return {"provisional_sum_id": data.parent_id}
        case _:
            assert_never(data.item_type)


def closed_out_comment(row: InterimItem) -> str | None:
    """History and adjustment rows get a Closed Out prefix (idempotent); claim-linked rows keep their comment."""
    comments = row.comments
    if row.claim_line_item_id is not None:
        return comments
    if not comments:
        return COMMENT_PREFIX_CLOSED_OUT
    if comments.startswith(COMMENT_PREFIX_CLOSED_OUT):
        return comments
    if comments.startswith(COMMENT_PREFIX_INTERIM):
        return COMMENT_PREFIX_CLOSED_OUT + comments[len(COMMENT_PREFIX_INTERIM) :]
    return f"{COMMENT_PREFIX_CLOSED_OUT}{COMMENT_SEPARATOR}{comments}"


async def close_out_item(
    db: AsyncSession, project_id: uuid.UUID, assessment_id: uuid.UUID, data: CloseOutRequest, user: User
) -> AssessmentAggregate:
    """Close out an interim item — sets all rows for this parent to 'approved' status."""
    assessment = await draft_assessment(db, project_id, assessment_id, "close out items")
    for row in group_rows(assessment, data.item_type, data.parent_id):
        row.status = LineItemStatus.approved
        row.is_closed_out = True
        row.comments = closed_out_comment(row)
        row.updated_by = user.id
    await db.commit()
    return await get_aggregated_assessment(db, project_id, assessment_id)


async def generate_assessment_export(
    db: AsyncSession, project_id: uuid.UUID, assessment_id: uuid.UUID, format: ExportFormat = ExportFormat.pdf
) -> ExportFile:
    assessment = require(await assessment_repo.get_by_id(db, assessment_id, project_id=project_id), "Assessment")
    project = require(await project_repo.get_by_id_with_retention(db, project_id), "Project")
    claim = await claim_repo.get_by_id(db, assessment.claim_id)

    aggregate = (await aggregate_assessment(db, project_id, assessment)).aggregate
    summary = summarise_assessment(aggregate, project)
    tiers = [RetentionTier.model_validate(t, from_attributes=True) for t in project.retention_tiers]
    recommendation = PaymentRecommendation.from_aggregate(
        aggregate,
        project=project,
        claim=claim,
        summary=summary,
        retention_details=[
            RetentionDetail(**detail) for detail in calculate_retention_per_tier(summary.total_recommended, tiers)
        ],
    )
    return render_export(recommendation, format)


def render_export(recommendation: PaymentRecommendation, format: ExportFormat) -> ExportFile:
    filename = f"payment-recommendation-{recommendation.pr_number}"
    if format == ExportFormat.excel:
        return ExportFile(
            content=generate_payment_recommendation_excel(recommendation),
            media_type=XLSX_MEDIA_TYPE,
            filename=f"{filename}.xlsx",
        )
    return ExportFile(
        content=generate_payment_recommendation_pdf(recommendation),
        media_type=PDF_MEDIA_TYPE,
        filename=f"{filename}.pdf",
    )


async def update_variation_item(
    db: AsyncSession, assessment_id: uuid.UUID, item_id: uuid.UUID, data: AssessmentVariationUpdate, user: User
) -> AssessmentVariation:
    item = require(await assessment_variation_repo.get_by_id(db, item_id, assessment_id), "Variation item")

    if data.total_recommended is not None:
        item.total_recommended = data.total_recommended
        recompute_item(item, denominator=item.variation.contractor_submission if item.variation else None)

    if data.status is not None:
        item.status = data.status
    if data.comments is not None:
        item.comments = data.comments

    item.updated_by = user.id

    await db.commit()
    return reloaded(await assessment_variation_repo.get_by_id(db, item.id, assessment_id), "Variation item")


async def update_provisional_sum_item(
    db: AsyncSession, assessment_id: uuid.UUID, item_id: uuid.UUID, data: AssessmentProvisionalSumUpdate, user: User
) -> AssessmentProvisionalSum:
    item = require(await assessment_provisional_sum_repo.get_by_id(db, item_id, assessment_id), "Provisional sum item")

    if data.total_recommended is not None:
        item.total_recommended = data.total_recommended
        recompute_item(item, denominator=item.provisional_sum.contract_sum if item.provisional_sum else None)

    if data.status is not None:
        item.status = data.status
    if data.comments is not None:
        item.comments = data.comments

    item.updated_by = user.id

    await db.commit()
    return reloaded(await assessment_provisional_sum_repo.get_by_id(db, item.id, assessment_id), "Provisional sum item")


def find_source_row(assessment: Assessment, data: ReclassifyRequest) -> tuple[InterimItem, uuid.UUID]:
    source = require(
        next((r for r in rows_of_kind(assessment, data.source_type) if r.id == data.source_item_id), None),
        "Source item",
    )
    if source.claim_line_item_id is None:
        raise BadRequestError("Cannot reclassify a history row without a linked claim line item")
    return source, source.claim_line_item_id


def require_target_wbs(data: ReclassifyRequest) -> uuid.UUID:
    if not data.target_wbs_code_id:
        raise BadRequestError("target_wbs_code_id is required when target_type is 'line-item'")
    return data.target_wbs_code_id


async def delete_source_row(db: AsyncSession, row: InterimItem) -> None:
    match row:
        case AssessmentLineItem():
            await assessment_line_item_repo.delete(db, row)
        case AssessmentVariation():
            await assessment_variation_repo.delete(db, row)
        case AssessmentProvisionalSum():
            await assessment_provisional_sum_repo.delete(db, row)
        case _:
            assert_never(row)


async def ensure_target_master(
    db: AsyncSession, data: ReclassifyRequest, carry: ReclassifyCarry, project_id: uuid.UUID, user: User
) -> uuid.UUID:
    description = data.new_record.description if data.new_record else carry.description
    match data.target_type:
        case AssessmentItemKind.variation:
            if data.target_id:
                existing = await variation_repo.get_by_project(db, project_id)
                if not any(v.id == data.target_id for v in existing):
                    raise NotFoundError("Target variation not found")
                return data.target_id
            ci_number = await variation_repo.get_max_ci_number(db, project_id) + 1
            variation = await variation_repo.create(
                db,
                project_id=project_id,
                ci_number=ci_number,
                contractor_ref=f"CI-{ci_number:03d}",
                description=description,
                contractor_submission=carry.contract_value,
                status=VariationStatus.unapproved,
                wbs_code_id=data.target_wbs_code_id,
                created_by=user.id,
            )
            return variation.id
        case AssessmentItemKind.provisional_sum:
            if data.target_id:
                existing_ps = await provisional_sum_repo.get_by_project(db, project_id)
                if not any(p.id == data.target_id for p in existing_ps):
                    raise NotFoundError("Target provisional sum not found")
                return data.target_id
            ps_number = await provisional_sum_repo.get_max_ps_number(db, project_id) + 1
            ps = await provisional_sum_repo.create(
                db,
                project_id=project_id,
                ps_number=ps_number,
                description=description,
                contract_sum=carry.contract_value,
                status=VariationStatus.unapproved,
                wbs_code_id=data.target_wbs_code_id,
                created_by=user.id,
            )
            return ps.id
        case AssessmentItemKind.line_item:
            raise BadRequestError("A line item has no variation or provisional sum master")
        case _:
            assert_never(data.target_type)


async def target_row_fields(
    db: AsyncSession,
    assessment: Assessment,
    data: ReclassifyRequest,
    carry: ReclassifyCarry,
    project_id: uuid.UUID,
    user: User,
) -> dict[str, Any]:
    match data.target_type:
        case AssessmentItemKind.line_item:
            wbs_code_id = require_target_wbs(data)
            # db.expire invalidated the cached collection and a lazy reload fails under async, so refresh explicitly.
            await db.refresh(assessment, ["line_items"])
            max_sort = max((li.sort_order for li in assessment.line_items), default=-1)
            return {"wbs_code_id": wbs_code_id, "description": carry.description, "sort_order": max_sort + 1}
        case AssessmentItemKind.variation:
            return {"variation_id": await ensure_target_master(db, data, carry, project_id, user)}
        case AssessmentItemKind.provisional_sum:
            return {"provisional_sum_id": await ensure_target_master(db, data, carry, project_id, user)}
        case _:
            assert_never(data.target_type)


async def create_target_row(
    db: AsyncSession,
    assessment: Assessment,
    data: ReclassifyRequest,
    carry: ReclassifyCarry,
    project_id: uuid.UUID,
    user: User,
) -> None:
    rtp = carry.recommended_this_period
    await ROW_CREATE[data.target_type](
        db,
        **await target_row_fields(db, assessment, data, carry, project_id, user),
        assessment_id=carry.assessment_id,
        claim_line_item_id=carry.claim_line_item_id,
        contractor_claim_to_date=carry.contractor_claim_to_date,
        total_recommended=rtp,
        percentage=Decimal("0"),
        variance_to_claim=rtp - carry.contractor_claim_to_date,
        previously_paid=Decimal("0"),
        recommended_this_period=rtp,
        status=LineItemStatus.unapproved,
        created_by=user.id,
    )


async def reclassify_item(
    db: AsyncSession, project_id: uuid.UUID, assessment_id: uuid.UUID, data: ReclassifyRequest, user: User
) -> AssessmentAggregate:
    assessment = require(await assessment_repo.get_by_id(db, assessment_id, project_id=project_id), "Assessment")
    source, claim_line_item_id = find_source_row(assessment, data)
    cli = await claim_line_item_repo.get_by_id(db, claim_line_item_id)

    if isinstance(source, AssessmentLineItem) and data.target_type == AssessmentItemKind.line_item:
        await assessment_line_item_repo.update(db, source, wbs_code_id=require_target_wbs(data))
        await db.commit()
        return await get_aggregated_assessment(db, project_id, assessment_id)

    carry = ReclassifyCarry(
        assessment_id=assessment_id,
        claim_line_item_id=claim_line_item_id,
        contractor_claim_to_date=source.contractor_claim_to_date,
        recommended_this_period=source.recommended_this_period,
        description=cli.description if cli else "",
        contract_value=cli.contract_value if cli else Decimal("0"),
    )
    await delete_source_row(db, source)
    # Expire so the collections reload fresh instead of returning the deleted row.
    db.expire(assessment)
    await create_target_row(db, assessment, data, carry, project_id, user)
    await db.commit()
    db.expire(assessment)
    return await get_aggregated_assessment(db, project_id, assessment_id)


def sync_masters(aggregated: AggregatedAssessment, user: User) -> None:
    var_map = {v.id: v for v in aggregated.variations}
    for g in aggregated.aggregate.variation_groups:
        if master := var_map.get(g.variation_id):
            master.approved_amount = g.total_recommended
            master.contractor_submission = g.contractor_claim_to_date
            master.status = rollup_status(([g.history_row] if g.history_row else []) + g.child_rows)
            master.updated_by = user.id
    ps_map = {p.id: p for p in aggregated.provisional_sums}
    for g in aggregated.aggregate.ps_groups:
        if master := ps_map.get(g.provisional_sum_id):
            master.approved_amount = g.total_recommended
            master.status = rollup_status(([g.history_row] if g.history_row else []) + g.child_rows)
            master.updated_by = user.id


async def finalise_assessment(
    db: AsyncSession, project_id: uuid.UUID, assessment_id: uuid.UUID, user: User
) -> Assessment:
    assessment = require(await assessment_repo.get_by_id(db, assessment_id, project_id=project_id), "Assessment")
    aggregated = await aggregate_assessment(db, project_id, assessment)
    sync_masters(aggregated, user)

    project = require(await project_repo.get_by_id_with_retention(db, project_id), "Project")
    await assessment_repo.update(
        db,
        assessment,
        **summarise_assessment(aggregated.aggregate, project).model_dump(),
        status=AssessmentStatus.finalised,
        finalised_at=datetime.now(UTC),
        updated_by=user.id,
    )

    await db.commit()
    return reloaded(await assessment_repo.get_by_id(db, assessment_id, project_id=project_id), "Assessment")


async def revert_to_draft(db: AsyncSession, project_id: uuid.UUID, assessment_id: uuid.UUID, user: User) -> Assessment:
    assessment = require(await assessment_repo.get_by_id(db, assessment_id, project_id=project_id), "Assessment")
    if assessment.status != AssessmentStatus.finalised:
        raise BadRequestError("Assessment is not finalised")

    # Block revert if a subsequent claim exists
    claims = await claim_repo.get_by_project(db, project_id)
    current_claim = reloaded(next((c for c in claims if c.id == assessment.claim_id), None), "Associated claim")
    if any(c.claim_number > current_claim.claim_number for c in claims):
        raise ConflictError("Cannot revert: a subsequent claim exists for this project")

    assessment.status = AssessmentStatus.draft
    assessment.finalised_at = None
    assessment.updated_by = user.id

    await db.commit()
    return reloaded(await assessment_repo.get_by_id(db, assessment_id, project_id=project_id), "Assessment")
