import uuid
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from decimal import Decimal
from typing import assert_never

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
    CENTS,
    COMMENT_PREFIX_CLOSED_OUT,
    COMMENT_PREFIX_INTERIM,
    COMMENT_SEPARATOR,
    PDF_MEDIA_TYPE,
    XLSX_MEDIA_TYPE,
)
from app.exceptions import BadRequestError, ConflictError, NotFoundError
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
from app.schemas.assessment_aggregate import AssessmentAggregate
from app.schemas.retention import RetentionTier
from app.services.assessment_aggregate import aggregate_assessment, export_display, recompute_item, rollup_status
from app.utils.assessment_aggregator import compute_assessment_totals
from app.utils.assessment_engine import calculate_retention, calculate_retention_per_tier
from app.utils.dates import auto_fill_dates
from app.utils.excel_generator import generate_payment_recommendation_excel
from app.utils.pdf_generator import generate_payment_recommendation_pdf

InterimItem = AssessmentLineItem | AssessmentVariation | AssessmentProvisionalSum


def _fmt_date(d) -> str:
    """Format a date for the PDF, handling both date and datetime objects."""
    if not d:
        return ""
    if hasattr(d, "date"):
        d = d.date()
    return d.strftime("%-d %B %Y")


def _resolve_claim_dates(claim) -> dict[str, str]:
    """Resolve claim dates for PDF, falling back to created_at and auto-calculating."""
    if not claim:
        return {
            "claim_received": "",
            "provisional_payment_schedule_due": "",
            "payment_schedule_due": "",
            "payment_due": "",
        }

    claim_received = claim.claim_received
    if not claim_received and claim.created_at:
        # No explicit claim_received — use created_at and recalculate all dates
        claim_received = claim.created_at.date() if hasattr(claim.created_at, "date") else claim.created_at
        auto = auto_fill_dates(claim_received)
        return {
            "claim_received": _fmt_date(claim_received),
            "provisional_payment_schedule_due": _fmt_date(auto["provisional_payment_schedule_due"]),
            "payment_schedule_due": _fmt_date(auto["payment_schedule_due"]),
            "payment_due": _fmt_date(auto["payment_due"]),
        }

    provisional = claim.provisional_payment_schedule_due
    schedule = claim.payment_schedule_due
    payment = claim.payment_due

    if claim_received and (not provisional or not schedule or not payment):
        auto = auto_fill_dates(claim_received)
        provisional = provisional or auto.get("provisional_payment_schedule_due")
        schedule = schedule or auto.get("payment_schedule_due")
        payment = payment or auto.get("payment_due")

    return {
        "claim_received": _fmt_date(claim_received),
        "provisional_payment_schedule_due": _fmt_date(provisional),
        "payment_schedule_due": _fmt_date(schedule),
        "payment_due": _fmt_date(payment),
    }


async def create_assessment(db: AsyncSession, project_id: uuid.UUID, data: AssessmentCreate, user: User) -> Assessment:
    # Load claim with line items
    claim = await claim_repo.get_by_id(db, data.claim_id)
    if not claim:
        raise NotFoundError("Claim not found")

    # Get previously certified amount from latest finalised assessment
    prev_assessment = await assessment_repo.get_latest_finalised(db, project_id)
    previously_certified = prev_assessment.total_payment_to_date if prev_assessment else Decimal("0")

    # Determine version
    latest_version = await assessment_repo.get_latest_version_number(db, data.claim_id)
    version = latest_version + 1

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
    assessment = await assessment_repo.get_latest_by_claim(db, claim_id, project_id=project_id)
    if not assessment:
        raise NotFoundError("Assessment not found")
    return assessment


async def get_aggregated_by_claim(db: AsyncSession, project_id: uuid.UUID, claim_id: uuid.UUID) -> AssessmentAggregate:
    """The latest assessment for ``claim_id``, aggregated."""
    assessment = await get_latest_by_claim(db, project_id, claim_id)
    return await get_aggregated_assessment(db, project_id, assessment.id)


