import logging
import uuid
from datetime import date, timedelta
from fastapi import HTTPException, UploadFile
from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

from app.models.claim import Claim, ClaimItemType
from app.models.claim_line_item import ClaimLineItem
from app.models.user import User
from app.models.wbs_code import WBSLevel
from app.repos import (
    claim_repo,
    wbs_code_repo,
    assessment_repo,
    variation_repo,
    provisional_sum_repo,
    harness_repo,
)
from app.schemas.claim import ClaimCreate, ClaimResponse, ClaimSummaryResponse, ClaimUpdate

WORKING_DAYS_OFFSET = 5


def _add_working_days(start: date, days: int) -> date:
    """Add N working days (Mon-Fri) to a date."""
    current = start
    added = 0
    while added < days:
        current += timedelta(days=1)
        if current.weekday() < 5:  # Mon=0 .. Fri=4
            added += 1
    return current


def _payment_due_20th(reference: date) -> date:
    """Return the 20th of the next month after the reference date."""
    if reference.month == 12:
        return date(reference.year + 1, 1, 20)
    return reference.replace(month=reference.month + 1, day=20)


def _auto_fill_dates(claim_received: date | None) -> dict[str, date | None]:
    """Derive schedule dates from claim_received using 5 working-day offsets."""
    if not claim_received:
        return {}
    provisional = _add_working_days(claim_received, WORKING_DAYS_OFFSET)
    schedule = _add_working_days(provisional, WORKING_DAYS_OFFSET)
    payment = _payment_due_20th(schedule)
    return {
        "provisional_payment_schedule_due": provisional,
        "payment_schedule_due": schedule,
        "payment_due": payment,
    }


MAX_UPLOAD_BYTES = 25 * 1024 * 1024  # 25 MB


async def create_document_from_upload(
    db: AsyncSession, project_id: uuid.UUID, file: UploadFile
):
    """Validate an uploaded PDF and persist it as a Document. Returns the Document."""
    from app.repos import document_repo

    if file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="Only PDF uploads are supported")
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=400, detail="File exceeds the 25MB limit")
    return await document_repo.create_document(
        db, project_id, file.filename or "upload.pdf", file.content_type, content,
    )


def _build_claim_response(
    claim: Claim,
    assessment_id: uuid.UUID | None = None,
    assessment_status: str | None = None,
) -> ClaimResponse:
    return ClaimResponse(
        id=claim.id,
        project_id=claim.project_id,
        claim_number=claim.claim_number,
        period_from=claim.period_from,
        period_to=claim.period_to,
        payment_due=claim.payment_due,
        claim_received=claim.claim_received,
        provisional_payment_schedule_due=claim.provisional_payment_schedule_due,
        payment_schedule_due=claim.payment_schedule_due,
        parsed_at=claim.parsed_at,
        assessment_id=assessment_id,
        assessment_status=assessment_status,
        line_items=claim.line_items,
        summary=ClaimSummaryResponse(
            original_contract_total=claim.original_contract_total,
            variations_total=claim.variations_total,
            revised_contract_total=claim.revised_contract_total,
            retention_amount=claim.retention_amount,
            claimed_amount=claim.claimed_amount,
        ),
    )


async def create_claim(db: AsyncSession, project_id: uuid.UUID, data: ClaimCreate, user: User) -> ClaimResponse:
    auto_dates = _auto_fill_dates(data.claim_received)
    claim = Claim(
        project_id=project_id,
        claim_number=data.claim_number,
        period_from=data.period_from,
        period_to=data.period_to,
        claim_received=data.claim_received,
        provisional_payment_schedule_due=data.provisional_payment_schedule_due or auto_dates.get("provisional_payment_schedule_due"),
        payment_schedule_due=data.payment_schedule_due or auto_dates.get("payment_schedule_due"),
        payment_due=auto_dates.get("payment_due"),
        created_by=user.id,
    )
    for i, item in enumerate(data.line_items):
        claim.line_items.append(ClaimLineItem(
            item_type=ClaimItemType(item.item_type),
            ref_code=item.ref_code,
            description=item.description,
            contract_value=item.contract_value,
            percentage=item.percentage,
            ptd=item.ptd,
            previous=item.previous,
            current=item.current,
            balance=item.balance,
            sort_order=i,
            created_by=user.id,
        ))
    db.add(claim)
    await db.commit()
    await db.refresh(claim, ["line_items"])
    return _build_claim_response(claim)


