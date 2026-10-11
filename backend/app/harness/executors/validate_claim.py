"""Phase 2: Deterministic validation of contractor claim math."""

import logging
import uuid
from collections import Counter
from collections.abc import Sequence
from decimal import Decimal
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.llm_client import LlmClient
from app.constants.enums import ClaimItemType, FlagSeverity, FlagType, WorkspaceFile
from app.harness.phase_context import load_workspace
from app.harness.schemas import FlagSpec, ParsedClaim, ParsedClaimItem, ValidationSummary
from app.models.project import Project
from app.repos import harness_repo, project_repo
from app.utils.money import parse_money

logger = logging.getLogger(__name__)

TOLERANCE = Decimal("0.02")
ZERO = Decimal("0")
HUNDRED = Decimal("100")


def item_flags(item: ParsedClaimItem) -> list[FlagSpec]:
    contract_value = parse_money(item.contract_value).value
    percentage = parse_money(item.percentage).value
    ptd = parse_money(item.ptd).value
    flags = []
    if percentage < ZERO or percentage > HUNDRED:
        flags.append(
            FlagSpec(
                flag_type=FlagType.percentage_error,
                severity=FlagSeverity.error,
                description=f"Percentage {percentage}% outside 0-100 range",
                line_item_ref=item.ref_code,
                expected_value=HUNDRED,
                actual_value=percentage,
            )
        )
    if contract_value > ZERO and ptd > contract_value:
        flags.append(
            FlagSpec(
                flag_type=FlagType.over_claim,
                severity=FlagSeverity.warning,
                description=f"PTD (${ptd:,.2f}) exceeds contract value (${contract_value:,.2f})",
                line_item_ref=item.ref_code,
                expected_value=contract_value,
                actual_value=ptd,
            )
        )
    return flags


def duplicate_ref_flags(items: Sequence[ParsedClaimItem]) -> list[FlagSpec]:
    ref_counts = Counter(item.ref_code for item in items if item.ref_code)
    return [
        FlagSpec(
            flag_type=FlagType.duplicate_item,
            severity=FlagSeverity.warning,
            description=f"Ref code '{ref}' appears {count} times",
            line_item_ref=ref,
        )
        for ref, count in ref_counts.items()
        if count > 1
    ]


def section_total(items: Sequence[ParsedClaimItem], item_type: ClaimItemType) -> Decimal:
    return sum((parse_money(i.contract_value).value for i in items if i.item_type == item_type), ZERO)


def provisional_sum_flags(items: Sequence[ParsedClaimItem], project: Project | None) -> list[FlagSpec]:
    sum_ps = section_total(items, ClaimItemType.provisional_sum)
    if not (project and project.provisional_sum_total and sum_ps > ZERO):
        return []
    ps_total = project.provisional_sum_total
    if abs(sum_ps - ps_total) <= TOLERANCE:
        return []
    return [
        FlagSpec(
            flag_type=FlagType.total_mismatch,
            severity=FlagSeverity.warning,
            description=f"Provisional sums claimed (${sum_ps:,.2f}) do not match "
            f"project provisional sum total (${ps_total:,.2f})",
            expected_value=ps_total,
            actual_value=sum_ps,
        )
    ]


def budget_flags(parsed: ParsedClaim) -> list[FlagSpec]:
    items = parsed.line_items
    revised_total = sum((section_total(items, kind) for kind in ClaimItemType), ZERO)
    orig_total = parse_money(parsed.summary.original_contract_total).value
    flags = []
    if orig_total > ZERO and revised_total > orig_total + TOLERANCE:
        flags.append(
            FlagSpec(
                flag_type=FlagType.project_over_budget,
                severity=FlagSeverity.warning,
                description=f"Project over budget: works + provisional sums + variations "
                f"(${revised_total:,.2f}) exceeds original contract (${orig_total:,.2f})",
                expected_value=orig_total,
                actual_value=revised_total,
            )
        )
    sum_claimed_ptd = sum((parse_money(i.ptd).value for i in items), ZERO)
    revised_contract = parse_money(parsed.summary.revised_contract_total).value
    if revised_contract > ZERO and sum_claimed_ptd > revised_contract + TOLERANCE:
        flags.append(
            FlagSpec(
                flag_type=FlagType.over_claim,
                severity=FlagSeverity.warning,
                description=f"Total claimed to date (${sum_claimed_ptd:,.2f}) exceeds "
                f"revised contract total (${revised_contract:,.2f})",
                expected_value=revised_contract,
                actual_value=sum_claimed_ptd,
            )
        )
    return flags


def collect_flags(parsed: ParsedClaim, project: Project | None) -> list[FlagSpec]:
    per_item = [flag for item in parsed.line_items for flag in item_flags(item)]
    return (
        per_item
        + duplicate_ref_flags(parsed.line_items)
        + provisional_sum_flags(parsed.line_items, project)
        + budget_flags(parsed)
    )


async def execute_validate_claim(
    *,
    db: AsyncSession,
    session_id: uuid.UUID,
    user_id: uuid.UUID,
    project_id: uuid.UUID,
    config: dict[str, Any],
    llm: LlmClient,
) -> ValidationSummary:
    parsed = await load_workspace(db, session_id, WorkspaceFile.parsed_claim, ParsedClaim.model_validate_json)
    project = await project_repo.get_by_id(db, project_id)

    flags = collect_flags(parsed, project)
    for spec in flags:
        await harness_repo.create_flag(db, session_id, spec)

    logger.info("Validation complete: %d items checked, %d flags created", len(parsed.line_items), len(flags))
    return ValidationSummary(total_items=len(parsed.line_items), flags_created=len(flags))
