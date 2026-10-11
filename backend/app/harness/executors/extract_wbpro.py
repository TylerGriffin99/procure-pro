"""Deterministic WBPRO table parser.

Converts raw_extraction.json (pdfplumber output) into parsed_claim.json
for WBPRO-format contractor claims. Column layouts are fixed and known,
so no LLM is needed.
"""

import logging
from collections.abc import Sequence
from typing import Final

from app.constants.enums import ClaimItemType
from app.constants.values import STANDARD_COLUMNS, VARIATION_COLUMNS
from app.harness.extract_shared import ITEM_MONEY_FIELDS, extract_metadata, money_warnings, summary_totals
from app.harness.schemas import ParsedClaim, ParsedClaimItem, ParsedClaimMetadata, RawExtraction, RawPage
from app.schemas.claim_extraction import MoneyFormatWarning
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


def detect_sections(pages: Sequence[RawPage]) -> dict[int, str]:
    """A page with no section header inherits the previous page's section; the first defaults to contract work."""
    page_sections: dict[int, str] = {}
    prev_section = SECTION_CONTRACT

    for page in pages:
        found_section = None
        for header, section_type in _SECTION_HEADERS:
            if header in page.text:
                found_section = section_type
        prev_section = found_section or prev_section
        page_sections[page.page_num] = prev_section

    return page_sections


def money_cells(cells: Sequence[str | None]) -> dict[str, str]:
    return {field: format_money(parse_money(cell).value) for field, cell in zip(ITEM_MONEY_FIELDS, cells, strict=True)}


def money_slice(row: list[str | None], section: str) -> list[str | None]:
    return row[3:9] if section == SECTION_VARIATION else row[2:8]


def row_warnings(item: ParsedClaimItem, row: list[str | None], section: str) -> list[MoneyFormatWarning]:
    cells = zip(ITEM_MONEY_FIELDS, money_slice(row, section), strict=True)
    return money_warnings((item.ref_code, field, cell) for field, cell in cells)


def map_row_to_item(row: list[str | None], section: str, item_index: int) -> ParsedClaimItem | None:
    """Contract Works / Provisional Sums rows have 8 columns
    ``[ref, description, contract_value, percentage, ptd, previous, current, balance]``; variation rows have 9,
    with ``client_ref`` after the description. Returns None for a row with the wrong column count."""
    ncols = len(row)
    if section == SECTION_VARIATION:
        if ncols != VARIATION_COLUMNS:
            logger.warning("Variation row has %d cols (expected %d), skipping", ncols, VARIATION_COLUMNS)
            return None
        item_type = ClaimItemType.variation
    else:
        if ncols != STANDARD_COLUMNS:
            logger.warning("%s row has %d cols (expected %d), skipping", section, ncols, STANDARD_COLUMNS)
            return None
        item_type = ClaimItemType.provisional_sum if section == SECTION_PS else ClaimItemType.contract_work
    return ParsedClaimItem(
        item_index=item_index,
        ref_code=str(row[0] or "").strip(),
        description=str(row[1] or "").strip(),
        item_type=item_type,
        **money_cells(money_slice(row, section)),
    )


def is_skip_row(row: list[str | None]) -> bool:
    """Empty rows, and total/subtotal rows (a total keyword in the description column with an empty ref)."""
    if all(not cell or not str(cell).strip() for cell in row):
        return True
    desc = str(row[1] or "").strip().lower() if len(row) > 1 else ""
    ref = str(row[0] or "").strip() if len(row) > 0 else ""
    total_keywords = ("total", "sub-total", "subtotal", "sub total")
    return not ref and any(kw in desc for kw in total_keywords)


def table_section(table: list[list[str | None]], page_section: str) -> str:
    # A page can hold tables from two sections; column count tells them apart (9 = variation, and an
    # 8-column table on a variation page is contract works overflow).
    first_data_row = next((r for r in table if not is_skip_row(r)), None)
    if first_data_row is None:
        return page_section
    ncols = len(first_data_row)
    if ncols == VARIATION_COLUMNS:
        return SECTION_VARIATION
    if ncols == STANDARD_COLUMNS and page_section == SECTION_VARIATION:
        return SECTION_CONTRACT
    return page_section


def page_rows(raw_extraction: RawExtraction) -> list[tuple[list[str | None], str]]:
    page_sections = detect_sections(raw_extraction.pages)
    rows: list[tuple[list[str | None], str]] = []
    for page in raw_extraction.pages:
        for table in page.tables:
            section = table_section(table, page_sections.get(page.page_num, SECTION_CONTRACT))
            rows += [(row, section) for row in table if not is_skip_row(row)]
    return rows


def parse_wbpro(raw_extraction: RawExtraction) -> ParsedClaim:
    metadata = extract_metadata(raw_extraction.all_text())
    line_items: list[ParsedClaimItem] = []
    format_warnings: list[MoneyFormatWarning] = []
    for row, section in page_rows(raw_extraction):
        item = map_row_to_item(row, section, len(line_items))
        if item is not None:
            line_items.append(item)
            format_warnings += row_warnings(item, row, section)

    logger.info(
        "WBPRO parse: %d line items (%d contract, %d variation, %d PS)",
        len(line_items),
        sum(1 for i in line_items if i.item_type == ClaimItemType.contract_work),
        sum(1 for i in line_items if i.item_type == ClaimItemType.variation),
        sum(1 for i in line_items if i.item_type == ClaimItemType.provisional_sum),
    )
    return ParsedClaim(
        metadata=ParsedClaimMetadata(**{key: value or "" for key, value in metadata.model_dump().items()}),
        line_items=line_items,
        summary=summary_totals(line_items),
        format_warnings=format_warnings,
    )
