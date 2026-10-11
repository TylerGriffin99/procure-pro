from app.schemas.base import StrictModel


class ClaimMetadata(StrictModel):
    claim_number: str | None = None
    period_from: str | None = None
    period_to: str | None = None
    payment_due: str | None = None


class ClaimSummary(StrictModel):
    original_contract_total: str
    revised_contract_total: str
    claimed_amount: str


class MoneyFormatWarning(StrictModel):
    ref: str | None
    field: str
    description: str
