"""Generic LLM-based line-item extractor.

For claim formats that don't match a known deterministic parser (e.g. WBPRO),
this module sends the raw extraction through an LLM prompt and normalises
the response into the parsed_claim.json schema.
"""

import json
import logging
import string

from app.clients.llm_client import LlmClient
from app.constants.enums import ClaimFormat, ClaimItemType
from app.harness.extract_shared import summary_totals
from app.harness.prompts import load_playbook, load_prompt
from app.harness.schemas import (
    GenericExtraction,
    GenericLineItem,
    GenericSummary,
    ParsedClaim,
    ParsedClaimItem,
    ParsedClaimMetadata,
    ParsedClaimSummary,
    RawExtraction,
)
from app.utils.money import format_money, parse_money

logger = logging.getLogger(__name__)

_DECIMAL_FIELDS = ("contract_value", "percentage", "ptd", "previous", "current", "balance")


def money_text(value: str | float | int | None) -> str:
    parsed = parse_money(value)
    if parsed.warning is not None:
        # A non-empty value we couldn't parse is bad data, not a true zero — surface it.
        logger.warning("Could not parse decimal value %r; defaulting to 0.00", value)
    return format_money(parsed.value)


def normalise_item(index: int, raw_item: GenericLineItem) -> ParsedClaimItem:
    item_type = raw_item.item_type or ClaimItemType.contract_work
    if item_type not in ClaimItemType:
        logger.warning("Unknown item_type %r on item %d; coercing to contract_work", item_type, index)
        item_type = ClaimItemType.contract_work
    return ParsedClaimItem(
        item_index=index,
        ref_code=raw_item.ref_code or "",
        description=raw_item.description or "",
        item_type=ClaimItemType(item_type),
        **{field: money_text(getattr(raw_item, field)) for field in _DECIMAL_FIELDS},
    )


def normalise_summary(raw_summary: GenericSummary, line_items: list[ParsedClaimItem]) -> ParsedClaimSummary:
    if not all(getattr(raw_summary, k) for k in GenericSummary.model_fields):
        return summary_totals(line_items)
    return ParsedClaimSummary(
        original_contract_total=money_text(raw_summary.original_contract_total),
        revised_contract_total=money_text(raw_summary.revised_contract_total),
        claimed_amount=money_text(raw_summary.claimed_amount),
    )


def validate_and_normalise(extraction: GenericExtraction) -> ParsedClaim:
    """Raises ValueError if line_items is empty; item indexes are reassigned 0..n-1."""
    if not extraction.line_items:
        raise ValueError("line_items is empty or missing — LLM returned no data")
    line_items = [normalise_item(idx, raw_item) for idx, raw_item in enumerate(extraction.line_items)]
    meta = extraction.metadata
    metadata = ParsedClaimMetadata(
        claim_number=meta.claim_number or "",
        period_from=meta.period_from or "",
        period_to=meta.period_to or "",
        payment_due=meta.payment_due or "",
    )
    return ParsedClaim(
        metadata=metadata, line_items=line_items, summary=normalise_summary(extraction.summary, line_items)
    )


async def parse_generic(raw_extraction: RawExtraction, *, llm: LlmClient) -> ParsedClaim:
    template_text = load_prompt("extract_line_items")
    playbook_text = load_playbook(ClaimFormat.generic)

    prompt = string.Template(template_text).safe_substitute(
        playbook_content=playbook_text,
        workspace_raw_extraction=json.dumps(raw_extraction.model_dump(mode="json", exclude_none=True)),
    )

    response = await llm.run_structured(
        output_type=GenericExtraction,
        system_prompt=prompt,
        user_prompt="Extract all line items from this contractor payment claim.",
        phase_name="extract_line_items_generic",
    )
    result = validate_and_normalise(response.output)

    logger.info(
        "Generic parse: %d line items (%d contract, %d variation, %d PS)",
        len(result.line_items),
        sum(1 for i in result.line_items if i.item_type == ClaimItemType.contract_work),
        sum(1 for i in result.line_items if i.item_type == ClaimItemType.variation),
        sum(1 for i in result.line_items if i.item_type == ClaimItemType.provisional_sum),
    )
    return result