async def list_claims(db: AsyncSession, project_id: uuid.UUID) -> list[ClaimResponse]:
    claims = await claim_repo.get_by_project(db, project_id)
    results = []
    for c in claims:
        latest = await assessment_repo.get_latest_by_claim(db, c.id, project_id=project_id)
        results.append(_build_claim_response(
            c,
            assessment_id=latest.id if latest else None,
            assessment_status=latest.status.value if latest else None,
        ))
    return results


async def get_claim(db: AsyncSession, project_id: uuid.UUID, claim_id: uuid.UUID) -> ClaimResponse:
    claim = await claim_repo.get_by_id(db, claim_id, project_id=project_id)
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")
    return _build_claim_response(claim)


async def update_claim(
    db: AsyncSession, project_id: uuid.UUID, claim_id: uuid.UUID, data: ClaimUpdate,
) -> ClaimResponse:
    claim = await claim_repo.get_by_id(db, claim_id, project_id=project_id)
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")

    updates = data.model_dump(exclude_unset=True)

    # If claim_received changed, auto-fill derived dates unless explicitly provided
    if "claim_received" in updates and updates["claim_received"]:
        auto = _auto_fill_dates(updates["claim_received"])
        for key, val in auto.items():
            if key not in updates:
                updates[key] = val

    for key, val in updates.items():
        setattr(claim, key, val)

    await db.commit()
    await db.refresh(claim, ["line_items"])
    return _build_claim_response(claim)


async def delete_claim(db: AsyncSession, project_id: uuid.UUID, claim_id: uuid.UUID) -> None:
    claim = await claim_repo.get_by_id(db, claim_id, project_id=project_id)
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")

    # Capture the source Document behind this claim before its sessions are removed.
    claim_session = await harness_repo.get_session_by_claim(db, claim_id)
    document_id = claim_session.document_id if claim_session else None

    # Collect WBS code IDs referenced by this claim's line items
    claim_wbs_ids = {
        cli.suggested_wbs_code_id
        for cli in claim.line_items
        if cli.suggested_wbs_code_id
    }

    # Delete harness sessions linked to this claim (cascades to workspace_files & flags)
    await harness_repo.delete_sessions_by_claim(db, claim_id)

    # Delete assessments linked to this claim
    await assessment_repo.delete_by_claim(db, claim_id)

    await claim_repo.delete(db, claim)
    await db.flush()

    # Clean up orphaned Variation/PS masters created by reclassification
    # (project-scoped records that may no longer have any assessment rows)
    from app.models.assessment_variation import AssessmentVariation
    from app.models.assessment_provisional_sum import AssessmentProvisionalSum
    from app.models.provisional_sum import ProvisionalSum

    all_variations = await variation_repo.get_by_project(db, project_id)
    for var in all_variations:
        has_rows = await db.execute(
            select(exists().where(AssessmentVariation.variation_id == var.id))
        )
        if not has_rows.scalar():
            await db.delete(var)

    all_ps = await provisional_sum_repo.get_by_project(db, project_id)
    for ps in all_ps:
        has_rows = await db.execute(
            select(exists().where(AssessmentProvisionalSum.provisional_sum_id == ps.id))
        )
        if not has_rows.scalar():
            await db.delete(ps)

    await db.flush()

    # Clean up orphaned WBS subcategories
    if claim_wbs_ids:
        for wbs_id in claim_wbs_ids:
            still_in_use = await wbs_code_repo.is_in_use(db, wbs_id)
            if not still_in_use:
                wbs_obj = await wbs_code_repo.get_by_id(db, wbs_id)
                if wbs_obj and wbs_obj.level == WBSLevel.subcategory:
                    await wbs_code_repo.delete(db, wbs_obj)

    # Delete the source Document (cascades away any remaining sessions on it).
    if document_id is not None:
        from app.repos import document_repo
        document = await document_repo.get_document(db, document_id)
        if document is not None:
            await db.delete(document)
            await db.flush()

    await db.commit()
