"""LLM-based WBS categorisation for claim line items.

Given a project's parent WBS categories and any existing subcategories,
uses an LLM to either match each claim line item to an existing subcategory
or propose a new subcategory under the appropriate parent category.
"""

import json
import logging
from dataclasses import dataclass
from pathlib import Path

from app.config import settings
from app.harness.llm_client import get_client

_PROMPT_TEMPLATE = (Path(__file__).parent.parent / "prompts" / "contractor_claim.md").read_text()

logger = logging.getLogger(__name__)


@dataclass
class WBSMatch:
    """Result of categorising a single claim line item."""

    ref_code: str
    wbs_code: str  # e.g. "DM-01"
    wbs_description: str  # e.g. "Demolition Works"
    parent_code: str  # e.g. "DM"
    is_new: bool  # True if the LLM proposed a new subcategory
    is_variation: bool  # True if the item description began with (U)
    confidence: float  # 0.0–1.0 LLM confidence in this match


async def categorise_claim_items(
    claim_items: list[dict],
    parent_categories: list[dict],
    existing_subcategories: list[dict],
) -> list[WBSMatch]:
    """Categorise claim line items into WBS subcategories using an LLM.

    Args:
        claim_items: List of dicts with 'description' and 'ref_code'
        parent_categories: List of dicts with 'code' and 'description' (e.g. DM, EX, PG)
        existing_subcategories: List of dicts with 'code', 'description', and 'parent_code'

    Returns:
        List of WBSMatch results — one per claim item (or fewer if LLM can't categorise some)
    """
    provider = settings.llm_provider.lower()
    key_map = {
        "anthropic": settings.anthropic_api_key,
        "openai": settings.openai_api_key,
        "openrouter": settings.open_router_api_key,
    }
    if not key_map.get(provider):
        logger.warning(
            "No API key configured for provider %s — skipping LLM categorisation", provider
        )
        return []

    if not claim_items:
        return []

    categories_text = "\n".join(f"- {c['code']}: {c['description']}" for c in parent_categories)

    if existing_subcategories:
        subcategories_text = "\n".join(
            f"- {s['code']}: {s['description']} (parent: {s['parent_code']})"
            for s in existing_subcategories
        )
    else:
        subcategories_text = "(none yet — you must create new subcategories for all items)"

    items_text = "\n".join(
        f'- ref_code="{item["ref_code"]}" [section: {item.get("section_title") or "Unknown"}]: {item["description"]}'
        for item in claim_items
    )

    prompt = (
        _PROMPT_TEMPLATE.replace("{CATEGORIES}", categories_text)
        .replace("{SUBCATEGORIES}", subcategories_text)
        .replace("{ITEMS}", items_text)
    )

    try:
        client = get_client()
        response = await client.chat.completions.create(
            model=settings.llm_model,
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )

        response_text = response.choices[0].message.content or ""

        # Extract JSON from response (handle markdown code blocks)
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0]
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0]

        raw_results = json.loads(response_text.strip())

        # Validate and convert to WBSMatch objects
        valid_parent_codes = {c["code"] for c in parent_categories}
        existing_codes = {s["code"] for s in existing_subcategories}
        matches = []

        for item in raw_results:
            parent_code = item.get("parent_code", "")
            if parent_code not in valid_parent_codes:
                logger.warning(
                    "LLM returned invalid parent code %s for ref %s — skipping",
                    parent_code,
                    item.get("ref_code"),
                )
                continue

            wbs_code = item.get("wbs_code", "")
            is_new = item.get("is_new", wbs_code not in existing_codes)

            matches.append(
                WBSMatch(
                    ref_code=str(item["ref_code"]),
                    wbs_code=wbs_code,
                    wbs_description=item.get("wbs_description", ""),
                    parent_code=parent_code,
                    is_new=is_new,
                    is_variation=bool(item.get("is_variation", False)),
                    confidence=float(item.get("confidence", 0.5)),
                )
            )

        logger.info(
            "LLM categorised %d/%d items (%d new subcategories)",
            len(matches),
            len(claim_items),
            sum(1 for m in matches if m.is_new),
        )
        return matches

    except Exception:
        logger.exception("LLM categorisation failed — continuing without")
        return []
