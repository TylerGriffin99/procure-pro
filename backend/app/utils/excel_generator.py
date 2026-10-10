"""Generate payment recommendation Excel workbook using openpyxl."""

import io
from decimal import Decimal

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter


def _dec(value) -> float:
    """Convert Decimal or any numeric to float for openpyxl."""
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (int, float)):
        return float(value)
    return 0.0


def _apply_header_style(ws, row_num: int, col_count: int):
    """Apply header styling to a row."""
    header_font = Font(bold=True, size=9, color="FFFFFF")
    header_fill = PatternFill(start_color="1A2744", end_color="1A2744", fill_type="solid")
    for col in range(1, col_count + 1):
        cell = ws.cell(row=row_num, column=col)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)


def _set_column_widths(ws, widths: list[int]):
    """Set column widths from a list."""
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w


NUMBER_FMT = "#,##0.00"


def _write_summary_sheet(wb: Workbook, data: dict):
    """Write the Summary sheet with project info and financial breakdown."""
    ws = wb.active
    ws.title = "Summary"

    title_font = Font(bold=True, size=14, color="1A2744")
    section_font = Font(bold=True, size=10, color="1A2744")
    label_font = Font(bold=True, size=9)
    value_font = Font(size=9)
    thin_border = Border(bottom=Side(style="thin", color="CCCCCC"))

    ws.merge_cells("A1:D1")
    ws["A1"] = f"Payment Recommendation #{data.get('pr_number', '')}"
    ws["A1"].font = title_font

    details = [
        ("Project", data.get("project_name", "")),
        ("Project Number", data.get("project_number", "")),
        ("Principal", data.get("principal", "")),
        ("Contractor", data.get("contractor", "")),
        ("Engineer", data.get("engineer", "")),
        ("Claim Number", data.get("claim_number", "")),
        ("Issue Date", data.get("issue_date", "")),
        ("Claim Received", data.get("claim_received", "")),
        ("Payment Due", data.get("payment_due", "")),
    ]

    row = 3
    for label, value in details:
        ws.cell(row=row, column=1, value=label).font = label_font
        ws.cell(row=row, column=2, value=value).font = value_font
        ws.cell(row=row, column=1).border = thin_border
        ws.cell(row=row, column=2).border = thin_border
        row += 1

    row += 1
    ws.cell(row=row, column=1, value="Financial Summary").font = section_font
    row += 1

    financials = [
        ("Contract Sum", data.get("contract_sum")),
        ("Adjustment to Provisional Sums", data.get("adjustment_to_provisional_sums")),
        ("Approved Variation Orders", data.get("approved_variation_orders")),
        ("Adjusted Contract Sum", data.get("adjusted_contract_sum")),
        ("Value of Works Claimed to Date", data.get("value_claimed")),
        ("Adjustments", data.get("adjustments")),
        ("Total Value Recommended", data.get("total_recommended")),
        ("Total Retention", data.get("total_retention")),
        ("Total Payment to Date", data.get("total_payment_to_date")),
        ("Previously Certified", data.get("previously_certified")),
        ("Recommended This Period", data.get("recommended_this_period")),
        ("GST Amount", data.get("gst_amount")),
        ("Total Including GST", data.get("total_including_gst")),
    ]

    for label, value in financials:
        ws.cell(row=row, column=1, value=label).font = label_font
        cell = ws.cell(row=row, column=2, value=_dec(value))
        cell.font = value_font
        cell.number_format = NUMBER_FMT
        ws.cell(row=row, column=1).border = thin_border
        cell.border = thin_border
        row += 1

    retention_details = data.get("retention_details", [])
    if retention_details:
        row += 1
        ws.cell(row=row, column=1, value="Retention Breakdown").font = section_font
        row += 1
        for tier in retention_details:
            ws.cell(row=row, column=1, value=tier.get("percentage", "")).font = value_font
            cell = ws.cell(row=row, column=2, value=_dec(tier.get("amount", 0)))
            cell.font = value_font
            cell.number_format = NUMBER_FMT
            row += 1

    _set_column_widths(ws, [30, 20, 15, 15])


