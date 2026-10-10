"""LLM-based matching of claim variation/PS items to existing project records."""

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

from app.config import settings
from app.harness.llm_client import get_client
from app.models.provisional_sum import ProvisionalSum
from app.models.variation import Variation

_PROMPT_TEMPLATE = (Path(__file__).parent.parent / "prompts" / "variation_matcher.md").read_text()

logger = logging.getLogger(__name__)


@dataclass
class VariationMatch:
    """Result of matching a single claim item to an existing project record."""

    claim_ref: str
    item_type: str  # "variation" or "provisional_sum"
    matched_id: UUID | None
    confidence: float  # 0.0–1.0 LLM confidence in this match


async def match_variations_and_ps(
    new_items: list[dict],
    existing_variations: list[Variation],
    existing_provisional_sums: list[ProvisionalSum],
) -> list[VariationMatch]:
    """Match parsed claim variation/PS items to existing project records via LLM.

    Args:
        new_items: List of dicts with keys: ref_code, description, value, item_type
        existing_variations: Project's existing Variation records
        existing_provisional_sums: Project's existing ProvisionalSum records

    Returns:
        List of VariationMatch results — one per new item
    """
    # First claim: no existing records, skip LLM entirely
    if not existing_variations and not existing_provisional_sums:
        return [
            VariationMatch(
                claim_ref=item["ref_code"],
                item_type=item["item_type"],
                matched_id=None,
                confidence=1.0,
            )
            for item in new_items
        ]

    if not new_items:
        return []

    provider = settings.llm_provider.lower()
    key_map = {
        "anthropic": settings.anthropic_api_key,
        "openai": settings.openai_api_key,
        "openrouter": settings.open_router_api_key,
    }
    if not key_map.get(provider):
        logger.warning("No API key for provider %s — skipping variation matching", provider)
        return [
            VariationMatch(
                claim_ref=item["ref_code"],
                item_type=item["item_type"],
                matched_id=None,
                confidence=1.0,
            )
            for item in new_items
        ]

    # Format existing records
    if existing_variations:
        variations_text = "\n".join(
            f'- id="{v.id}", contractor_ref="{v.contractor_ref}", '
            f'description="{v.description}", submission={v.contractor_submission}'
            for v in existing_variations
        )
    else:
        variations_text = "(none)"

    if existing_provisional_sums:
        ps_text = "\n".join(
            f'- id="{ps.id}", ps_number={ps.ps_number}, '
            f'description="{ps.description}", contract_sum={ps.contract_sum}'
            for ps in existing_provisional_sums
        )
    else:
        ps_text = "(none)"

    items_text = "\n".join(
        f'- ref_code="{item["ref_code"]}", type={item["item_type"]}, '
        f'description="{item["description"]}", value={item["value"]}'
        for item in new_items
    )

    prompt = (
        _PROMPT_TEMPLATE.replace("{EXISTING_VARIATIONS}", variations_text)
        .replace("{EXISTING_PROVISIONAL_SUMS}", ps_text)
        .replace("{NEW_ITEMS}", items_text)
    )

    try:
        client = get_client()
        response = await client.chat.completions.create(
            model=settings.llm_model,
            max_tokens=2048,
            messages=[{"role": "user", "content": prompt}],
        )

        response_text = response.choices[0].message.content or ""

        # Extract JSON from response (handle markdown code blocks)
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0]
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0]

        raw_results = json.loads(response_text.strip())

        # Build valid ID sets for validation
        valid_variation_ids = {str(v.id) for v in existing_variations}
        valid_ps_ids = {str(ps.id) for ps in existing_provisional_sums}
        valid_ids = valid_variation_ids | valid_ps_ids

        matches = []
        for item in raw_results:
            matched_id_str = item.get("matched_id")
            matched_id = None
            if matched_id_str and str(matched_id_str) in valid_ids:
                matched_id = UUID(str(matched_id_str))

            matches.append(
                VariationMatch(
                    claim_ref=str(item["claim_ref"]),
                    item_type=item.get("item_type", "variation"),
                    matched_id=matched_id,
                    confidence=float(item.get("confidence", 0.5)),
                )
            )

        logger.info(
            "Variation matcher: %d/%d items matched to existing records",
            sum(1 for m in matches if m.matched_id),
            len(matches),
        )
        return matches

    except Exception:
        logger.exception("Variation matching LLM call failed — treating all as new")
        return [
            VariationMatch(
                claim_ref=item["ref_code"],
                item_type=item["item_type"],
                matched_id=None,
                confidence=0.0,
            )
            for item in new_items
        ]
