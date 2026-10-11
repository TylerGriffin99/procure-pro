import asyncio
import logging
import uuid

from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants.values import PDF_MEDIA_TYPE
from app.exceptions import BadRequestError, NotFoundError
from app.harness.models import HarnessType
from app.models.claim import Claim
from app.models.claim_line_item import ClaimLineItem
from app.models.user import User
from app.repos import (
    assessment_repo,
    claim_repo,
    document_repo,
    harness_repo,
    provisional_sum_repo,
    variation_repo,
    wbs_code_repo,
)
from app.schemas.claim import ClaimCreate, ClaimResponse, ClaimUpdate, ClaimUploadResponse
from app.services import guardrails
from app.utils.dates import auto_fill_dates

logger = logging.getLogger(__name__)

MAX_UPLOAD_BYTES = 25 * 1024 * 1024  # 25 MB


async def create_document_from_upload(db: AsyncSession, project_id: uuid.UUID, file: UploadFile):
    """Validate an uploaded PDF and persist it as a Document. Returns the Document."""
    if file.content_type != PDF_MEDIA_TYPE:
        raise BadRequestError("Only PDF uploads are supported")
    content = await file.read()
    if not content:
        raise BadRequestError("Uploaded file is empty")
    if len(content) > MAX_UPLOAD_BYTES:
        raise BadRequestError("File exceeds the 25MB limit")

    await asyncio.to_thread(guardrails.screen_pdf, content)  # PDF parse is blocking
    return await document_repo.create_document(
        db, project_id, file.filename or "upload.pdf", file.content_type, content
    )


async def upload_claim(db: AsyncSession, project_id: uuid.UUID, file: UploadFile, user: User) -> ClaimUploadResponse:
    """Store the screened PDF and open a CLAIM_PARSE harness session on it."""
    document = await create_document_from_upload(db, project_id, file)
    session = await harness_repo.create_session(
        db=db,
        user_id=user.id,
        project_id=project_id,
        harness_type=HarnessType.CLAIM_PARSE,
        document_id=document.id,
        config={"document_id": str(document.id)},
    )
    await db.commit()
    return ClaimUploadResponse(harness_session_id=session.id)


async def create_claim(db: AsyncSession, project_id: uuid.UUID, data: ClaimCreate, user: User) -> ClaimResponse:
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
                item_type=item.item_type,
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
    latest = await assessment_repo.latest_assessments_by_claim(db, project_id)
    return [
        ClaimResponse.from_claim(
            c,
            assessment_id=latest[c.id].id if c.id in latest else None,
            assessment_status=latest[c.id].status.value if c.id in latest else None,
        )
        for c in claims
    ]


async def get_claim(db: AsyncSession, project_id: uuid.UUID, claim_id: uuid.UUID) -> ClaimResponse:
    claim = await claim_repo.get_by_id(db, claim_id, project_id=project_id)
    if not claim:
        raise NotFoundError("Claim not found")
    return ClaimResponse.from_claim(claim)


async def update_claim(
    db: AsyncSession, project_id: uuid.UUID, claim_id: uuid.UUID, data: ClaimUpdate
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
    claim_wbs_ids = {cli.suggested_wbs_code_id for cli in claim.line_items if cli.suggested_wbs_code_id}

    # Delete harness sessions linked to this claim (cascades to workspace_files & flags)
    await harness_repo.delete_sessions_by_claim(db, claim_id)

    # Delete assessments linked to this claim
    await assessment_repo.delete_by_claim(db, claim_id)

    await claim_repo.delete(db, claim)
    # Orphan cleanup is project-wide: masters left without any assessment rows are removed, not just this claim's.
    await variation_repo.delete_orphans(db, project_id)
    await provisional_sum_repo.delete_orphans(db, project_id)
    await wbs_code_repo.delete_unused_subcategories(db, claim_wbs_ids)
    if document_id is not None:
        # Deleting the source Document cascades away any remaining sessions on it.
        await document_repo.delete(db, document_id)

    await db.commit()
