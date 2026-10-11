import re
from collections.abc import Sequence
from decimal import Decimal
from typing import Final

from app.constants.enums import ClaimItemType
from app.harness.schemas import ParsedClaimItem, ParsedClaimSummary
from app.schemas.claim_extraction import ClaimMetadata
from app.utils.money import format_money

# "Claim No." and "Claim Number" are both in the wild; the other fields have one spelling each.
_METADATA_PATTERNS: Final = {
    "claim_number": re.compile(r"Claim\s*(?:No\.?|Number)\s*[:\-]?\s*(\d+)", re.IGNORECASE),
    "period_from": re.compile(r"Period\s*From\s*[:\-]?\s*([\d/]+)", re.IGNORECASE),
    "period_to": re.compile(r"Period\s*To\s*[:\-]?\s*([\d/]+)", re.IGNORECASE),
    "payment_due": re.compile(r"Payment\s*Due\s*[:\-]?\s*([\d/]+)", re.IGNORECASE),
}


def extract_metadata(text: str) -> ClaimMetadata:
    found = {key: match.group(1) for key, pattern in _METADATA_PATTERNS.items() if (match := pattern.search(text))}
    return ClaimMetadata(**found)


def summary_totals(items: Sequence[ParsedClaimItem]) -> ParsedClaimSummary:
    # Items must already carry normalised decimal strings in contract_value and ptd.
    contract_total = Decimal("0")
    revised_total = Decimal("0")
    claimed_total = Decimal("0")
    for item in items:
        val = Decimal(str(item.contract_value))
        revised_total += val
        if item.item_type == ClaimItemType.contract_work:
            contract_total += val
        claimed_total += Decimal(str(item.ptd))
    return ParsedClaimSummary(
        original_contract_total=format_money(contract_total),
        revised_contract_total=format_money(revised_total),
        claimed_amount=format_money(claimed_total),
    )
