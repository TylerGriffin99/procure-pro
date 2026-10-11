from app.schemas.base import StrictModel


class ClaimMetadata(StrictModel):
    """Header fields regex-read from claim text; None where the pattern did not match."""

    claim_number: str | None = None
    period_from: str | None = None
    period_to: str | None = None
    payment_due: str | None = None


class ClaimSummary(StrictModel):
    """Claim totals recomputed from normalised line items, as 2dp strings."""

    original_contract_total: str
    revised_contract_total: str
    claimed_amount: str


class MoneyFormatWarning(StrictModel):
    """A persisted money cell create_records could not parse (decision D6); ref is None for summary cells."""

    ref: str | None
    field: str
    description: str
