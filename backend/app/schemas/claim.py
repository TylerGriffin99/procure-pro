from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from pydantic import BaseModel

from app.models.claim import ClaimItemType

if TYPE_CHECKING:
    from app.models.claim import Claim


class ClaimLineItemResponse(BaseModel):
    id: uuid.UUID
    ref_code: str | None
    description: str
    item_type: ClaimItemType
    contract_value: Decimal
    percentage: Decimal
    ptd: Decimal
    previous: Decimal
    current: Decimal
    balance: Decimal
    suggested_wbs_code_id: uuid.UUID | None
    categorisation_confidence: Decimal | None = None
    warnings: list[str] | None = []

    model_config = {"from_attributes": True}


class ClaimSummaryResponse(BaseModel):
    original_contract_total: Decimal | None
    variations_total: Decimal | None
    revised_contract_total: Decimal | None
    retention_amount: Decimal | None
    claimed_amount: Decimal | None


class ClaimResponse(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    claim_number: int
    period_from: date | None
    period_to: date | None
    payment_due: date | None
    claim_received: date | None = None
    provisional_payment_schedule_due: date | None = None
    payment_schedule_due: date | None = None
    parsed_at: datetime | None
    assessment_id: uuid.UUID | None = None
    assessment_status: str | None = None
    line_items: list[ClaimLineItemResponse] = []
    summary: ClaimSummaryResponse
    validation_warnings: list[str] | None = []

    model_config = {"from_attributes": True}

    @classmethod
    def from_claim(
        cls, claim: Claim, *, assessment_id: uuid.UUID | None = None, assessment_status: str | None = None
    ) -> ClaimResponse:
        return cls(
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


class ClaimUploadResponse(BaseModel):
    harness_session_id: uuid.UUID


class ClaimLineItemCreate(BaseModel):
    ref_code: str | None = None
    description: str
    item_type: str
    contract_value: Decimal
    percentage: Decimal
    ptd: Decimal
    previous: Decimal
    current: Decimal
    balance: Decimal


class ClaimCreate(BaseModel):
    claim_number: int
    period_from: date | None = None
    period_to: date | None = None
    claim_received: date | None = None
    provisional_payment_schedule_due: date | None = None
    payment_schedule_due: date | None = None
    line_items: list[ClaimLineItemCreate] = []


class ClaimUpdate(BaseModel):
    claim_received: date | None = None
    provisional_payment_schedule_due: date | None = None
    payment_schedule_due: date | None = None
    payment_due: date | None = None
