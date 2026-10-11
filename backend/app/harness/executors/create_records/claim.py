import logging
import uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Final

from sqlalchemy.ext.asyncio import AsyncSession

from app.constants.enums import FlagSeverity, FlagType
from app.harness.schemas import ClaimLinks, FlagSpec, ParsedClaim, ParsedClaimItem, ParsedClaimSummary
from app.models.claim import Claim
from app.repos import claim_repo, harness_repo
from app.schemas.claim_extraction import ClaimLineValues, MoneyFormatWarning
from app.utils.dates import parse_ddmmyy
from app.utils.money import parse_money

logger = logging.getLogger(__name__)

ITEM_MONEY_FIELDS: Final = ("contract_value", "percentage", "ptd", "previous", "current", "balance")
SUMMARY_MONEY_FIELDS: Final = (
    "original_contract_total",
    "variations_total",
    "revised_contract_total",
    "retention_amount",
    "claimed_amount",
)


def money_format_warnings(
    line_items: Sequence[ParsedClaimItem], summary: ParsedClaimSummary
) -> list[MoneyFormatWarning]:
    cells: list[tuple[str | None, str, Any]] = [
        (item.ref_code, field, getattr(item, field)) for item in line_items for field in ITEM_MONEY_FIELDS
    ]
    cells += [(None, field, getattr(summary, field)) for field in SUMMARY_MONEY_FIELDS]
    return [
        MoneyFormatWarning(ref=ref, field=field, description=f"{field}: {warning}; recorded as 0")
        for ref, field, raw in cells
        if (warning := parse_money(raw).warning) is not None
    ]


def money(raw: str | float | int | None) -> Decimal:
    return parse_money(raw).value


def claim_line_values(index: int, item: ParsedClaimItem, links: ClaimLinks, user_id: uuid.UUID) -> ClaimLineValues:
    return ClaimLineValues(
        item_type=item.item_type,
        ref_code=item.ref_code,
        description=item.description,
        contract_value=money(item.contract_value),
        percentage=money(item.percentage),
        ptd=money(item.ptd),
        previous=money(item.previous),
        current=money(item.current),
        balance=money(item.balance),
        sort_order=index,
        suggested_wbs_code_id=links.wbs.get(index),
        variation_id=links.vps.variations.get(index),
        provisional_sum_id=links.vps.provisional_sums.get(index),
        categorisation_confidence=links.confidence.get(index, Decimal(0)),
        created_by=user_id,
    )


async def build_claim(
    db: AsyncSession, *, project_id: uuid.UUID, user_id: uuid.UUID, parsed: ParsedClaim, links: ClaimLinks
) -> Claim:
    metadata, summary = parsed.metadata, parsed.summary
    return await claim_repo.create(
        db,
        line_items=[claim_line_values(i, item, links, user_id) for i, item in enumerate(parsed.line_items)],
        project_id=project_id,
        claim_number=int(metadata.claim_number or 0),
        period_from=parse_ddmmyy(metadata.period_from),
        period_to=parse_ddmmyy(metadata.period_to),
        payment_due=parse_ddmmyy(metadata.payment_due),
        parsed_at=datetime.now(UTC),
        original_contract_total=money(summary.original_contract_total),
        variations_total=money(summary.variations_total),
        revised_contract_total=money(summary.revised_contract_total),
        retention_amount=money(summary.retention_amount),
        claimed_amount=money(summary.claimed_amount),
        created_by=user_id,
    )


async def record_format_warnings(db: AsyncSession, session_id: uuid.UUID, parsed: ParsedClaim) -> None:
    for warning in money_format_warnings(parsed.line_items, parsed.summary):
        logger.warning("create_records: %s (ref=%s)", warning.description, warning.ref)
        await harness_repo.create_flag(
            db,
            session_id,
            FlagSpec(
                flag_type=FlagType.format_warning,
                severity=FlagSeverity.warning,
                description=warning.description,
                line_item_ref=warning.ref,
            ),
        )
