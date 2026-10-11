import uuid
from decimal import Decimal

import pytest

from app.constants.enums import ClaimItemType
from app.harness.executors.create_records.claim import claim_line_values, parse_claim_number, parse_warning_flags
from app.harness.schemas import ClaimLinks, ParsedClaim, ParsedClaimItem, ParsedClaimMetadata, VpsLinks

USER = uuid.uuid4()


def test_claim_line_values_parses_money_and_attaches_links():
    wbs_id, ps_id = uuid.uuid4(), uuid.uuid4()
    links = ClaimLinks(
        wbs={0: wbs_id}, vps=VpsLinks(variations={}, provisional_sums={1: ps_id}), confidence={0: Decimal("0.9")}
    )
    cw = ParsedClaimItem(item_index=0, ref_code="1.1", description="Dig", contract_value="1,000.00", current="(5)")
    ps = ParsedClaimItem(item_index=1, item_type=ClaimItemType.provisional_sum, contract_value="bad")

    first = claim_line_values(0, cw, links, USER)
    second = claim_line_values(1, ps, links, USER)

    assert (first.contract_value, first.current, first.balance) == (Decimal("1000.00"), Decimal("-5"), Decimal("0"))
    assert (first.suggested_wbs_code_id, first.categorisation_confidence, first.sort_order) == (
        wbs_id,
        Decimal("0.9"),
        0,
    )
    assert (second.provisional_sum_id, second.contract_value, second.categorisation_confidence) == (
        ps_id,
        Decimal("0"),
        Decimal("0"),
    )


def metadata_flags(**metadata: str) -> list[tuple[str, str | None]]:
    parsed = ParsedClaim(
        metadata=ParsedClaimMetadata(**metadata),
        line_items=[ParsedClaimItem(item_index=0, ref_code="1", contract_value="1.00")],
    )
    return [(flag.description, flag.line_item_ref) for flag in parse_warning_flags(parsed)]


def test_present_but_unparseable_dates_are_flagged():
    assert metadata_flags(claim_number="3", period_from="31/13/2024", period_to="", payment_due="2025-01-20") == [
        ("period_from: unparseable date '31/13/2024'; recorded as blank", None),
        ("payment_due: unparseable date '2025-01-20'; recorded as blank", None),
    ]


@pytest.mark.parametrize("raw", ["", "abc", "3a"])
def test_missing_or_unparseable_claim_number_is_flagged(raw):
    assert metadata_flags(claim_number=raw) == [(f"claim_number {raw!r} missing or unparseable; recorded as 0", None)]


def test_clean_metadata_raises_no_flags():
    assert metadata_flags(claim_number=" 7 ", period_from="01/01/25", period_to="31/01/25", payment_due="") == []


@pytest.mark.parametrize(("raw", "expected"), [("7", 7), (" 12 ", 12), ("", None), ("abc", None)])
def test_parse_claim_number(raw, expected):
    assert parse_claim_number(raw) == expected