async def update_line_item(
    db: AsyncSession, assessment_id: uuid.UUID, line_item_id: uuid.UUID, data: AssessmentLineItemUpdate, user: User
) -> AssessmentLineItem:
    item = await assessment_line_item_repo.get_by_id(db, line_item_id, assessment_id)
    if not item:
        raise NotFoundError("Line item not found")

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
    assessment = await assessment_repo.get_by_id(db, assessment_id, project_id=project_id)
    if not assessment:
        raise NotFoundError("Assessment not found")
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
        wbs_interims=_interim_groups(wbs_groups),
        variation_interims=_interim_groups(var_groups),
        ps_interims=_interim_groups(ps_groups),
    )


def _interim_groups(groups: Mapping[uuid.UUID, Sequence[InterimItem]]) -> list[PriorInterimResponse]:
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
    assessment = await assessment_repo.get_by_id(db, assessment_id, project_id=project_id)
    if not assessment:
        raise NotFoundError("Assessment not found")
    if assessment.status != AssessmentStatus.draft:
        raise BadRequestError("Assessment must be in draft to add adjustments")

    prev_assessment = await assessment_repo.get_latest_finalised(db, project_id)
    source_id = prev_assessment.id if prev_assessment and prev_assessment.id != assessment_id else None

    comment_prefix = COMMENT_PREFIX_INTERIM
    comment_text = f"{comment_prefix}{COMMENT_SEPARATOR}{data.comments}" if data.comments else comment_prefix

    match data.item_type:
        case AssessmentItemKind.line_item:
            history = next(
                (
                    li
                    for li in assessment.line_items
                    if li.wbs_code_id == data.parent_id and li.claim_line_item_id is None and not li.adjustment_type
                ),
                None,
            )
            group_prev_paid = history.previously_paid if history else Decimal("0")
            difference = data.agreed_total - group_prev_paid

            max_sort = max((li.sort_order for li in assessment.line_items), default=-1)
            new_item = AssessmentLineItem(
                assessment_id=assessment_id,
                claim_line_item_id=None,
                wbs_code_id=data.parent_id,
                description=history.description if history else "Interim adjustment",
                contractor_claim_to_date=Decimal("0"),
                total_recommended=difference,
                percentage=Decimal("0"),
                variance_to_claim=difference,
                previously_paid=Decimal("0"),
                recommended_this_period=difference,
                status=LineItemStatus.interim,
                comments=comment_text,
                sort_order=max_sort + 1,
                adjustment_type=AdjustmentType.interim_adjustment,
                source_assessment_id=source_id,
                created_by=user.id,
            )
            db.add(new_item)

        case AssessmentItemKind.variation:
            history = next(
                (
                    av
                    for av in assessment.variation_items
                    if av.variation_id == data.parent_id and av.claim_line_item_id is None and not av.adjustment_type
                ),
                None,
            )
            group_prev_paid = history.previously_paid if history else Decimal("0")
            difference = data.agreed_total - group_prev_paid

            new_item = AssessmentVariation(
                assessment_id=assessment_id,
                variation_id=data.parent_id,
                claim_line_item_id=None,
                contractor_claim_to_date=Decimal("0"),
                total_recommended=difference,
                percentage=Decimal("0"),
                variance_to_claim=difference,
                previously_paid=Decimal("0"),
                recommended_this_period=difference,
                status=LineItemStatus.interim,
                comments=comment_text,
                adjustment_type=AdjustmentType.interim_adjustment,
                source_assessment_id=source_id,
                created_by=user.id,
            )
            db.add(new_item)

        case AssessmentItemKind.provisional_sum:
            history = next(
                (
                    ps
                    for ps in assessment.provisional_sum_items
                    if ps.provisional_sum_id == data.parent_id
                    and ps.claim_line_item_id is None
                    and not ps.adjustment_type
                ),
                None,
            )
            group_prev_paid = history.previously_paid if history else Decimal("0")
            difference = data.agreed_total - group_prev_paid

            new_item = AssessmentProvisionalSum(
                assessment_id=assessment_id,
                provisional_sum_id=data.parent_id,
                claim_line_item_id=None,
                contractor_claim_to_date=Decimal("0"),
                total_recommended=difference,
                percentage=Decimal("0"),
                variance_to_claim=difference,
                previously_paid=Decimal("0"),
                recommended_this_period=difference,
                status=LineItemStatus.interim,
                comments=comment_text,
                adjustment_type=AdjustmentType.interim_adjustment,
                source_assessment_id=source_id,
                created_by=user.id,
            )
            db.add(new_item)
        case _:
            assert_never(data.item_type)

    await db.commit()
    return await get_aggregated_assessment(db, project_id, assessment_id)


