"""Phase 2: Deterministic validation of contractor claim math."""
import json
import logging
import uuid
from collections import Counter
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.claim_parse_flag import FlagType, FlagSeverity
from app.repos import harness_repo, project_repo

logger = logging.getLogger(__name__)

TOLERANCE = Decimal("0.02")
ZERO = Decimal("0")
HUNDRED = Decimal("100")


def _dec(value: str | None) -> Decimal:
    """Safely parse a string to Decimal."""
    if not value:
        return ZERO
    try:
        return Decimal(str(value).replace(",", ""))
    except (InvalidOperation, ValueError):
        return ZERO


async def execute_validate_claim(
    db: AsyncSession,
    session_id: uuid.UUID,
    user_id: uuid.UUID,
    project_id: uuid.UUID,
    config: dict[str, Any],
) -> dict:
    """Run deterministic validation checks on parsed claim data."""
    raw = await harness_repo.read_workspace_file(db, session_id, "parsed_claim.json")
    if raw is None:
        raise ValueError("parsed_claim.json not found in workspace")

    parsed = json.loads(raw)
    line_items = parsed.get("line_items", [])
    summary = parsed.get("summary", {})

    flags_created = 0

    async def _flag(flag_type: FlagType, severity: FlagSeverity, description: str,
                    ref: str | None = None, expected: Decimal | None = None,
                    actual: Decimal | None = None) -> None:
        nonlocal flags_created
        await harness_repo.create_flag(
            db=db, session_id=session_id,
            flag_type=flag_type, severity=severity, description=description,
            line_item_ref=ref, expected_value=expected, actual_value=actual,
        )
        flags_created += 1

    # -- Per-item checks --
    for item in line_items:
        ref = item.get("ref_code", "")
        contract_value = _dec(item.get("contract_value"))
        percentage = _dec(item.get("percentage"))
        ptd = _dec(item.get("ptd"))

        # Percentage bounds
        if percentage < ZERO or percentage > HUNDRED:
            await _flag(
                FlagType.percentage_error, FlagSeverity.error,
                f"Percentage {percentage}% outside 0-100 range",
                ref=ref, expected=HUNDRED, actual=percentage,
            )

        # Over-claiming: PTD exceeds contract value
        if contract_value > ZERO and ptd > contract_value:
            await _flag(
                FlagType.over_claim, FlagSeverity.warning,
                f"PTD (${ptd:,.2f}) exceeds contract value (${contract_value:,.2f})",
                ref=ref, expected=contract_value, actual=ptd,
            )

        # Missing ref — not a data quality issue, ref_code is the
        # contractor's own reference and may not exist in all formats.

    # -- Duplicate ref check --
    refs = [item.get("ref_code", "") for item in line_items if item.get("ref_code")]
    ref_counts = Counter(refs)
    for ref, count in ref_counts.items():
        if count > 1:
            await _flag(
                FlagType.duplicate_item, FlagSeverity.warning,
                f"Ref code '{ref}' appears {count} times",
                ref=ref,
            )

    # -- Section total checks --
    cw_items = [i for i in line_items if i.get("item_type") == "contract_work"]
    var_items = [i for i in line_items if i.get("item_type") == "variation"]
    ps_items = [i for i in line_items if i.get("item_type") == "provisional_sum"]

    sum_cw = sum(_dec(i.get("contract_value")) for i in cw_items)
    sum_var = sum(_dec(i.get("contract_value")) for i in var_items)
    sum_ps = sum(_dec(i.get("contract_value")) for i in ps_items)

    orig_total = _dec(summary.get("original_contract_total"))

    # Provisional sums total mismatch against project-level PS total
    project = await project_repo.get_by_id(db, project_id)
    if project and project.provisional_sum_total and sum_ps > ZERO:
        ps_total = project.provisional_sum_total
        if abs(sum_ps - ps_total) > TOLERANCE:
            await _flag(
                FlagType.total_mismatch, FlagSeverity.warning,
                f"Provisional sums claimed (${sum_ps:,.2f}) do not match "
                f"project provisional sum total (${ps_total:,.2f})",
                expected=ps_total, actual=sum_ps,
            )

    # Project over budget: contract works + provisional sums + variations > original total
    revised_total = sum_cw + sum_ps + sum_var
    if orig_total > ZERO and revised_total > orig_total + TOLERANCE:
        await _flag(
            FlagType.project_over_budget, FlagSeverity.warning,
            f"Project over budget: works + provisional sums + variations "
            f"(${revised_total:,.2f}) exceeds original contract (${orig_total:,.2f})",
            expected=orig_total, actual=revised_total,
        )

    # Total claimed exceeds revised contract total (all current + historic claims)
    sum_claimed_ptd = sum(_dec(i.get("ptd")) for i in line_items)
    revised_contract = _dec(summary.get("revised_contract_total"))
    if revised_contract > ZERO and sum_claimed_ptd > revised_contract + TOLERANCE:
        await _flag(
            FlagType.over_claim, FlagSeverity.warning,
            f"Total claimed to date (${sum_claimed_ptd:,.2f}) exceeds "
            f"revised contract total (${revised_contract:,.2f})",
            expected=revised_contract, actual=sum_claimed_ptd,
        )

    logger.info(
        "Validation complete: %d items checked, %d flags created",
        len(line_items), flags_created,
    )

    return {
        "total_items": len(line_items),
        "flags_created": flags_created,
    }
