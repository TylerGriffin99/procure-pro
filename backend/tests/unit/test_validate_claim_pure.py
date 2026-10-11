from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.constants.enums import FlagSeverity, FlagType
from app.harness.executors.validate_claim import collect_flags
from app.harness.schemas import FlagSpec, ParsedClaim


def item(index, ref="1001", item_type="contract_work", value="100000.00", pct="50.00", ptd="50000.00"):
    return {
        "item_index": index,
        "ref_code": ref,
        "description": "Excavation",
        "item_type": item_type,
        "contract_value": value,
        "percentage": pct,
        "ptd": ptd,
    }


def parsed(items, original="100000.00", revised="100000.00"):
    return ParsedClaim.model_validate(
        {"line_items": items, "summary": {"original_contract_total": original, "revised_contract_total": revised}}
    )


NO_PROJECT = None


def kinds(flags: list[FlagSpec]) -> list[FlagType]:
    return [f.flag_type for f in flags]


@pytest.mark.parametrize(
    ("claim", "project", "expected"),
    [
        (parsed([item(0)]), NO_PROJECT, []),
        (
            parsed([item(0, pct="120.00", ptd="120000.00")], revised="200000.00"),
            NO_PROJECT,
            [FlagType.percentage_error, FlagType.over_claim],
        ),
        (
            parsed([item(0), item(1, ref="V001", item_type="variation", value="25000.00", pct="0", ptd="0")]),
            NO_PROJECT,
            [FlagType.project_over_budget],
        ),
        (
            parsed([item(0, value="50000.00", ptd="0"), item(1, value="50000.00", ptd="0")]),
            NO_PROJECT,
            [FlagType.duplicate_item],
        ),
        (parsed([item(0, ref="", value="50000.00", pct="40.00", ptd="20000.00")], "0", "0"), NO_PROJECT, []),
        (
            parsed([item(0, item_type="provisional_sum", value="5000.00", ptd="0")]),
            SimpleNamespace(provisional_sum_total=Decimal("9000.00")),
            [FlagType.total_mismatch],
        ),
        (
            parsed([item(0, item_type="provisional_sum", value="5000.00", ptd="0")]),
            SimpleNamespace(provisional_sum_total=Decimal("5000.01")),
            [],
        ),
        (parsed([item(0, ptd="90000.00")], revised="80000.00"), NO_PROJECT, [FlagType.over_claim]),
    ],
    ids=["clean", "pct-and-ptd", "over-budget", "duplicate-ref", "missing-ref-silent", "ps-mismatch", "ps-ok", "ptd"],
)
def test_collect_flags_table(claim, project, expected):
    assert kinds(collect_flags(claim, project)) == expected


def test_collect_flags_carries_values_and_ref():
    [pct, over] = collect_flags(parsed([item(0, pct="120.00", ptd="120000.00")], revised="200000.00"), NO_PROJECT)
    assert pct == FlagSpec(
        flag_type=FlagType.percentage_error,
        severity=FlagSeverity.error,
        description="Percentage 120.00% outside 0-100 range",
        line_item_ref="1001",
        expected_value=Decimal("100"),
        actual_value=Decimal("120.00"),
    )
    assert over.description == "PTD ($120,000.00) exceeds contract value ($100,000.00)"
    assert (over.expected_value, over.actual_value) == (Decimal("100000.00"), Decimal("120000.00"))