async def close_out_item(
    db: AsyncSession, project_id: uuid.UUID, assessment_id: uuid.UUID, data: CloseOutRequest, user: User
) -> AssessmentAggregate:
    """Close out an interim item — sets all rows for this parent to 'approved' status."""
    assessment = await assessment_repo.get_by_id(db, assessment_id, project_id=project_id)
    if not assessment:
        raise NotFoundError("Assessment not found")
    if assessment.status != AssessmentStatus.draft:
        raise BadRequestError("Assessment must be in draft to close out items")

    def _update_comment(item):
        """Update comment prefix from Interim to Closed Out (idempotent)."""
        if item.claim_line_item_id is None:
            if item.comments:
                if item.comments.startswith(COMMENT_PREFIX_CLOSED_OUT):
                    return  # already closed out, don't double-prefix
                if item.comments.startswith(COMMENT_PREFIX_INTERIM):
                    item.comments = COMMENT_PREFIX_CLOSED_OUT + item.comments[len(COMMENT_PREFIX_INTERIM) :]
                else:
                    item.comments = f"{COMMENT_PREFIX_CLOSED_OUT}{COMMENT_SEPARATOR}{item.comments}"
            else:
                item.comments = COMMENT_PREFIX_CLOSED_OUT

    match data.item_type:
        case AssessmentItemKind.line_item:
            matching = [li for li in assessment.line_items if li.wbs_code_id == data.parent_id]
            for item in matching:
                item.status = LineItemStatus.approved
                item.is_closed_out = True
                _update_comment(item)
                item.updated_by = user.id

        case AssessmentItemKind.variation:
            matching = [av for av in assessment.variation_items if av.variation_id == data.parent_id]
            for item in matching:
                item.status = LineItemStatus.approved
                item.is_closed_out = True
                _update_comment(item)
                item.updated_by = user.id

        case AssessmentItemKind.provisional_sum:
            matching = [ps for ps in assessment.provisional_sum_items if ps.provisional_sum_id == data.parent_id]
            for item in matching:
                item.status = LineItemStatus.approved
                item.is_closed_out = True
                _update_comment(item)
                item.updated_by = user.id
        case _:
            assert_never(data.item_type)

    await db.commit()
    return await get_aggregated_assessment(db, project_id, assessment_id)


