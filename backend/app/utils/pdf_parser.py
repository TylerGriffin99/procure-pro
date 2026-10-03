"""Template-based WBPRO claim PDF parser using pdfplumber."""
import re
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation

import pdfplumber


class WBPROFormatError(Exception):
    """Raised when a PDF does not match the expected WBPRO format."""


@dataclass
class ParsedLineItem:
    ref_code: str | None
    description: str
    item_type: str  # "contract_work", "variation", "provisional_sum"
    contract_value: Decimal
    percentage: Decimal
    ptd: Decimal
    previous: Decimal
    current: Decimal
    balance: Decimal
    section_title: str | None = None  # e.g. "Variation Works", "Contract Works"


@dataclass
class ParsedSummary:
    original_contract_total: Decimal = Decimal("0")
    variations_total: Decimal = Decimal("0")
    revised_contract_total: Decimal = Decimal("0")
    retention_amount: Decimal = Decimal("0")
    claimed_amount: Decimal = Decimal("0")


@dataclass
class ParsedClaim:
    claim_number: int | None
    project_name: str | None
    contractor_name: str
    job_number: str | None
    period_from: str | None
    period_to: str | None
    payment_due: str | None
    line_items: list[ParsedLineItem] = field(default_factory=list)
    summary: ParsedSummary = field(default_factory=ParsedSummary)


def _parse_number(text: str | None) -> Decimal:
    """Parse a number string, handling commas and negatives."""
    if not text or text.strip() in ("", "-"):
        return Decimal("0.00")
    cleaned = text.strip().replace(",", "").replace(" ", "")
    # Handle parenthetical negatives: (1,730.00) -> -1730.00
    if cleaned.startswith("(") and cleaned.endswith(")"):
        cleaned = "-" + cleaned[1:-1]
    try:
        return Decimal(cleaned)
    except InvalidOperation:
        return Decimal("0.00")


def _parse_percentage(text: str | None) -> Decimal:
    """Parse percentage string like '47.43 %' -> 47.43"""
    if not text or text.strip() in ("", "-"):
        return Decimal("0.00")
    cleaned = text.strip().replace("%", "").replace(" ", "").replace(",", "")
    try:
        return Decimal(cleaned)
    except InvalidOperation:
        return Decimal("0.00")


def _detect_wbpro_format(pages: list) -> bool:
    """Check if the PDF matches WBPRO format markers."""
    if not pages:
        return False
    text = pages[0].extract_text() or ""
    # WBPRO claims have distinctive markers on the first page
    markers = ["Claim No.", "Period From:", "Period To:", "Payment Due:"]
    found = sum(1 for m in markers if m in text)
    return found >= 2


def _extract_header_info(pages: list) -> dict:
    """Extract claim header info from first page text."""
    text = pages[0].extract_text() or ""

    claim_number = None
    project_name = None
    contractor_name = None
    period_from = None
    period_to = None
    payment_due = None
    job_number = None

    for line in text.split("\n"):
        line_stripped = line.strip()
        if "Claim No." in line_stripped:
            m = re.search(r"Claim No\.\s*(\d+)", line_stripped)
            if m:
                claim_number = int(m.group(1))
        if "Project Name:" in line_stripped:
            project_name = line_stripped.split("Project Name:")[-1].strip()
        if "Our Job No:" in line_stripped:
            m = re.search(r"Our Job No:\s*(\S+)", line_stripped)
            if m:
                job_number = m.group(1)
        if "Kynoch" in line_stripped and "Payee" not in line_stripped:
            contractor_name = "Kynoch Construction Ltd"
        if "Period From:" in line_stripped:
            m = re.search(r"Period From:\s*(\S+)", line_stripped)
            if m:
                period_from = m.group(1)
        if "Period To:" in line_stripped:
            m = re.search(r"Period To:\s*(\S+)", line_stripped)
            if m:
                period_to = m.group(1)
        if "Payment Due:" in line_stripped:
            m = re.search(r"Payment Due:\s*(\S+)", line_stripped)
            if m:
                payment_due = m.group(1)

    # Fallback: search all text for contractor name
    if not contractor_name:
        if "Kynoch" in text:
            contractor_name = "Kynoch Construction Ltd"

    return {
        "claim_number": claim_number,
        "project_name": project_name,
        "contractor_name": contractor_name or "Unknown",
        "job_number": job_number,
        "period_from": period_from,
        "period_to": period_to,
        "payment_due": payment_due,
    }


def _is_contract_works_row(row: list[str | None]) -> bool:
    """Check if a table row looks like a contract works line item (has 4-digit Ref code)."""
    if not row or len(row) < 8:
        return False
    ref = (row[0] or "").strip()
    return bool(re.match(r"^\d{4}$", ref))


