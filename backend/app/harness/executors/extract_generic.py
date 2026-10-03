"""Generic LLM-based line-item extractor.

For claim formats that don't match a known deterministic parser (e.g. WBPRO),
this module sends the raw extraction through an LLM prompt and normalises
the response into the parsed_claim.json schema.
"""
import json
import logging
import string
from decimal import Decimal, InvalidOperation
from pathlib import Path

from pydantic_ai.models import Model

from app.harness.agent_runner import run_structured
from app.harness.schemas import GenericExtraction

logger = logging.getLogger(__name__)

_VALID_ITEM_TYPES = {"contract_work", "variation", "provisional_sum"}

_DECIMAL_FIELDS = (
    "contract_value",
    "percentage",
    "ptd",
    "previous",
    "current",
    "balance",
)


def _normalise_decimal(value) -> str:
    """Normalise any value to a 2-decimal-place string.

    Handles: strings, ints, floats, None, empty strings, dashes,
    parenthesised negatives like "(1,234.56)", dollar signs, commas, spaces.
    """
    if value is None:
        return "0.00"

    if isinstance(value, (int, float)):
        return str(Decimal(str(value)).quantize(Decimal("0.01")))

    s = str(value).strip()
    if not s or s == "-":
        return "0.00"

    # Strip dollar signs and spaces
    s = s.replace("$", "").replace(" ", "")

    # Parenthesised negative: (1,234.56) -> -1234.56
    neg = False
    if s.startswith("(") and s.endswith(")"):
        neg = True
        s = s[1:-1]

    # Strip commas
    s = s.replace(",", "")

    try:
        d = Decimal(s)
    except InvalidOperation:
        # A non-empty value we couldn't parse is bad data, not a true zero — surface it.
        logger.warning("Could not parse decimal value %r; defaulting to 0.00", value)
        return "0.00"

    if neg:
        d = -d

    return str(d.quantize(Decimal("0.01")))


def validate_and_normalise(raw_response: dict) -> dict:
    """Validate and normalise an LLM response to match parsed_claim.json schema.

    Raises ValueError if line_items is empty.
    """
    # --- metadata ---
    raw_meta = raw_response.get("metadata") or {}
    metadata = {
        "claim_number": str(raw_meta.get("claim_number", "") or ""),
        "period_from": str(raw_meta.get("period_from", "") or ""),
        "period_to": str(raw_meta.get("period_to", "") or ""),
        "payment_due": str(raw_meta.get("payment_due", "") or ""),
    }

    # --- line_items ---
    raw_items = raw_response.get("line_items")
    if not raw_items:
        raise ValueError("line_items is empty or missing — LLM returned no data")

    line_items: list[dict] = []
    for idx, raw_item in enumerate(raw_items):
        item_type = str(raw_item.get("item_type", "contract_work") or "contract_work")
        if item_type not in _VALID_ITEM_TYPES:
            logger.warning(
                "Unknown item_type %r on item %d; coercing to contract_work", item_type, idx
            )
            item_type = "contract_work"

        item = {
            "item_index": idx,
            "ref_code": str(raw_item.get("ref_code", "") or ""),
            "description": str(raw_item.get("description", "") or ""),
            "item_type": item_type,
        }
        for field in _DECIMAL_FIELDS:
            item[field] = _normalise_decimal(raw_item.get(field))

        line_items.append(item)

    # --- summary ---
    raw_summary = raw_response.get("summary") or {}
    # Recompute from items if summary is missing or incomplete
    needs_recompute = not raw_summary or not all(
        raw_summary.get(k) for k in ("original_contract_total", "revised_contract_total", "claimed_amount")
    )

    if needs_recompute:
        contract_total = Decimal("0")
        revised_total = Decimal("0")
        claimed_total = Decimal("0")
        for item in line_items:
            val = Decimal(item["contract_value"])
            revised_total += val
            if item["item_type"] == "contract_work":
                contract_total += val
            claimed_total += Decimal(item["ptd"])
        summary = {
            "original_contract_total": str(contract_total.quantize(Decimal("0.01"))),
            "revised_contract_total": str(revised_total.quantize(Decimal("0.01"))),
            "claimed_amount": str(claimed_total.quantize(Decimal("0.01"))),
        }
    else:
        summary = {
            "original_contract_total": _normalise_decimal(raw_summary["original_contract_total"]),
            "revised_contract_total": _normalise_decimal(raw_summary["revised_contract_total"]),
            "claimed_amount": _normalise_decimal(raw_summary["claimed_amount"]),
        }

    return {
        "metadata": metadata,
        "line_items": line_items,
        "summary": summary,
    }


async def parse_generic(raw_extraction: dict, model: Model | None = None) -> dict:
    """Parse a generic-format claim using a structured LLM agent.

    Loads the prompt template and generic playbook, runs the extraction through
    a pydantic-ai agent (validated against ``GenericExtraction``), and normalises
    the typed result. ``model`` is for tests; production uses the configured one.
    """
    prompts_dir = Path(__file__).parent.parent / "prompts"
    playbooks_dir = Path(__file__).parent.parent / "playbooks" / "formats"

    template_text = (prompts_dir / "extract_line_items.md").read_text()
    playbook_text = (playbooks_dir / "generic.md").read_text()

    # Render prompt
    prompt = string.Template(template_text).safe_substitute(
        playbook_content=playbook_text,
        workspace_raw_extraction=json.dumps(raw_extraction),
    )

    # Run the structured agent — output is a validated GenericExtraction.
    response = await run_structured(
        output_type=GenericExtraction,
        system_prompt=prompt,
        user_prompt="Extract all line items from this contractor payment claim.",
        model=model,
        phase_name="extract_line_items_generic",
    )

    # Normalise the typed extraction into the parsed_claim.json schema.
    result = validate_and_normalise(response.output.model_dump())

    logger.info(
        "Generic parse: %d line items (%d contract, %d variation, %d PS)",
        len(result["line_items"]),
        sum(1 for i in result["line_items"] if i["item_type"] == "contract_work"),
        sum(1 for i in result["line_items"] if i["item_type"] == "variation"),
        sum(1 for i in result["line_items"] if i["item_type"] == "provisional_sum"),
    )

    return result
