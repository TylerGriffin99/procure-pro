import asyncio
import logging
import uuid
from datetime import date, timedelta
from io import BytesIO

import pdfplumber
from fastapi import UploadFile
from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import BadRequestError, NotFoundError
from app.models.assessment_provisional_sum import AssessmentProvisionalSum
from app.models.assessment_variation import AssessmentVariation
from app.models.claim import Claim, ClaimItemType
from app.models.claim_line_item import ClaimLineItem
from app.models.user import User
from app.models.wbs_code import WBSLevel
from app.repos import (
    assessment_repo,
    claim_repo,
    document_repo,
    harness_repo,
    provisional_sum_repo,
    variation_repo,
    wbs_code_repo,
)
from app.schemas.claim import ClaimCreate, ClaimResponse, ClaimUpdate
from app.services.guardrails import screen_text

logger = logging.getLogger(__name__)

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


def auto_fill_dates(claim_received: date | None) -> dict[str, date | None]:
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


def _extract_screenable_text(content: bytes) -> str:
    """Return the page text + table-cell text a PDF would expose downstream.

    Mirrors what raw_extraction feeds the LLM phases (text and tables) so the
    screen covers the same surface. Raises if the PDF cannot be read.
    """
    parts: list[str] = []
    with pdfplumber.open(BytesIO(content)) as pdf:
        if len(pdf.pages) == 0:
            raise ValueError("PDF has zero pages")
        for page in pdf.pages:
            parts.append(page.extract_text() or "")
            for table in page.extract_tables() or []:
                for row in table:
                    parts.extend(cell for cell in row if cell)
    return "\n".join(parts)


def _screen_pdf_content(content: bytes) -> None:
    """Reject the upload unless it can be read AND is free of disallowed content.

    This is the ingestion trust boundary: a document only reaches the DB if it was
    successfully screened and found clean, so downstream code can treat stored
    documents as trusted. We fail CLOSED — an unreadable PDF is rejected rather
    than stored unscreened, because the screen and a downstream reader are not
    guaranteed to fail on the same inputs.
    """
    try:
        text = _extract_screenable_text(content)
    except Exception as e:
        logger.warning("Rejected upload: PDF could not be read for screening", exc_info=True)
        raise BadRequestError("Could not read the PDF to screen it") from e

    if not text.strip():
        # Parsed, but yielded no text/tables to screen (e.g. an image-only scan).
        # Fail closed: we can't vouch for content we couldn't extract.
        logger.warning("Rejected upload: PDF has no extractable text to screen")
        raise BadRequestError("PDF has no extractable text to screen")

    violations = screen_text(text)
    if violations:
        categories = sorted({v.category for v in violations})
        # Snippets are attacker-controlled: log them (repr guards against log
        # injection) but never reflect them to the client.
        snippets = "; ".join(f"{v.category}:{v.snippet!r}" for v in violations)
        logger.warning(
            "Rejected upload: disallowed content [%s] — %s", ", ".join(categories), snippets
        )
        raise BadRequestError(
            f"Document rejected: it contains disallowed content ({', '.join(categories)})",
        )


async def create_document_from_upload(db: AsyncSession, project_id: uuid.UUID, file: UploadFile):
    """Validate an uploaded PDF and persist it as a Document. Returns the Document."""
    if file.content_type != "application/pdf":
        raise BadRequestError("Only PDF uploads are supported")
    content = await file.read()
    if not content:
        raise BadRequestError("Uploaded file is empty")
    if len(content) > MAX_UPLOAD_BYTES:
        raise BadRequestError("File exceeds the 25MB limit")

    await asyncio.to_thread(_screen_pdf_content, content)  # PDF parse is blocking
    return await document_repo.create_document(
        db,
        project_id,
        file.filename or "upload.pdf",
        file.content_type,
        content,
    )


async def create_claim(
    db: AsyncSession, project_id: uuid.UUID, data: ClaimCreate, user: User
) -> ClaimResponse:
    auto_dates = auto_fill_dates(data.claim_received)
    claim = Claim(
        project_id=project_id,
        claim_number=data.claim_number,
        period_from=data.period_from,
        period_to=data.period_to,
        claim_received=data.claim_received,
        provisional_payment_schedule_due=data.provisional_payment_schedule_due
        or auto_dates.get("provisional_payment_schedule_due"),
        payment_schedule_due=data.payment_schedule_due or auto_dates.get("payment_schedule_due"),
        payment_due=auto_dates.get("payment_due"),
        created_by=user.id,
    )
    for i, item in enumerate(data.line_items):
        claim.line_items.append(
            ClaimLineItem(
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
            )
        )
    db.add(claim)
    await db.commit()
    await db.refresh(claim, ["line_items"])
    return ClaimResponse.from_claim(claim)


async def list_claims(db: AsyncSession, project_id: uuid.UUID) -> list[ClaimResponse]:
    claims = await claim_repo.get_by_project(db, project_id)
    results = []
    for c in claims:
        latest = await assessment_repo.get_latest_by_claim(db, c.id, project_id=project_id)
        results.append(
            ClaimResponse.from_claim(
                c,
                assessment_id=latest.id if latest else None,
                assessment_status=latest.status.value if latest else None,
            )
        )
    return results


async def get_claim(db: AsyncSession, project_id: uuid.UUID, claim_id: uuid.UUID) -> ClaimResponse:
    claim = await claim_repo.get_by_id(db, claim_id, project_id=project_id)
    if not claim:
        raise NotFoundError("Claim not found")
    return ClaimResponse.from_claim(claim)


async def update_claim(
    db: AsyncSession,
    project_id: uuid.UUID,
    claim_id: uuid.UUID,
    data: ClaimUpdate,
) -> ClaimResponse:
    claim = await claim_repo.get_by_id(db, claim_id, project_id=project_id)
    if not claim:
        raise NotFoundError("Claim not found")

    updates = data.model_dump(exclude_unset=True)

    # If claim_received changed, auto-fill derived dates unless explicitly provided
    if updates.get("claim_received"):
        auto = auto_fill_dates(updates["claim_received"])
        for key, val in auto.items():
            if key not in updates:
                updates[key] = val

    for key, val in updates.items():
        setattr(claim, key, val)

    await db.commit()
    await db.refresh(claim, ["line_items"])
    return ClaimResponse.from_claim(claim)


async def delete_claim(db: AsyncSession, project_id: uuid.UUID, claim_id: uuid.UUID) -> None:
    claim = await claim_repo.get_by_id(db, claim_id, project_id=project_id)
    if not claim:
        raise NotFoundError("Claim not found")

    # Capture the source Document behind this claim before its sessions are removed.
    claim_session = await harness_repo.get_session_by_claim(db, claim_id)
    document_id = claim_session.document_id if claim_session else None

    # Collect WBS code IDs referenced by this claim's line items
    claim_wbs_ids = {
        cli.suggested_wbs_code_id for cli in claim.line_items if cli.suggested_wbs_code_id
    }

    # Delete harness sessions linked to this claim (cascades to workspace_files & flags)
    await harness_repo.delete_sessions_by_claim(db, claim_id)

    # Delete assessments linked to this claim
    await assessment_repo.delete_by_claim(db, claim_id)

    await claim_repo.delete(db, claim)
    await db.flush()

    # Clean up orphaned Variation/PS masters created by reclassification
    # (project-scoped records that may no longer have any assessment rows)
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
        document = await document_repo.get_document(db, document_id)
        if document is not None:
            await db.delete(document)
            await db.flush()

    await db.commit()
