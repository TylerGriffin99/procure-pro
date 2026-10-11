"""Structured-output schemas for LLM harness phases.

These models are the ``output_type`` of the pydantic-ai agents. They are
validated by pydantic-ai on every call and serialized to the workspace files
that downstream programmatic phases (``create_records``) consume.

Field sets mirror exactly what ``create_records`` reads, so the workspace-file
contract is unchanged — only now it is typed and validated at the source.
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.constants.enums import ClaimFormat, ClaimItemType, FlagSeverity, FlagType, MatcherName, VpsKind
from app.schemas.assessment_aggregate import AssessmentAggregate
from app.schemas.base import StrictModel
from app.schemas.claim_extraction import ClaimMetadata, DroppedRow, MoneyFormatWarning
from app.schemas.common import Confidence, ItemIndex

# Decimal-ish fields arrive as strings ("$1,234.56", "(500.00)") or numbers;
# downstream normalisation (`validate_and_normalise`) handles the conversion.
_Numeric = str | float | int | None


class ParsedClaimItem(BaseModel):
    """Money fields keep their raw extracted form: ``contract_value`` is forwarded verbatim to the Jev
    decisions API, and ``parse_money`` converts at the point of use."""

    model_config = ConfigDict(extra="ignore")

    item_index: ItemIndex
    ref_code: str = ""
    description: str = ""
    item_type: ClaimItemType = ClaimItemType.contract_work
    contract_value: _Numeric = None
    percentage: _Numeric = None
    ptd: _Numeric = None
    previous: _Numeric = None
    current: _Numeric = None
    balance: _Numeric = None


class ParsedClaimMetadata(BaseModel):
    model_config = ConfigDict(extra="ignore")

    claim_number: str = ""
    period_from: str = ""
    period_to: str = ""
    payment_due: str = ""


class ParsedClaimSummary(BaseModel):
    model_config = ConfigDict(extra="ignore")

    original_contract_total: _Numeric = None
    variations_total: _Numeric = None
    revised_contract_total: _Numeric = None
    retention_amount: _Numeric = None
    claimed_amount: _Numeric = None


class ParsedClaim(BaseModel):
    model_config = ConfigDict(extra="ignore")

    metadata: ParsedClaimMetadata = Field(default_factory=ParsedClaimMetadata)
    line_items: list[ParsedClaimItem]
    summary: ParsedClaimSummary = Field(default_factory=ParsedClaimSummary)
    # Malformed cells seen before the extractor normalised them to "0.00"; create_records flags each one.
    format_warnings: list[MoneyFormatWarning] = Field(default_factory=list)
    # Table rows the deterministic parser could not map (wrong column count); each one understates the claim.
    dropped_rows: list[DroppedRow] = Field(default_factory=list)


class RawPage(StrictModel):
    page_num: int
    text: str = ""
    tables: list[list[list[str | None]]] = Field(default_factory=list)


class RawExtraction(StrictModel):
    metadata: ClaimMetadata = Field(default_factory=ClaimMetadata)
    pages: list[RawPage] = Field(default_factory=list)

    def all_text(self) -> str:
        return "\n".join(p.text for p in self.pages)


class FormatDetection(StrictModel):
    format: ClaimFormat
    confidence: float
    markers_found: list[str]

    def detail(self) -> str:
        percent = f" ({int(self.confidence * 100)}%)" if self.confidence else ""
        return f"Format: {self.format.upper()}{percent}"


class ValidationSummary(StrictModel):
    total_items: int
    flags_created: int


class CreationSummary(StrictModel):
    claim_id: uuid.UUID
    assessment_id: uuid.UUID
    line_items_created: int


class FlagSpec(StrictModel):
    flag_type: FlagType
    severity: FlagSeverity
    description: str
    line_item_ref: str | None = None
    expected_value: Decimal | None = None
    actual_value: Decimal | None = None


class CreateRecordsInputs(StrictModel):
    parsed: ParsedClaim
    wbs_matches: list[WbsMatch]
    vps_matches: list[VpsMatch]


class VpsLinks(StrictModel):
    variations: dict[int, uuid.UUID]
    provisional_sums: dict[int, uuid.UUID]


class ClaimLinks(StrictModel):
    wbs: dict[int, uuid.UUID]
    vps: VpsLinks
    confidence: dict[int, Decimal]


class MasterRef(StrictModel):
    id: uuid.UUID
    denominator: Decimal | None
    description: str | None = None
    sort_order: int | None = None


class KindHistory(StrictModel):
    recommended: dict[uuid.UUID, Decimal]
    claimed: dict[uuid.UUID, Decimal]
    comments: dict[uuid.UUID, str]
    accepted: dict[uuid.UUID, Decimal]


class HistorySource(StrictModel):
    model_config = ConfigDict(extra="forbid", frozen=True, arbitrary_types_allowed=True)

    claim_lines: list[Any]
    previous: AssessmentAggregate | None
    latest: Any
    wbs_codes: list[Any]
    variations: list[Any]
    provisional_sums: list[Any]
    user_id: uuid.UUID


ExecutorResult = RawExtraction | FormatDetection | ParsedClaim | ValidationSummary | CreationSummary


class JevAnswer(BaseModel):
    """One answer within a Jev decisions response (``answers[question_id]``)."""

    model_config = ConfigDict(extra="ignore")

    choice: str
    confidence: Confidence


class JevUsage(BaseModel):
    model_config = ConfigDict(extra="ignore")

    input_tokens: int = 0


class JevDecisionResponse(BaseModel):
    """The decisions-endpoint response body for a single Jev call."""

    model_config = ConfigDict(extra="ignore")

    answers: dict[str, JevAnswer] = Field(default_factory=dict)
    usage: JevUsage = Field(default_factory=JevUsage)


class WbsMatch(BaseModel):
    """One WBS categorisation match for a contract-work line item.

    Serialized list -> ``wbs_matches.json``.
    """

    item_index: ItemIndex
    wbs_code_id: str | None = None
    wbs_code: str
    wbs_description: str = ""
    parent_code: str = ""
    is_new: bool = False
    # Required and range-checked: an omitted confidence must not silently read as 0.0.
    confidence: Confidence


class VpsMatch(BaseModel):
    """One variation / provisional-sum match. Serialized list -> ``vps_matches.json``."""

    item_index: ItemIndex
    item_type: VpsKind
    matched_id: str | None = None
    confidence: Confidence


class Subcat(StrictModel):
    """A WBS subcategory offered to the matcher as a choice."""

    id: str
    code: str
    description: str
    parent_code: str
    contract_sum: float | None


class VpsRecord(StrictModel):
    """An existing variation / provisional-sum record offered to the matcher as a choice."""

    id: str
    description: str
    value: float | None
    item_type: VpsKind


class JevTuning(StrictModel):
    confidence_floor: float
    max_concurrency: int


class ItemDecision(StrictModel):
    """One Jev answer for one line item. ``error`` is the non-fatal failure that left the item
    unmatched; it is kept so an all-failed phase can report and chain it."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    item_index: ItemIndex
    choice: str | None = None
    confidence: Confidence = 0.0
    input_tokens: int = 0
    error: Exception | None = Field(default=None, exclude=True)

    @property
    def failed(self) -> bool:
        return self.error is not None