async def generate_assessment_export(
    db: AsyncSession, project_id: uuid.UUID, assessment_id: uuid.UUID, format: ExportFormat = ExportFormat.pdf
) -> tuple[bytes, str]:
    assessment = await assessment_repo.get_by_id(db, assessment_id, project_id=project_id)
    if not assessment:
        raise NotFoundError("Assessment not found")

    project = await project_repo.get_by_id_with_retention(db, project_id)
    if project is None:
        raise NotFoundError("Project not found")
    claim = await claim_repo.get_by_id(db, assessment.claim_id)

    aggregate = (await aggregate_assessment(db, project_id, assessment)).aggregate
    wbs_groups, var_groups, ps_groups = aggregate.wbs_groups, aggregate.variation_groups, aggregate.ps_groups

    # Build contract_works list for PDF
    contract_works = []
    for g in wbs_groups:
        all_rows = ([g.history_row] if g.history_row else []) + g.child_rows
        comments = "; ".join(r.comments for r in all_rows if r.comments)
        contract_works.append(
            {
                "description": g.description,
                "contract_sum": g.contract_sum,
                "contractor_claim": g.contractor_claim_to_date,
                "recommended": g.total_recommended,
                "percentage": f"{g.percentage:.1f}%",
                "variance": g.variance_to_claim,
                "previously_paid": g.previously_paid,
                "recommended_this_period": g.recommended_this_period,
                "comments": comments,
            }
        )

    # Build variation_works list for PDF
    variation_works = []
    for g in var_groups:
        display_comments, display_status = export_display(g.history_row, g.child_rows)
        variation_works.append(
            {
                "ci_number": g.contractor_ref,
                "description": g.description,
                "submission": g.contractor_submission,
                "type": "",
                "claimed_to_date": g.contractor_claim_to_date,
                "recommended": g.total_recommended,
                "previously_paid": g.previously_paid,
                "this_period": g.recommended_this_period,
                "status": display_status,
                "comments": display_comments,
            }
        )

    # Build provisional_sums list for PDF
    provisional_sums = []
    for g in ps_groups:
        display_comments, display_status = export_display(g.history_row, g.child_rows)
        provisional_sums.append(
            {
                "ps_number": g.ps_number,
                "description": g.description,
                "contract_sum": g.contract_sum,
                "claimed_to_date": g.contractor_claim_to_date,
                "recommended": g.total_recommended,
                "previously_paid": g.previously_paid,
                "this_period": g.recommended_this_period,
                "percentage": f"{g.percentage:.1f}%",
                "status": display_status,
                "comments": display_comments,
            }
        )

    # Calculate totals using aggregator
    totals = compute_assessment_totals(wbs_groups, var_groups, ps_groups)

    total_recommended = totals.total_recommended
    value_claimed = totals.value_claimed_to_date
    adjustments = totals.adjustments

    retention_tiers = [
        RetentionTier(percentage=t.percentage, up_to_amount=t.up_to_amount) for t in project.retention_tiers
    ]
    total_retention = calculate_retention(total_recommended, retention_tiers)
    retention_details = calculate_retention_per_tier(total_recommended, retention_tiers)

    previously_certified = assessment.previously_certified or Decimal("0")
    payment_to_date = total_recommended - total_retention
    recommended_this_period = payment_to_date - previously_certified
    gst = (recommended_this_period * project.gst_rate).quantize(CENTS)

    pdf_data = {
        "project_name": project.name,
        "project_number": project.project_number or "",
        "pr_number": claim.claim_number if claim else assessment.version,
        "revision": 0,
        "issue_date": assessment.created_at.strftime("%d %B %Y") if assessment.created_at else "",
        "principal": project.client_name,
        "end_client_name": project.end_client_name or project.client_name,
        "end_client_address_lines": (project.end_client_address or "").split("\n")
        if project.end_client_address
        else [],
        "end_client_representative_first_name": (project.end_client_representative or "").split()[0]
        if project.end_client_representative
        else "",
        "landlord_split_pct": project.landlord_split_pct,
        "operator_split_pct": project.operator_split_pct,
        "landlord_amount": (recommended_this_period * project.landlord_split_pct).quantize(CENTS)
        if project.landlord_split_pct
        else Decimal("0"),
        "operator_amount": (recommended_this_period * project.operator_split_pct).quantize(CENTS)
        if project.operator_split_pct
        else Decimal("0"),
        "engineer": project.end_client_representative or "",
        "contractor": project.contractor_name,
        "claim_number": claim.claim_number if claim else assessment.version,
        **_resolve_claim_dates(claim),
        "contract_sum": project.contract_sum,
        "adjustment_to_provisional_sums": totals.adjustment_to_provisional_sums,
        "approved_variation_orders": totals.approved_variation_orders,
        "adjusted_contract_sum": project.contract_sum
        + totals.approved_variation_orders
        + totals.adjustment_to_provisional_sums,
        "value_claimed": value_claimed,
        "adjustments": adjustments,
        "total_recommended": total_recommended,
        "retention_details": retention_details,
        "total_retention": total_retention,
        "total_payment_to_date": payment_to_date,
        "previously_certified": previously_certified,
        "recommended_this_period": recommended_this_period,
        "gst_rate": project.gst_rate,
        "gst_amount": gst,
        "total_including_gst": recommended_this_period + gst,
        "contract_works": contract_works,
        "variation_works": variation_works,
        "provisional_sums": provisional_sums,
        "is_draft": assessment.status != AssessmentStatus.finalised,
    }

    if format == ExportFormat.excel:
        return generate_payment_recommendation_excel(pdf_data), XLSX_MEDIA_TYPE
    return generate_payment_recommendation_pdf(pdf_data), PDF_MEDIA_TYPE


