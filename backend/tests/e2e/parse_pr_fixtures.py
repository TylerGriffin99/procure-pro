"""
Parse the 8 Gilmours Payment Recommendation PDFs and generate golden fixture data.

Usage:
    cd backend
    python tests/e2e/parse_pr_fixtures.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pdfplumber

# ── PDF paths ──────────────────────────────────────────────────────────────
REPO_ROOT = Path(__file__).resolve().parents[3]  # backend/tests/e2e -> repo root
PR_DIR = REPO_ROOT / "claim" / "Gilmours" / "payment_recomendations"

PR_FILES = [
    "Gilmours Central Seismic PR No 1 09Sep25.pdf",
    "Gilmours Central Seismic PR No 2 10Oct25.pdf",
    "Gilmours Central Seismic PR No 3 12Nov25.pdf",
    "Gilmours Central Seismic PR No 4 03Dec25.pdf",
    "Gilmours Central Seismic PR No 5 18Dec25.pdf",
    "Gilmours Central Seismic PR No 6 10Feb26.pdf",
    "Gilmours Central Seismic PR No 7 10Mar26.pdf",
    "Gilmours Central Seismic PR No 8 R2 20Apr26.pdf",
]

# ── Category headers to skip in Contract Works table ───────────────────────
CATEGORY_HEADERS = {
    "Demolition",
    "Drainage",
    "Car Park & Yard",
    "Substructure",
    "Frame",
    "External Walls & Exterior Finishes",
    "Internal Partitions & Doors",
    "Ceiling Finishes",
    "HVAC",
    "Fire Protection",
    # These sometimes appear as subcategory-level but are actually categories
    "External Walls",
    "Internal Partitions",
}

# ── Summary rows to skip ──────────────────────────────────────────────────
SKIP_DESCRIPTIONS = {
    "SUB TOTAL CONTRACT WORKS",
    "Materials Onsite",
    "Materials Offsite",
    "Provisional Sums",
    "Variations",
    "Retentions",
    "TOTAL",
}


def parse_value(raw: str | None) -> str:
    """Convert a PDF cell value to a clean decimal string.

    - None / empty / "-" -> "0.00"
    - "(1,730.00)" -> "-1730.00"
    - "1,234.56" -> "1234.56"
    - "6 1,728.65" (OCR space glitch) -> "61728.65"
    """
    if not raw or raw.strip() in ("", "-"):
        return "0.00"
    s = raw.strip()
    negative = False
    if s.startswith("(") and s.endswith(")"):
        negative = True
        s = s[1:-1]
    # Remove commas and stray spaces within numbers (OCR artifacts like "6 6,801.52")
    s = s.replace(",", "").replace(" ", "")
    # Remove any trailing % sign
    s = s.rstrip("%")
    if not s or s == "-":
        return "0.00"
    try:
        val = float(s)
    except ValueError:
        return "0.00"
    if negative:
        val = -val
    return f"{val:.2f}"


def parse_percentage(raw: str | None) -> str:
    """Convert a PDF percentage cell to a 4-decimal string."""
    if not raw or raw.strip() in ("", "-"):
        return "0.0000"
    s = raw.strip().rstrip("%").replace(",", "").replace(" ", "")
    if not s or s == "-":
        return "0.0000"
    try:
        val = float(s)
    except ValueError:
        return "0.0000"
    return f"{val:.4f}"


def find_page_by_header(pdf: pdfplumber.PDF, header: str) -> int | None:
    """Find the page index containing a specific section header."""
    for i, page in enumerate(pdf.pages):
        text = page.extract_text() or ""
        if header in text:
            return i
    return None


def is_skip_row(desc: str) -> bool:
    """Check if a contract works row should be skipped."""
    desc_clean = desc.strip()
    if not desc_clean:
        return True
    if desc_clean in CATEGORY_HEADERS:
        return True
    if desc_clean in SKIP_DESCRIPTIONS:
        return True
    # Skip rows that start with "SUB TOTAL"
    if desc_clean.startswith("SUB TOTAL"):
        return True
    return False


def extract_contract_works(pdf: pdfplumber.PDF) -> list[dict]:
    """Extract assessment line items from the CONTRACT WORKS page."""
    page_idx = find_page_by_header(pdf, "PAYMENT RECOMMENDATION - CONTRACT WORKS")
    if page_idx is None:
        print("  WARNING: Could not find CONTRACT WORKS page", file=sys.stderr)
        return []

    page = pdf.pages[page_idx]
    tables = page.extract_tables()
    if not tables:
        print("  WARNING: No tables on CONTRACT WORKS page", file=sys.stderr)
        return []

    table = tables[0]
    items = []
    for row in table[1:]:  # skip header
        desc = (row[0] or "").strip()
        if is_skip_row(desc):
            continue
        # Must have a contract_sum to be a real line item
        contract_sum = parse_value(row[1])
        if contract_sum == "0.00":
            # Category header with no contract_sum — but some items legitimately
            # have contract_sum that parses. Check if it looks like a category.
            # If it has dashes in ALL value columns, it's a category header.
            if all((row[c] or "").strip() in ("", "-") for c in [1, 2, 3]):
                continue

        # Columns: 0=Description, 1=Contract Sum, 2=Claim To Date,
        #          3=Total Recommended, 4=%, 5=Variance, 6=Previously Paid,
        #          7=Recommended This Period, 8=Comments
        items.append({
            "description": desc,
            "contract_sum": parse_value(row[1]),
            "contractor_claim_to_date": parse_value(row[2]),
            "total_recommended": parse_value(row[3]),
            "percentage": parse_percentage(row[4]),
            "previously_paid": parse_value(row[6]),
            "recommended_this_period": parse_value(row[7]),
        })

    return items


def extract_provisional_sums(pdf: pdfplumber.PDF) -> list[dict]:
    """Extract provisional sum items from the PROVISIONAL SUMS page."""
    page_idx = find_page_by_header(pdf, "PAYMENT RECOMMENDATION - PROVISIONAL SUMS")
    if page_idx is None:
        print("  WARNING: Could not find PROVISIONAL SUMS page", file=sys.stderr)
        return []

    page = pdf.pages[page_idx]
    tables = page.extract_tables()
    if not tables:
        print("  WARNING: No tables on PROVISIONAL SUMS page", file=sys.stderr)
        return []

    table = tables[0]
    items = []
    # Columns: 0=PS No., 1=Description, 2=Contract Sum, 3=LL/OP, 4=Trade,
    #          5=Claim To Date, 6=Total Recommended, 7=%, 8=Variance,
    #          9=Previously paid, 10=Recommended This Period, 11=Comments
    for row in table[1:]:  # skip header (may have duplicate header row)
        ps_no_raw = (row[0] or "").strip()
        desc = (row[1] or "").strip()

        # Skip empty rows, duplicate header rows, TOTAL rows
        if not ps_no_raw or desc.upper() == "TOTAL" or desc == "":
            continue
        # Skip if it's a header row repeat
        if ps_no_raw.startswith("PS\n") or ps_no_raw == "PS":
            continue

        # Extract PS number (e.g., "PS 1" -> "1")
        match = re.match(r"PS\s*(\d+)", ps_no_raw)
        if not match:
            continue
        ps_number = match.group(1)

        items.append({
            "ps_number": ps_number,
            "description": desc,
            "contract_sum": parse_value(row[2]),
            "contractor_claim_to_date": parse_value(row[5]),
            "total_recommended": parse_value(row[6]),
            "percentage": parse_percentage(row[7]),
            "previously_paid": parse_value(row[9]),
            "recommended_this_period": parse_value(row[10]),
        })

    return items


def extract_variations(pdf: pdfplumber.PDF) -> list[dict]:
    """Extract variation items from the VARIATIONS page."""
    page_idx = find_page_by_header(pdf, "PAYMENT RECOMMENDATION - VARIATIONS")
    if page_idx is None:
        print("  WARNING: Could not find VARIATIONS page", file=sys.stderr)
        return []

    page = pdf.pages[page_idx]
    tables = page.extract_tables()
    if not tables:
        print("  WARNING: No tables on VARIATIONS page", file=sys.stderr)
        return []

    table = tables[0]
    items = []
    # Columns: 0=CI/PMI No., 1=Description, 2=Contractor's Submission,
    #          3=LL/OP, 4=Trade, 5=Claim To Date, 6=Total Recommended,
    #          7=%, 8=Variance, 9=Previously paid, 10=Recommended This Period,
    #          11=Comments
    for row in table[1:]:  # skip header
        ref_raw = (row[0] or "").strip()
        desc = (row[1] or "").strip()

        # Skip empty rows, header rows, section headers, TOTAL rows
        if not ref_raw:
            continue
        if desc.upper() == "TOTAL":
            continue
        if ref_raw.startswith("CI / PMI") or ref_raw.startswith("CI /"):
            continue

        # Match CI or SI number
        match = re.match(r"(?:CI|SI|PMI)\s*(\d+)", ref_raw)
        if not match:
            continue

        ref_number = match.group(1)
        contractor_submission = parse_value(row[2])

        # Skip TBC items with no real values
        if desc.upper() == "TBC" and contractor_submission == "0.00":
            continue

        items.append({
            "contractor_ref": ref_number,
            "ref_type": "CI" if ref_raw.startswith("CI") else ("SI" if ref_raw.startswith("SI") else "PMI"),
            "description": desc,
            "contractor_submission": contractor_submission,
            "contractor_claim_to_date": parse_value(row[5]),
            "total_recommended": parse_value(row[6]),
            "percentage": parse_percentage(row[7]),
            "previously_paid": parse_value(row[9]),
            "recommended_this_period": parse_value(row[10]),
        })

    return items


def extract_summary(pdf: pdfplumber.PDF) -> dict:
    """Extract summary totals from the SUMMARY page."""
    page_idx = find_page_by_header(pdf, "PAYMENT RECOMMENDATION - SUMMARY")
    if page_idx is None:
        print("  WARNING: Could not find SUMMARY page", file=sys.stderr)
        return {}

    text = pdf.pages[page_idx].extract_text() or ""
    lines = text.split("\n")

    result = {}

    for i, line in enumerate(lines):
        # Contract Sum
        if line.strip().startswith("Contract Sum:"):
            val = line.split(":")[-1].strip()
            result["contract_sum"] = parse_value(val)

        # Total Value of Works Recommended for Payment
        if "Total Value of Works Recommended for Payment" in line:
            # Value is at end of line or next line
            parts = line.split("Payment")
            val = parts[-1].strip() if len(parts) > 1 else ""
            if not val and i + 1 < len(lines):
                val = lines[i + 1].strip()
            result["total_recommended"] = parse_value(val)

        # Total Payment to Date
        if "Total Payment to Date" in line:
            # Value is at end of line
            val = line.replace("Total Payment to Date", "").strip()
            result["total_payment_to_date"] = parse_value(val)

        # Less Previously Certified
        if "Less Previously Certified" in line:
            val = line.replace("Less Previously Certified", "").strip()
            result["previously_certified"] = parse_value(val)

        # Recommended Payment to Contractor (Excluding GST) 61,728.65
        if "Recommended Payment to Contractor" in line and "Excluding GST" in line:
            nums = re.findall(r"[\d,]+\.\d{2}", line)
            if nums:
                result["recommended_this_period"] = parse_value(nums[-1])

    # Extract retention from the retention lines
    # Look for retention total — sum of all retention lines
    # Pattern: "10% of total works recommended (X) (Y)"
    retention_total = 0.0
    for line in lines:
        # Match patterns like "10% of total works recommended (68,587.39) (6,858.74)"
        # or "5% of total works recommended 0.00 0.00"
        if "% of total works recommended" in line:
            # Find all numbers in the line (after the pattern)
            after = line.split("recommended")[-1]
            nums = re.findall(r"\(?([\d,]+\.\d{2})\)?", after)
            if len(nums) >= 2:
                # Last number is the retention amount for this tier
                ret_val = float(nums[-1].replace(",", ""))
                # Check if it's in parentheses (negative)
                if f"({nums[-1]})" in after:
                    ret_val = abs(ret_val)
                retention_total += ret_val

    if retention_total > 0:
        result["total_retention"] = f"{retention_total:.2f}"
    else:
        result["total_retention"] = "0.00"

    return result


def parse_pr(filepath: Path, claim_number: int) -> dict:
    """Parse a single Payment Recommendation PDF."""
    print(f"\n{'='*60}", file=sys.stderr)
    print(f"Parsing PR {claim_number}: {filepath.name}", file=sys.stderr)
    print(f"{'='*60}", file=sys.stderr)

    pdf = pdfplumber.open(filepath)

    contract_works = extract_contract_works(pdf)
    ps_items = extract_provisional_sums(pdf)
    var_items = extract_variations(pdf)
    summary = extract_summary(pdf)

    print(f"  Contract works items: {len(contract_works)}", file=sys.stderr)
    print(f"  PS items: {len(ps_items)}", file=sys.stderr)
    print(f"  Variation items: {len(var_items)}", file=sys.stderr)
    print(f"  Summary: {summary}", file=sys.stderr)

    pdf.close()

    return {
        "claim_number": claim_number,
        "assessment_line_items": contract_works,
        "assessment_ps_items": ps_items,
        "assessment_var_items": var_items,
        "finalised_totals": summary,
    }


def format_dict(d: dict, indent: int = 8) -> str:
    """Format a dict as a Python literal string."""
    pad = " " * indent
    parts = []
    for k, v in d.items():
        parts.append(f'{pad}"{k}": "{v}"')
    return "{\n" + ",\n".join(parts) + ",\n" + " " * (indent - 4) + "}"


def format_list_of_dicts(items: list[dict], indent: int = 8) -> str:
    """Format a list of dicts as a Python literal string."""
    if not items:
        return "[]"
    pad = " " * indent
    parts = []
    for item in items:
        kvs = ", ".join(f'"{k}": "{v}"' for k, v in item.items())
        parts.append(f"{pad}{{{kvs}}}")
    return "[\n" + ",\n".join(parts) + ",\n" + " " * (indent - 4) + "]"


def main():
    results = []
    for i, filename in enumerate(PR_FILES, 1):
        filepath = PR_DIR / filename
        if not filepath.exists():
            print(f"MISSING: {filepath}", file=sys.stderr)
            continue
        result = parse_pr(filepath, i)
        results.append(result)

    # Print as Python code
    print("GOLDEN_FIXTURES = [")
    for r in results:
        print(f"    {{")
        print(f'        "claim_number": {r["claim_number"]},')
        print(f'        "assessment_line_items": {format_list_of_dicts(r["assessment_line_items"], 12)},')
        print(f'        "assessment_ps_items": {format_list_of_dicts(r["assessment_ps_items"], 12)},')
        print(f'        "assessment_var_items": {format_list_of_dicts(r["assessment_var_items"], 12)},')
        print(f'        "finalised_totals": {format_dict(r["finalised_totals"], 12)},')
        print(f"    }},")
    print("]")


if __name__ == "__main__":
    main()