class MatchOutcome(StrictModel):
    """Result of a matcher run: the typed list, its serialized form, and usage counters."""

    matcher: MatcherName
    output: list[Any]  # list[WbsMatch] or list[VpsMatch]
    output_json: str  # bare JSON array matching the phase output_schema
    input_tokens: int = 0
    output_tokens: int = 0
    fell_back: int = 0  # items that fell back after a Jev failure
    residue: int = 0  # items routed to the LLM (none / low confidence)
    out_of_criteria: int = 0  # the model named an option that was never offered


class GenericMetadata(BaseModel):
    claim_number: str = ""
    period_from: str = ""
    period_to: str = ""
    payment_due: str = ""


class GenericLineItem(BaseModel):
    ref_code: str = ""
    description: str = ""
    # Kept as a plain string (not Literal) so a stray type does not fail the whole
    # extraction — `validate_and_normalise` coerces unknown types to contract_work.
    item_type: str = ClaimItemType.contract_work
    contract_value: _Numeric = None
    percentage: _Numeric = None
    ptd: _Numeric = None
    previous: _Numeric = None
    current: _Numeric = None
    balance: _Numeric = None


class GenericSummary(BaseModel):
    original_contract_total: _Numeric = None
    revised_contract_total: _Numeric = None
    claimed_amount: _Numeric = None


class GenericExtraction(BaseModel):
    """Full generic-format claim extraction. Normalised, then -> ``parsed_claim.json``."""

    metadata: GenericMetadata = Field(default_factory=GenericMetadata)
    line_items: list[GenericLineItem]
    summary: GenericSummary = Field(default_factory=GenericSummary)