async def update_variation_item(
    db: AsyncSession, assessment_id: uuid.UUID, item_id: uuid.UUID, data: AssessmentVariationUpdate, user: User
) -> AssessmentVariation:
    item = await assessment_variation_repo.get_by_id(db, item_id, assessment_id)
    if not item:
        raise NotFoundError("Variation item not found")

    if data.total_recommended is not None:
        item.total_recommended = data.total_recommended
        recompute_item(item, denominator=item.variation.contractor_submission if item.variation else None)

    if data.status is not None:
        item.status = data.status
    if data.comments is not None:
        item.comments = data.comments

    item.updated_by = user.id

    await db.commit()
    refreshed = await assessment_variation_repo.get_by_id(db, item.id, assessment_id)
    if refreshed is None:
        raise NotFoundError("Variation item not found after update")
    return refreshed


async def update_provisional_sum_item(
    db: AsyncSession, assessment_id: uuid.UUID, item_id: uuid.UUID, data: AssessmentProvisionalSumUpdate, user: User
) -> AssessmentProvisionalSum:
    item = await assessment_provisional_sum_repo.get_by_id(db, item_id, assessment_id)
    if not item:
        raise NotFoundError("Provisional sum item not found")

    if data.total_recommended is not None:
        item.total_recommended = data.total_recommended
        recompute_item(item, denominator=item.provisional_sum.contract_sum if item.provisional_sum else None)

    if data.status is not None:
        item.status = data.status
    if data.comments is not None:
        item.comments = data.comments

    item.updated_by = user.id

    await db.commit()
    refreshed = await assessment_provisional_sum_repo.get_by_id(db, item.id, assessment_id)
    if refreshed is None:
        raise NotFoundError("Provisional sum item not found after update")
    return refreshed


