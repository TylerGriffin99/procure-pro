"""Deterministic validation checks on parsed claim data."""

import uuid
from dataclasses import dataclass, field
from decimal import Decimal

from app.utils.pdf_parser import ParsedClaim, ParsedLineItem

TOLERANCE = Decimal("0.02")
ZERO = Decimal("0")
HUNDRED = Decimal("100")


@dataclass
class ValidationResult:
    claim_warnings: list[str] = field(default_factory=list)
    item_warnings: dict[str, list[str]] = field(default_factory=dict)


def _item_key(item: ParsedLineItem) -> str:
    return item.ref_code if item.ref_code else item.description


def _validate_line_item(item: ParsedLineItem) -> list[str]:
    warnings: list[str] = []

    if item.percentage < ZERO or item.percentage > HUNDRED:
        warnings.append(f"Percentage {item.percentage}% is outside expected 0-100% range")

    if item.current > ZERO and item.contract_value > ZERO and item.current > item.contract_value:
        warnings.append(
            f"Current claim (${item.current:,.2f}) exceeds "
            f"contract value (${item.contract_value:,.2f})"
        )

    if item.ptd > ZERO and item.contract_value > ZERO and item.ptd > item.contract_value:
        warnings.append(
            f"Paid to date (${item.ptd:,.2f}) exceeds contract value (${item.contract_value:,.2f})"
        )

    if item.contract_value < ZERO:
        warnings.append(f"Negative contract value (${item.contract_value:,.2f})")

    all_zero = all(
        getattr(item, f) == ZERO
        for f in ("contract_value", "percentage", "ptd", "previous", "current", "balance")
    )
    if all_zero:
        warnings.append("All values are zero — possible parsing artifact")

    return warnings


def _validate_claim_totals(parsed: ParsedClaim) -> list[str]:
    warnings: list[str] = []

    if not parsed.line_items:
        warnings.append("No line items extracted from PDF")
        return warnings

    sum_cw = sum(i.contract_value for i in parsed.line_items if i.item_type == "contract_work")
    sum_var = sum(i.contract_value for i in parsed.line_items if i.item_type == "variation")

    orig = parsed.summary.original_contract_total
    if orig and abs(sum_cw - orig) > TOLERANCE:
        diff = sum_cw - orig
        warnings.append(
            f"Contract work items sum to ${sum_cw:,.2f} but reported total is ${orig:,.2f} "
            f"(difference: ${diff:,.2f})"
        )

    var_total = parsed.summary.variations_total
    if var_total and abs(sum_var - var_total) > TOLERANCE:
        diff = sum_var - var_total
        warnings.append(
            f"Variation items sum to ${sum_var:,.2f} but reported total is ${var_total:,.2f} "
            f"(difference: ${diff:,.2f})"
        )

    revised = parsed.summary.revised_contract_total
    if revised and orig:
        expected_revised = orig + (var_total or ZERO)
        if abs(revised - expected_revised) > TOLERANCE:
            warnings.append(
                f"revised_contract_total (${revised:,.2f}) != original (${orig:,.2f}) "
                f"+ variations (${var_total or ZERO:,.2f})"
            )

    return warnings


def validate_parsed_claim(parsed: ParsedClaim) -> ValidationResult:
    result = ValidationResult()
    result.claim_warnings = _validate_claim_totals(parsed)

    for item in parsed.line_items:
        item_warns = _validate_line_item(item)
        if item_warns:
            result.item_warnings[_item_key(item)] = item_warns

    return result


def validate_provisional_sum_discrepancies(
    claim_items: list,
    project_ps_total: Decimal | None,
    provisional_sums: list,
) -> ValidationResult:
    """Compare contractor-submitted PS values against project allocations."""
    result = ValidationResult()
    ps_lookup = {ps.id: ps for ps in provisional_sums}

    # Filter to PS items only
    ps_items = [i for i in claim_items if i.item_type == "provisional_sum"]

    # ── Per-PS group check ──
    groups: dict[uuid.UUID, list] = {}
    for item in ps_items:
        if item.provisional_sum_id:
            groups.setdefault(item.provisional_sum_id, []).append(item)
        else:
            key = item.ref_code or item.description
            result.item_warnings.setdefault(key, []).append(
                "Provisional sum not found in project records"
            )

    for ps_id, items in groups.items():
        ps_record = ps_lookup.get(ps_id)
        if not ps_record:
            continue

        group_total = sum(i.contract_value for i in items)
        if group_total > ps_record.contract_sum:
            for item in items:
                key = item.ref_code or item.description
                result.item_warnings.setdefault(key, []).append(
                    f"Provisional sum group total (${group_total:,.2f}) exceeds "
                    f"allocated contract sum (${ps_record.contract_sum:,.2f})"
                )

    # ── Aggregate ceiling check ──
    if project_ps_total is not None:
        total_claimed = sum(i.contract_value for i in ps_items)
        if total_claimed > project_ps_total:
            result.claim_warnings.append(
                f"Total provisional sums claimed (${total_claimed:,.2f}) "
                f"exceed project allocation (${project_ps_total:,.2f})"
            )

    return result


def validate_variation_status_warnings(
    claim_items: list,
    variations: list,
) -> ValidationResult:
    """Flag claim items that reference unapproved variations."""
    result = ValidationResult()
    var_lookup = {v.id: v for v in variations}

    for item in claim_items:
        if item.item_type != "variation" or not item.variation_id:
            continue

        variation = var_lookup.get(item.variation_id)
        if variation and variation.status == "unapproved":
            key = item.ref_code or item.description
            result.item_warnings.setdefault(key, []).append(
                "Variation is unapproved — contractor submission subject to review"
            )

    return result
