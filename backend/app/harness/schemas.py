"""Structured-output schemas for LLM harness phases.

These models are the ``output_type`` of the pydantic-ai agents. They are
validated by pydantic-ai on every call and serialized to the workspace files
that downstream programmatic phases (``create_records``) consume.

Field sets mirror exactly what ``create_records`` reads, so the workspace-file
contract is unchanged — only now it is typed and validated at the source.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

_Confidence = Annotated[float, Field(ge=0.0, le=1.0)]
_ItemIndex = Annotated[int, Field(ge=0)]

# Decimal-ish fields arrive as strings ("$1,234.56", "(500.00)") or numbers;
# downstream normalisation (`validate_and_normalise`) handles the conversion.
_Numeric = str | float | int | None


class ParsedClaimItem(BaseModel):
    """A single line item as stored in ``parsed_claim.json`` and read by the
    matchers. Only the fields matchers consume are declared; any other keys the
    extraction wrote (``ref_code``, ``percentage``, ``ptd``, …) are ignored.

    ``contract_value`` keeps its raw extracted form (it is forwarded verbatim to
    the Jev decisions API and never used arithmetically here).
    """

    model_config = ConfigDict(extra="ignore")

    item_index: _ItemIndex
    description: str = ""
    item_type: str = "contract_work"
    contract_value: _Numeric = None


class JevAnswer(BaseModel):
    """One answer within a Jev decisions response (``answers[question_id]``)."""

    model_config = ConfigDict(extra="ignore")

    choice: str | None = None
    confidence: float = 0.0


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

    item_index: _ItemIndex
    wbs_code_id: str | None = None
    wbs_code: str
    wbs_description: str = ""
    parent_code: str = ""
    is_new: bool = False
    # Required and range-checked: an omitted confidence must not silently read as 0.0.
    confidence: _Confidence


class VpsMatch(BaseModel):
    """One variation / provisional-sum match. Serialized list -> ``vps_matches.json``."""

    item_index: _ItemIndex
    item_type: Literal["variation", "provisional_sum"]
    matched_id: str | None = None
    confidence: _Confidence


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
    item_type: str = "contract_work"
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
