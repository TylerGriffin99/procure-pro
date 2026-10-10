"""Deterministic WBPRO table parser.

Converts raw_extraction.json (pdfplumber output) into parsed_claim.json
for WBPRO-format contractor claims. Column layouts are fixed and known,
so no LLM is needed.
"""

import logging
import re
from decimal import Decimal, InvalidOperation

logger = logging.getLogger(__name__)


def parse_decimal(value: str | None) -> str:
    """Parse a string value into a normalised decimal string.

    Handles: commas, parenthesised negatives, blanks, dashes.
    Returns a string like "1234.56" or "0.00".
    """
    if not value or not value.strip() or value.strip() == "-":
        return "0.00"
    s = value.strip()
    # Parenthesised negative: (1,234.56) -> -1234.56
    neg = False
    if s.startswith("(") and s.endswith(")"):
        neg = True
        s = s[1:-1]
    s = s.replace(",", "")
    try:
        d = Decimal(s)
    except InvalidOperation:
        return "0.00"
    if neg:
        d = -d
    # Normalise to 2dp string
    return str(d.quantize(Decimal("0.01")))


# Section type constants
SECTION_CONTRACT = "contract_work"
SECTION_VARIATION = "variation"
SECTION_PS = "provisional_sum"

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


def map_row_to_item(
    row: list[str | None],
    section: str,
    item_index: int,
) -> dict | None:
    """Map a table row to a parsed_claim line item dict.

    Returns None if column count is invalid for the section type.

    Contract Works / Provisional Sums (8 cols):
        [ref, description, contract_value, percentage, ptd, previous, current, balance]

    Variations (9 cols):
        [ctc_ref, description, client_ref, contract_value, percentage, ptd, previous, current, balance]
    """
    ncols = len(row)

    if section == SECTION_VARIATION:
        if ncols != 9:
            logger.warning("Variation row has %d cols (expected 9), skipping", ncols)
            return None
        return {
            "item_index": item_index,
            "ref_code": str(row[0] or "").strip(),
            "description": str(row[1] or "").strip(),
            "item_type": "variation",
            "contract_value": parse_decimal(row[3]),
            "percentage": parse_decimal(row[4]),
            "ptd": parse_decimal(row[5]),
            "previous": parse_decimal(row[6]),
            "current": parse_decimal(row[7]),
            "balance": parse_decimal(row[8]),
        }
    else:
        # Contract Works or Provisional Sums — both 8 cols
        if ncols != 8:
            logger.warning("%s row has %d cols (expected 8), skipping", section, ncols)
            return None
        item_type = "provisional_sum" if section == SECTION_PS else "contract_work"
        return {
            "item_index": item_index,
            "ref_code": str(row[0] or "").strip(),
            "description": str(row[1] or "").strip(),
            "item_type": item_type,
            "contract_value": parse_decimal(row[2]),
            "percentage": parse_decimal(row[3]),
            "ptd": parse_decimal(row[4]),
            "previous": parse_decimal(row[5]),
            "current": parse_decimal(row[6]),
            "balance": parse_decimal(row[7]),
        }


_METADATA_PATTERNS = {
    "claim_number": re.compile(r"Claim\s*(?:No\.?|Number)\s*[:\-]?\s*(\d+)", re.IGNORECASE),
    "period_from": re.compile(r"Period\s*From\s*[:\-]?\s*([\d/]+)", re.IGNORECASE),
    "period_to": re.compile(r"Period\s*To\s*[:\-]?\s*([\d/]+)", re.IGNORECASE),
    "payment_due": re.compile(r"Payment\s*Due\s*[:\-]?\s*([\d/]+)", re.IGNORECASE),
}


def extract_metadata(all_pages_text: str) -> dict[str, str]:
    """Extract claim metadata from the combined text of all pages."""
    result: dict[str, str] = {
        "claim_number": "",
        "period_from": "",
        "period_to": "",
        "payment_due": "",
    }
    for key, pattern in _METADATA_PATTERNS.items():
        match = pattern.search(all_pages_text)
        if match:
            result[key] = match.group(1)
    return result


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
    metadata = extract_metadata(all_text)

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
                if ncols == 9:
                    table_section = SECTION_VARIATION
                elif ncols == 8 and page_section == SECTION_VARIATION:
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

    logger.info(
        "WBPRO parse: %d line items (%d contract, %d variation, %d PS)",
        len(line_items),
        sum(1 for i in line_items if i["item_type"] == "contract_work"),
        sum(1 for i in line_items if i["item_type"] == "variation"),
        sum(1 for i in line_items if i["item_type"] == "provisional_sum"),
    )

    return {
        "metadata": metadata,
        "line_items": line_items,
        "summary": summary,
    }
