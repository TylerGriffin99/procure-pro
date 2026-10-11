from decimal import Decimal
from enum import StrEnum
from typing import get_args

import pytest

from app.constants import (
    CENTS,
    CURRENCY_BY_COUNTRY,
    AdjustmentType,
    AssessmentItemKind,
    AssessmentStatus,
    ClaimFormat,
    ClaimItemType,
    Country,
    ExportFormat,
    FlagSeverity,
    FlagType,
    HarnessSessionStatus,
    LineItemStatus,
    LlmProvider,
    MatcherName,
    PhaseStatus,
    UserRole,
    VariationStatus,
    ViolationCategory,
    VpsKind,
    WBSLevel,
    WorkspaceFile,
)

ALL_ENUMS: list[type[StrEnum]] = [
    AdjustmentType,
    AssessmentItemKind,
    AssessmentStatus,
    ClaimFormat,
    ClaimItemType,
    Country,
    ExportFormat,
    FlagSeverity,
    FlagType,
    HarnessSessionStatus,
    LineItemStatus,
    LlmProvider,
    MatcherName,
    PhaseStatus,
    UserRole,
    VariationStatus,
    ViolationCategory,
    WBSLevel,
    WorkspaceFile,
]

MEMBERS = [member for enum_cls in ALL_ENUMS for member in enum_cls]


@pytest.mark.parametrize("member", MEMBERS, ids=lambda m: f"{type(m).__name__}.{m.name}")
def test_enum_round_trips_its_value(member: StrEnum) -> None:
    assert type(member)(member.value) is member


@pytest.mark.parametrize("member", MEMBERS, ids=lambda m: f"{type(m).__name__}.{m.name}")
def test_str_and_format_of_member_is_its_value(member: StrEnum) -> None:
    assert str(member) == member.value
    assert f"{member}" == member.value


def test_wire_values_are_unchanged() -> None:
    assert {k.value for k in ClaimItemType} == {"contract_work", "variation", "provisional_sum"}
    assert {k.value for k in AssessmentItemKind} == {"line-item", "variation", "provisional-sum"}
    assert {s.value for s in AssessmentStatus} == {"draft", "finalised"}
    assert {s.value for s in LineItemStatus} == {"unapproved", "approved", "interim"}
    assert {s.value for s in WBSLevel} == {"category", "subcategory"}
    assert {s.value for s in HarnessSessionStatus} == {"pending", "running", "completed", "failed"}
    assert {p.value for p in LlmProvider} == {"anthropic", "openai", "openrouter", "deepseek"}
    assert {m.value for m in MatcherName} == {"llm", "jev"}
    assert {c.value for c in Country} == {"NZ", "AU"}
    assert {f.value for f in FlagType} == {
        "total_mismatch",
        "project_over_budget",
        "over_claim",
        "percentage_error",
        "ptd_decrease",
        "missing_ref",
        "duplicate_item",
        "format_warning",
        "confidence_low",
    }
    assert {f.value for f in FlagSeverity} == {"error", "warning", "info"}
    assert {s.value for s in VariationStatus} == {"unapproved", "in_review", "approved"}
    assert {r.value for r in UserRole} == {"user", "admin"}
    assert {a.value for a in AdjustmentType} == {"interim_adjustment"}
    assert {p.value for p in PhaseStatus} == {"pending", "running", "completed", "failed"}
    assert {w.value for w in WorkspaceFile} == {
        "raw_extraction.json",
        "format_detection.json",
        "parsed_claim.json",
        "validation_summary.json",
        "wbs_matches.json",
        "vps_matches.json",
        "creation_summary.json",
    }
    assert {e.value for e in ExportFormat} == {"pdf", "excel"}
    assert {v.value for v in ViolationCategory} == {"prompt_injection", "code"}
    assert {f.value for f in ClaimFormat} == {"wbpro", "generic"}


def test_vps_kind_literal_matches_claim_item_type_members() -> None:
    assert set(get_args(VpsKind)) == {ClaimItemType.variation.value, ClaimItemType.provisional_sum.value}


def test_currency_by_country_covers_every_country() -> None:
    assert CURRENCY_BY_COUNTRY == {Country.NZ: "NZD", Country.AU: "AUD"}


def test_cents_is_two_decimal_places() -> None:
    assert Decimal("1.005").quantize(CENTS) == Decimal("1.00")
    assert CENTS == Decimal("0.01")