def _write_contract_works_sheet(wb: Workbook, data: dict):
    """Write the Contract Works sheet."""
    ws = wb.create_sheet("Contract Works")
    headers = [
        "Description",
        "Contract Sum",
        "Claim to Date",
        "Total Recommended",
        "Percentage",
        "Variance",
        "Previously Paid",
        "Recommended This Period",
        "Comments",
    ]

    for col, header in enumerate(headers, 1):
        ws.cell(row=1, column=col, value=header)
    _apply_header_style(ws, 1, len(headers))

    for i, item in enumerate(data.get("contract_works", []), 2):
        ws.cell(row=i, column=1, value=item.get("description", ""))
        ws.cell(row=i, column=2, value=_dec(item.get("contract_sum"))).number_format = NUMBER_FMT
        ws.cell(row=i, column=3, value=_dec(item.get("contractor_claim"))).number_format = NUMBER_FMT
        ws.cell(row=i, column=4, value=_dec(item.get("recommended"))).number_format = NUMBER_FMT
        ws.cell(row=i, column=5, value=item.get("percentage", ""))
        ws.cell(row=i, column=6, value=_dec(item.get("variance"))).number_format = NUMBER_FMT
        ws.cell(row=i, column=7, value=_dec(item.get("previously_paid"))).number_format = NUMBER_FMT
        ws.cell(row=i, column=8, value=_dec(item.get("recommended_this_period"))).number_format = NUMBER_FMT
        ws.cell(row=i, column=9, value=item.get("comments", ""))

    _set_column_widths(ws, [30, 15, 15, 18, 12, 15, 15, 20, 30])


def _write_variations_sheet(wb: Workbook, data: dict):
    """Write the Variations sheet."""
    ws = wb.create_sheet("Variations")
    headers = [
        "CI Number",
        "Description",
        "Submission",
        "Type",
        "Claimed to Date",
        "Recommended",
        "Previously Paid",
        "This Period",
        "Status",
        "Comments",
    ]

    for col, header in enumerate(headers, 1):
        ws.cell(row=1, column=col, value=header)
    _apply_header_style(ws, 1, len(headers))

    for i, item in enumerate(data.get("variation_works", []), 2):
        ws.cell(row=i, column=1, value=item.get("ci_number", ""))
        ws.cell(row=i, column=2, value=item.get("description", ""))
        ws.cell(row=i, column=3, value=_dec(item.get("submission"))).number_format = NUMBER_FMT
        ws.cell(row=i, column=4, value=item.get("type", ""))
        ws.cell(row=i, column=5, value=_dec(item.get("claimed_to_date"))).number_format = NUMBER_FMT
        ws.cell(row=i, column=6, value=_dec(item.get("recommended"))).number_format = NUMBER_FMT
        ws.cell(row=i, column=7, value=_dec(item.get("previously_paid"))).number_format = NUMBER_FMT
        ws.cell(row=i, column=8, value=_dec(item.get("this_period"))).number_format = NUMBER_FMT
        ws.cell(row=i, column=9, value=item.get("status", ""))
        ws.cell(row=i, column=10, value=item.get("comments", ""))

    _set_column_widths(ws, [15, 30, 15, 12, 15, 15, 15, 15, 12, 30])


def _write_provisional_sums_sheet(wb: Workbook, data: dict):
    """Write the Provisional Sums sheet."""
    ws = wb.create_sheet("Provisional Sums")
    headers = [
        "PS Number",
        "Description",
        "Contract Sum",
        "Claimed to Date",
        "Recommended",
        "Previously Paid",
        "This Period",
        "Percentage",
        "Status",
        "Comments",
    ]

    for col, header in enumerate(headers, 1):
        ws.cell(row=1, column=col, value=header)
    _apply_header_style(ws, 1, len(headers))

    for i, item in enumerate(data.get("provisional_sums", []), 2):
        ws.cell(row=i, column=1, value=item.get("ps_number", ""))
        ws.cell(row=i, column=2, value=item.get("description", ""))
        ws.cell(row=i, column=3, value=_dec(item.get("contract_sum"))).number_format = NUMBER_FMT
        ws.cell(row=i, column=4, value=_dec(item.get("claimed_to_date"))).number_format = NUMBER_FMT
        ws.cell(row=i, column=5, value=_dec(item.get("recommended"))).number_format = NUMBER_FMT
        ws.cell(row=i, column=6, value=_dec(item.get("previously_paid"))).number_format = NUMBER_FMT
        ws.cell(row=i, column=7, value=_dec(item.get("this_period"))).number_format = NUMBER_FMT
        ws.cell(row=i, column=8, value=item.get("percentage", ""))
        ws.cell(row=i, column=9, value=item.get("status", ""))
        ws.cell(row=i, column=10, value=item.get("comments", ""))

    _set_column_widths(ws, [15, 30, 15, 15, 15, 15, 15, 12, 12, 30])


def generate_payment_recommendation_excel(data: dict) -> bytes:
    """Generate a payment recommendation Excel workbook from assessment data.

    Args:
        data: Dict containing all PR fields (same structure as PDF generator)

    Returns:
        Excel (.xlsx) file contents as bytes
    """
    wb = Workbook()
    _write_summary_sheet(wb, data)
    _write_contract_works_sheet(wb, data)
    _write_variations_sheet(wb, data)
    _write_provisional_sums_sheet(wb, data)

    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()
