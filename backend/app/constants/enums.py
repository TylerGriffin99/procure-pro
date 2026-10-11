from enum import StrEnum
from typing import Literal


class ClaimItemType(StrEnum):
    contract_work = "contract_work"
    variation = "variation"
    provisional_sum = "provisional_sum"


# Pydantic/Literal view of the two VPS members of ClaimItemType; kept equal by tests/unit/test_constants.py.
VpsKind = Literal["variation", "provisional_sum"]


class AssessmentItemKind(StrEnum):
    line_item = "line-item"
    variation = "variation"
    provisional_sum = "provisional-sum"


class AssessmentStatus(StrEnum):
    draft = "draft"
    finalised = "finalised"


class LineItemStatus(StrEnum):
    unapproved = "unapproved"
    approved = "approved"
    interim = "interim"


class AdjustmentType(StrEnum):
    interim_adjustment = "interim_adjustment"


class FlagType(StrEnum):
    total_mismatch = "total_mismatch"  # kept for DB compat with existing rows
    project_over_budget = "project_over_budget"
    over_claim = "over_claim"
    percentage_error = "percentage_error"
    ptd_decrease = "ptd_decrease"
    missing_ref = "missing_ref"
    duplicate_item = "duplicate_item"
    format_warning = "format_warning"
    confidence_low = "confidence_low"


class FlagSeverity(StrEnum):
    error = "error"
    warning = "warning"
    info = "info"


class HarnessSessionStatus(StrEnum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"


class PhaseStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class VariationStatus(StrEnum):
    unapproved = "unapproved"
    in_review = "in_review"
    approved = "approved"


class WBSLevel(StrEnum):
    category = "category"
    subcategory = "subcategory"


class UserRole(StrEnum):
    user = "user"
    admin = "admin"


class Country(StrEnum):
    NZ = "NZ"
    AU = "AU"


class MatcherName(StrEnum):
    llm = "llm"
    jev = "jev"


class LlmProvider(StrEnum):
    anthropic = "anthropic"
    openai = "openai"
    openrouter = "openrouter"
    deepseek = "deepseek"


class ClaimFormat(StrEnum):
    wbpro = "wbpro"
    generic = "generic"


class WorkspaceFile(StrEnum):
    raw_extraction = "raw_extraction.json"
    format_detection = "format_detection.json"
    parsed_claim = "parsed_claim.json"
    validation_summary = "validation_summary.json"
    wbs_matches = "wbs_matches.json"
    vps_matches = "vps_matches.json"
    creation_summary = "creation_summary.json"


class ExportFormat(StrEnum):
    pdf = "pdf"
    excel = "excel"


class ViolationCategory(StrEnum):
    prompt_injection = "prompt_injection"
    code = "code"
