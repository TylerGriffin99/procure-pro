import uuid
from decimal import Decimal

from app.constants.enums import ClaimItemType
from app.schemas.base import StrictModel


class ClaimMetadata(StrictModel):
    claim_number: str | None = None
    period_from: str | None = None
    period_to: str | None = None
    payment_due: str | None = None


class MoneyFormatWarning(StrictModel):
    ref: str | None
    field: str
    description: str


class DroppedRow(StrictModel):
    page: int
    row_index: int
    column_count: int
    first_cell: str | None


class ClaimLineValues(StrictModel):
    item_type: ClaimItemType
    ref_code: str
    description: str
    contract_value: Decimal
    percentage: Decimal
    ptd: Decimal
    previous: Decimal
    current: Decimal
    balance: Decimal
    sort_order: int
    suggested_wbs_code_id: uuid.UUID | None
    variation_id: uuid.UUID | None
    provisional_sum_id: uuid.UUID | None
    categorisation_confidence: Decimal
    created_by: uuid.UUID