def _find_section_titles(text: str) -> list[str]:
    """Find section title lines from page text (all-caps, 2+ words)."""
    titles = []
    for line in text.split("\n"):
        stripped = line.strip()
        if re.match(r'^[A-Z]{2,}(?:\s+[A-Z]{2,})+$', stripped):
            titles.append(stripped.title())
    return titles


def _is_variation_row(row: list[str | None]) -> bool:
    """Check if a table row looks like a variation line item (has short CTC# number)."""
    if not row or len(row) < 9:
        return False
    ref = (row[0] or "").strip()
    return bool(re.match(r"^\d{1,3}$", ref))


def _extract_summary(pages: list) -> ParsedSummary:
    """Extract contract summary from the last page."""
    last_page = pages[-1]
    text = last_page.extract_text() or ""

    summary = ParsedSummary()

    for line in text.split("\n"):
        if "Original Contract:" in line:
            m = re.search(r"Original Contract:\s*([\d,]+\.\d{2})", line)
            if m:
                summary.original_contract_total = _parse_number(m.group(1))
        if "Variations:" in line and "Approved" not in line:
            m = re.search(r"Variations:\s*([\d,]+\.\d{2})", line)
            if m:
                summary.variations_total = _parse_number(m.group(1))
        if "Revised Contract:" in line:
            m = re.search(r"Revised Contract:\s*([\d,]+\.\d{2})", line)
            if m:
                summary.revised_contract_total = _parse_number(m.group(1))
        if "Retentions:" in line or "Less Retentions:" in line:
            m = re.search(r"Retentions:\s*([\d,]+\.\d{2})", line)
            if m:
                summary.retention_amount = _parse_number(m.group(1))
        if "Claim Amount:" in line:
            m = re.search(r"Claim Amount:\s*([\d,]+\.\d{2})", line)
            if m:
                summary.claimed_amount = _parse_number(m.group(1))

    return summary


def parse_wbpro_claim(pdf_path: str) -> ParsedClaim:
    """Parse a WBPRO-format contractor progress claim PDF.

    Raises:
        WBPROFormatError: If the PDF does not match WBPRO format.
    """
    with pdfplumber.open(pdf_path) as pdf:
        pages = pdf.pages

        if not _detect_wbpro_format(pages):
            raise WBPROFormatError(
                "This PDF does not appear to be in WBPRO format. "
                "Only WBPRO-format contractor progress claims are currently supported."
            )

        header = _extract_header_info(pages)
        line_items: list[ParsedLineItem] = []
        in_variations = False
        current_section = "Contract Works"

        for page in pages:
            text = page.extract_text() or ""

            # Update section context from page headings before processing tables
            for title in _find_section_titles(text):
                current_section = title
            if "VARIATION WORKS" in text:
                in_variations = True

            tables = page.extract_tables()
            for table in tables:
                for row in table:
                    if not row or all(c is None or c.strip() == "" for c in row):
                        continue

                    # Skip header rows
                    first_cell = (row[0] or "").strip()
                    if first_cell in ("Ref", "CTC#", ""):
                        continue

                    if in_variations and _is_variation_row(row):
                        ref = first_cell
                        desc = (row[1] or "").strip()

                        line_items.append(ParsedLineItem(
                            ref_code=ref,
                            description=desc,
                            contract_value=_parse_number(row[3]),
                            percentage=_parse_percentage(row[4]),
                            ptd=_parse_number(row[5]),
                            previous=_parse_number(row[6]),
                            current=_parse_number(row[7]),
                            balance=_parse_number(row[8]) if len(row) > 8 else Decimal("0"),
                            item_type="variation",
                            section_title=current_section,
                        ))

                    elif _is_contract_works_row(row):
                        ref = first_cell
                        desc = (row[1] or "").strip()

                        item_type = "contract_work"
                        if desc.lower().startswith("provisional sum"):
                            item_type = "provisional_sum"

                        line_items.append(ParsedLineItem(
                            ref_code=ref,
                            description=desc,
                            contract_value=_parse_number(row[2]),
                            percentage=_parse_percentage(row[3]),
                            ptd=_parse_number(row[4]),
                            previous=_parse_number(row[5]),
                            current=_parse_number(row[6]),
                            balance=_parse_number(row[7]) if len(row) > 7 else Decimal("0"),
                            item_type=item_type,
                            section_title=current_section,
                        ))

            # Reset variation flag for next page if we see contract works again
            if "CONTRACT WORKS" in text and "VARIATION" not in text:
                in_variations = False

        summary = _extract_summary(pages)

        return ParsedClaim(
            claim_number=header["claim_number"],
            project_name=header["project_name"],
            contractor_name=header["contractor_name"],
            job_number=header["job_number"],
            period_from=header["period_from"],
            period_to=header["period_to"],
            payment_due=header["payment_due"],
            line_items=line_items,
            summary=summary,
        )
