import logging
import uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from decimal import Decimal
from typing import Final

from sqlalchemy.ext.asyncio import AsyncSession

from app.constants.enums import FlagSeverity, FlagType
from app.constants.values import STANDARD_COLUMNS, VARIATION_COLUMNS
from app.harness.extract_shared import ITEM_MONEY_FIELDS, MoneyCell, money_warnings, parse_cell
from app.harness.schemas import (
    ClaimLinks,
    FlagSpec,
    ParsedClaim,
    ParsedClaimItem,
    ParsedClaimMetadata,
    ParsedClaimSummary,
)
from app.models.claim import Claim
from app.repos import claim_repo, harness_repo
from app.schemas.claim_extraction import ClaimLineValues, ParseWarning
from app.utils.dates import parse_ddmmyy
from app.utils.money import parse_money

logger = logging.getLogger(__name__)

SUMMARY_MONEY_FIELDS: Final = (
    "original_contract_total",
    "variations_total",
    "revised_contract_total",
    "retention_amount",
    "claimed_amount",
)


def money_format_warnings(line_items: Sequence[ParsedClaimItem], summary: ParsedClaimSummary) -> list[ParseWarning]:
    cells: list[MoneyCell] = [
        (item.ref_code, field, getattr(item, field)) for item in line_items for field in ITEM_MONEY_FIELDS
    ]
    cells += [(None, field, getattr(summary, field)) for field in SUMMARY_MONEY_FIELDS]
    return money_warnings(cells)


METADATA_DATE_FIELDS: Final = ("period_from", "period_to", "payment_due")


def parse_claim_number(raw: str) -> int | None:
    text = raw.strip()
    return int(text) if text.isdecimal() else None


def metadata_warnings(metadata: ParsedClaimMetadata) -> list[ParseWarning]:
    warnings = [
        ParseWarning(ref=None, field=field, description=f"{field}: {warning}; recorded as blank")
        for field in METADATA_DATE_FIELDS
        if (warning := parse_ddmmyy(getattr(metadata, field)).warning) is not None
    ]
    if parse_claim_number(metadata.claim_number) is None:
        description = f"claim_number {metadata.claim_number!r} missing or unparseable; recorded as 0"
        warnings.append(ParseWarning(ref=None, field="claim_number", description=description))
    return warnings


def money(raw: str | float | int | None) -> Decimal:
    return parse_money(raw).value


def claim_line_values(index: int, item: ParsedClaimItem, links: ClaimLinks, user_id: uuid.UUID) -> ClaimLineValues:
    return ClaimLineValues(
        item_type=item.item_type,
        ref_code=item.ref_code,
        description=item.description,
        contract_value=money(item.contract_value),
        percentage=parse_cell("percentage", item.percentage).value,
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
        claim_number=parse_claim_number(metadata.claim_number) or 0,
        period_from=parse_ddmmyy(metadata.period_from).value,
        period_to=parse_ddmmyy(metadata.period_to).value,
        payment_due=parse_ddmmyy(metadata.payment_due).value,
        parsed_at=datetime.now(UTC),
        original_contract_total=money(summary.original_contract_total),
        variations_total=money(summary.variations_total),
        revised_contract_total=money(summary.revised_contract_total),
        retention_amount=money(summary.retention_amount),
        claimed_amount=money(summary.claimed_amount),
        created_by=user_id,
    )


def parse_warning_flags(parsed: ParsedClaim) -> list[FlagSpec]:
    # Extractor warnings cover cells already normalised to "0.00"; the re-parse covers a hand-written parsed_claim.
    warnings = [
        *parsed.format_warnings,
        *money_format_warnings(parsed.line_items, parsed.summary),
        *metadata_warnings(parsed.metadata),
    ]
    flags = [format_warning(w.description, w.ref) for w in warnings]
    flags += [
        format_warning(
            f"Table row dropped: {row.column_count} columns (expected {STANDARD_COLUMNS} or {VARIATION_COLUMNS}) "
            f"on page {row.page}, row {row.row_index}",
            row.first_cell,
        )
        for row in parsed.dropped_rows
    ]
    return flags


def format_warning(description: str, ref: str | None) -> FlagSpec:
    return FlagSpec(
        flag_type=FlagType.format_warning, severity=FlagSeverity.warning, description=description, line_item_ref=ref
    )


async def record_parse_warnings(db: AsyncSession, session_id: uuid.UUID, parsed: ParsedClaim) -> None:
    for spec in parse_warning_flags(parsed):
        logger.warning("create_records: %s (ref=%s)", spec.description, spec.line_item_ref)
        await harness_repo.create_flag(db, session_id, spec)
