"""Deterministic WBPRO table parser.

Converts raw_extraction.json (pdfplumber output) into parsed_claim.json
for WBPRO-format contractor claims. Column layouts are fixed and known,
so no LLM is needed.
"""

import logging
from typing import Final

from app.constants.enums import ClaimItemType
from app.constants.values import STANDARD_COLUMNS, VARIATION_COLUMNS
from app.harness.extract_shared import extract_metadata, summary_totals
from app.utils.money import format_money, parse_money

logger = logging.getLogger(__name__)


SECTION_CONTRACT: Final = ClaimItemType.contract_work
SECTION_VARIATION: Final = ClaimItemType.variation
SECTION_PS: Final = ClaimItemType.provisional_sum

# Section header patterns — checked in order, last match on a page wins
_SECTION_HEADERS = [
    ("CONTRACT WORKS", SECTION_CONTRACT),
    ("VARIATION WORKS", SECTION_VARIATION),
    ("PROVISIONAL SUMS", SECTION_PS),
]


def detect_sections(pages: list[dict]) -> dict[int, str]:
    """Map page numbers to their active section type.

    Scans page text for section headers. If a page has no header,
    it inherits from the previous page. First page defaults to contract_work.
    """
    page_sections: dict[int, str] = {}
    prev_section = SECTION_CONTRACT

    for page in pages:
        page_num = page["page_num"]
        text = page.get("text", "")
        found_section = None

        for header, section_type in _SECTION_HEADERS:
            if header in text:
                found_section = section_type

        if found_section:
            page_sections[page_num] = found_section
            prev_section = found_section
        else:
            page_sections[page_num] = prev_section

    return page_sections


def map_row_to_item(row: list[str | None], section: str, item_index: int) -> dict | None:
    """Map a table row to a parsed_claim line item dict.

    Returns None if column count is invalid for the section type.

    Contract Works / Provisional Sums (8 cols):
        [ref, description, contract_value, percentage, ptd, previous, current, balance]

    Variations (9 cols):
        [ctc_ref, description, client_ref, contract_value, percentage, ptd, previous,
         current, balance]
    """
    ncols = len(row)

    if section == SECTION_VARIATION:
        if ncols != VARIATION_COLUMNS:
            logger.warning("Variation row has %d cols (expected %d), skipping", ncols, VARIATION_COLUMNS)
            return None
        return {
            "item_index": item_index,
            "ref_code": str(row[0] or "").strip(),
            "description": str(row[1] or "").strip(),
            "item_type": ClaimItemType.variation,
            "contract_value": format_money(parse_money(row[3]).value),
            "percentage": format_money(parse_money(row[4]).value),
            "ptd": format_money(parse_money(row[5]).value),
            "previous": format_money(parse_money(row[6]).value),
            "current": format_money(parse_money(row[7]).value),
            "balance": format_money(parse_money(row[8]).value),
        }
    else:
        # Contract Works or Provisional Sums — both 8 cols
        if ncols != STANDARD_COLUMNS:
            logger.warning("%s row has %d cols (expected %d), skipping", section, ncols, STANDARD_COLUMNS)
            return None
        item_type = ClaimItemType.provisional_sum if section == SECTION_PS else ClaimItemType.contract_work
        return {
            "item_index": item_index,
            "ref_code": str(row[0] or "").strip(),
            "description": str(row[1] or "").strip(),
            "item_type": item_type,
            "contract_value": format_money(parse_money(row[2]).value),
            "percentage": format_money(parse_money(row[3]).value),
            "ptd": format_money(parse_money(row[4]).value),
            "previous": format_money(parse_money(row[5]).value),
            "current": format_money(parse_money(row[6]).value),
            "balance": format_money(parse_money(row[7]).value),
        }


def is_skip_row(row: list[str | None]) -> bool:
    """Return True if this row should be skipped (empty or total/subtotal)."""
    # All empty/None
    if all(not cell or not str(cell).strip() for cell in row):
        return True
    # Total/subtotal row: description column (index 1) contains a total keyword,
    # and ref column (index 0) is empty — meaning it's a summary row, not a real item.
    desc = str(row[1] or "").strip().lower() if len(row) > 1 else ""
    ref = str(row[0] or "").strip() if len(row) > 0 else ""
    total_keywords = ("total", "sub-total", "subtotal", "sub total")
    return not ref and any(kw in desc for kw in total_keywords)


def parse_wbpro(raw_extraction: dict) -> dict:
    """Parse a WBPRO-format raw extraction into the parsed_claim.json schema.

    Args:
        raw_extraction: The output of Phase 0 (raw_extraction.json).

    Returns:
        Dict matching the parsed_claim.json schema with metadata, line_items, summary.
    """
    pages = raw_extraction.get("pages", [])

    # 1. Detect section per page
    page_sections = detect_sections(pages)

    # 2. Extract metadata from all page text
    all_text = "\n".join(p.get("text", "") for p in pages)
    metadata = {key: value or "" for key, value in extract_metadata(all_text).model_dump().items()}

    # 3. Walk pages → tables → rows, map each row to a line item
    line_items: list[dict] = []
    item_index = 0

    for page in pages:
        page_num = page["page_num"]
        page_section = page_sections.get(page_num, SECTION_CONTRACT)

        for table in page.get("tables", []):
            # Determine section for this table using column count as primary signal.
            # A page can contain tables from two sections (e.g. contract works overflow
            # followed by variations). Column count reliably distinguishes them:
            #   8 cols = contract_work or provisional_sum
            #   9 cols = variation
            first_data_row = next((r for r in table if not is_skip_row(r)), None)
            if first_data_row is not None:
                ncols = len(first_data_row)
                if ncols == VARIATION_COLUMNS:
                    table_section = SECTION_VARIATION
                elif ncols == STANDARD_COLUMNS and page_section == SECTION_VARIATION:
                    # 8-col table on a variation page = contract works overflow
                    table_section = SECTION_CONTRACT
                else:
                    table_section = page_section
            else:
                table_section = page_section

            for row in table:
                if is_skip_row(row):
                    continue
                item = map_row_to_item(row, table_section, item_index)
                if item is None:
                    continue
                line_items.append(item)
                item_index += 1

    # 4. Compute summary totals
    summary = summary_totals(line_items).model_dump()

    logger.info(
        "WBPRO parse: %d line items (%d contract, %d variation, %d PS)",
        len(line_items),
        sum(1 for i in line_items if i["item_type"] == ClaimItemType.contract_work),
        sum(1 for i in line_items if i["item_type"] == ClaimItemType.variation),
        sum(1 for i in line_items if i["item_type"] == ClaimItemType.provisional_sum),
    )

    return {"metadata": metadata, "line_items": line_items, "summary": summary}
