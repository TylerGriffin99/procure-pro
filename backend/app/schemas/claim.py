import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel

from app.models.claim import ClaimItemType


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