async def reclassify_item(
    db: AsyncSession, project_id: uuid.UUID, assessment_id: uuid.UUID, data: ReclassifyRequest, user: User
) -> Assessment:
    assessment = await assessment_repo.get_by_id(db, assessment_id, project_id=project_id)
    if not assessment:
        raise NotFoundError("Assessment not found")

    # Find source row in the appropriate list
    source_row = None
    match data.source_type:
        case AssessmentItemKind.line_item:
            source_row = next((li for li in assessment.line_items if li.id == data.source_item_id), None)
        case AssessmentItemKind.variation:
            source_row = next((av for av in assessment.variation_items if av.id == data.source_item_id), None)
        case AssessmentItemKind.provisional_sum:
            source_row = next((ps for ps in assessment.provisional_sum_items if ps.id == data.source_item_id), None)
        case _:
            assert_never(data.source_type)

    if not source_row:
        raise NotFoundError("Source item not found")
    if source_row.claim_line_item_id is None:
        raise BadRequestError("Cannot reclassify a history row without a linked claim line item")

    # Capture carried values
    recommended_this_period = source_row.recommended_this_period
    contractor_claim_to_date = source_row.contractor_claim_to_date
    claim_line_item_id = source_row.claim_line_item_id

    # Get linked ClaimLineItem for description and contract_value
    cli = await claim_line_item_repo.get_by_id(db, claim_line_item_id)
    description = cli.description if cli else ""
    contract_value = cli.contract_value if cli else Decimal("0")

    # WBS-to-WBS: same type, just update the wbs_code_id
    if data.source_type == AssessmentItemKind.line_item and data.target_type == AssessmentItemKind.line_item:
        if not data.target_wbs_code_id:
            raise BadRequestError("target_wbs_code_id is required when target_type is 'line-item'")
        assert isinstance(source_row, AssessmentLineItem)
        await assessment_line_item_repo.update(db, source_row, wbs_code_id=data.target_wbs_code_id)
        await db.commit()
        refreshed = await assessment_repo.get_by_id(db, assessment_id, project_id=project_id)
        if refreshed is None:
            raise NotFoundError("Assessment not found after reclassify")
        return refreshed

    # Cross-type: delete source, create new target row
    match data.source_type:
        case AssessmentItemKind.line_item:
            assert isinstance(source_row, AssessmentLineItem)
            await assessment_line_item_repo.delete(db, source_row)
        case AssessmentItemKind.variation:
            assert isinstance(source_row, AssessmentVariation)
            await assessment_variation_repo.delete(db, source_row)
        case AssessmentItemKind.provisional_sum:
            assert isinstance(source_row, AssessmentProvisionalSum)
            await assessment_provisional_sum_repo.delete(db, source_row)
        case _:
            assert_never(data.source_type)
    # Expire the assessment so collections are reloaded fresh
    db.expire(assessment)

    match data.target_type:
        case AssessmentItemKind.variation:
            # Find or create variation master record
            if data.target_id:
                # Use existing variation — query project variations directly
                existing_variations = await variation_repo.get_by_project(db, project_id)
                variation = next((v for v in existing_variations if v.id == data.target_id), None)
                if not variation:
                    raise NotFoundError("Target variation not found")
            else:
                max_ci = await variation_repo.get_max_ci_number(db, project_id)
                new_desc = data.new_record.description if data.new_record else description
                variation = await variation_repo.create(
                    db,
                    project_id=project_id,
                    ci_number=max_ci + 1,
                    contractor_ref=f"CI-{max_ci + 1:03d}",
                    description=new_desc,
                    contractor_submission=contract_value,
                    status=VariationStatus.unapproved,
                    wbs_code_id=data.target_wbs_code_id,
                    created_by=user.id,
                )

            await assessment_variation_repo.create(
                db,
                assessment_id=assessment_id,
                variation_id=variation.id,
                claim_line_item_id=claim_line_item_id,
                contractor_claim_to_date=contractor_claim_to_date,
                total_recommended=recommended_this_period,
                percentage=Decimal("0"),
                variance_to_claim=recommended_this_period - contractor_claim_to_date,
                previously_paid=Decimal("0"),
                recommended_this_period=recommended_this_period,
                status=LineItemStatus.unapproved,
                created_by=user.id,
            )

        case AssessmentItemKind.provisional_sum:
            if data.target_id:
                existing_ps = await provisional_sum_repo.get_by_project(db, project_id)
                ps = next((p for p in existing_ps if p.id == data.target_id), None)
                if not ps:
                    raise NotFoundError("Target provisional sum not found")
            else:
                max_ps = await provisional_sum_repo.get_max_ps_number(db, project_id)
                new_desc = data.new_record.description if data.new_record else description
                ps = await provisional_sum_repo.create(
                    db,
                    project_id=project_id,
                    ps_number=max_ps + 1,
                    description=new_desc,
                    contract_sum=contract_value,
                    status=VariationStatus.unapproved,
                    wbs_code_id=data.target_wbs_code_id,
                    created_by=user.id,
                )

            await assessment_provisional_sum_repo.create(
                db,
                assessment_id=assessment_id,
                provisional_sum_id=ps.id,
                claim_line_item_id=claim_line_item_id,
                contractor_claim_to_date=contractor_claim_to_date,
                total_recommended=recommended_this_period,
                percentage=Decimal("0"),
                variance_to_claim=recommended_this_period - contractor_claim_to_date,
                previously_paid=Decimal("0"),
                recommended_this_period=recommended_this_period,
                status=LineItemStatus.unapproved,
                created_by=user.id,
            )

        case AssessmentItemKind.line_item:
            if not data.target_wbs_code_id:
                raise BadRequestError("target_wbs_code_id is required when target_type is 'line-item'")
            # From variation/PS back to line-item
            # Use explicit query instead of assessment.line_items to avoid MissingGreenlet
            # (db.expire above invalidates cached collections; lazy reload fails in async)
            await db.refresh(assessment, ["line_items"])
            max_sort = max((li.sort_order for li in assessment.line_items), default=-1)
            await assessment_line_item_repo.create(
                db,
                assessment_id=assessment_id,
                claim_line_item_id=claim_line_item_id,
                wbs_code_id=data.target_wbs_code_id,
                description=description,
                contractor_claim_to_date=contractor_claim_to_date,
                total_recommended=recommended_this_period,
                percentage=Decimal("0"),
                variance_to_claim=recommended_this_period - contractor_claim_to_date,
                previously_paid=Decimal("0"),
                recommended_this_period=recommended_this_period,
                status=LineItemStatus.unapproved,
                sort_order=max_sort + 1,
                created_by=user.id,
            )
        case _:
            assert_never(data.target_type)

    await db.commit()
    # Expire the assessment so the identity map doesn't return stale collections
    db.expire(assessment)
    refreshed = await assessment_repo.get_by_id(db, assessment_id, project_id=project_id)
    if refreshed is None:
        raise NotFoundError("Assessment not found after reclassify")
    return refreshed


