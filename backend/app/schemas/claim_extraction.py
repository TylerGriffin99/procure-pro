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