async def finalise_assessment(
    db: AsyncSession, project_id: uuid.UUID, assessment_id: uuid.UUID, user: User
) -> Assessment:
    assessment = await assessment_repo.get_by_id(db, assessment_id, project_id=project_id)
    if not assessment:
        raise NotFoundError("Assessment not found")

    aggregated = await aggregate_assessment(db, project_id, assessment)
    var_groups, ps_groups = aggregated.aggregate.variation_groups, aggregated.aggregate.ps_groups
    totals = compute_assessment_totals(aggregated.aggregate.wbs_groups, var_groups, ps_groups)

    # Sync variation master records from aggregated groups (not individual items)
    var_map = {v.id: v for v in aggregated.variations}
    for g in var_groups:
        master = var_map.get(g.variation_id)
        if master:
            master.approved_amount = g.total_recommended
            master.contractor_submission = g.contractor_claim_to_date
            master.status = rollup_status(([g.history_row] if g.history_row else []) + g.child_rows)
            master.updated_by = user.id

    # Sync provisional sum master records from aggregated groups
    ps_map = {p.id: p for p in aggregated.provisional_sums}
    for g in ps_groups:
        master = ps_map.get(g.provisional_sum_id)
        if master:
            master.approved_amount = g.total_recommended
            master.status = rollup_status(([g.history_row] if g.history_row else []) + g.child_rows)
            master.updated_by = user.id

    project = await project_repo.get_by_id_with_retention(db, project_id)
    if project is None:
        raise NotFoundError("Project not found")
    assessment.contract_sum = project.contract_sum
    assessment.approved_variation_orders = totals.approved_variation_orders
    assessment.adjustment_to_provisional_sums = totals.adjustment_to_provisional_sums
    assessment.adjusted_contract_sum = (
        project.contract_sum + totals.approved_variation_orders + totals.adjustment_to_provisional_sums
    )
    total_recommended = totals.total_recommended
    assessment.total_recommended = total_recommended

    # Calculate retention and payment-to-date for use by future assessments
    retention_tiers = [
        RetentionTier(percentage=t.percentage, up_to_amount=t.up_to_amount) for t in project.retention_tiers
    ]
    total_retention = calculate_retention(total_recommended, retention_tiers)
    assessment.total_retention = total_retention
    total_payment_to_date = total_recommended - total_retention
    assessment.total_payment_to_date = total_payment_to_date

    # Calculate recommended this period
    previously_certified = assessment.previously_certified or Decimal("0")
    assessment.recommended_this_period = total_payment_to_date - previously_certified

    assessment.status = AssessmentStatus.finalised
    assessment.finalised_at = datetime.now(UTC)
    assessment.updated_by = user.id

    await db.commit()
    refreshed = await assessment_repo.get_by_id(db, assessment_id, project_id=project_id)
    if refreshed is None:
        raise NotFoundError("Assessment not found after finalise")
    return refreshed


async def revert_to_draft(db: AsyncSession, project_id: uuid.UUID, assessment_id: uuid.UUID, user: User) -> Assessment:
    assessment = await assessment_repo.get_by_id(db, assessment_id, project_id=project_id)
    if not assessment:
        raise NotFoundError("Assessment not found")
    if assessment.status != AssessmentStatus.finalised:
        raise BadRequestError("Assessment is not finalised")

    # Block revert if a subsequent claim exists
    claims = await claim_repo.get_by_project(db, project_id)
    current_claim = next((c for c in claims if c.id == assessment.claim_id), None)
    if not current_claim:
        raise NotFoundError("Associated claim not found")
    if any(c.claim_number > current_claim.claim_number for c in claims):
        raise ConflictError("Cannot revert: a subsequent claim exists for this project")

    assessment.status = AssessmentStatus.draft
    assessment.finalised_at = None
    assessment.updated_by = user.id

    await db.commit()
    refreshed = await assessment_repo.get_by_id(db, assessment_id, project_id=project_id)
    if refreshed is None:
        raise NotFoundError("Assessment not found after revert")
    return refreshed
