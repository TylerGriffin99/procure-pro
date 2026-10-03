## WBPRO Claim Format

This document is a WBPRO-format contractor progress claim.

### Extraction Guidance

**Column layout** (in order):

| Position | Header | Maps to |
|----------|--------|---------|
| 1 | Ref / No. (optional) | ref_code |
| 2 | Item Description | description |
| 3 | Value / Contract Value | contract_value |
| 4 | % | percentage |
| 5 | PTD / Claimed to Date | ptd |
| 6 | Previous / Prev | previous |
| 7 | Current / This Period | current |
| 8 | Balance | balance |

**Section structure:**
- **CONTRACT WORKS**: Main contract items. Ref codes are typically 4 digits (e.g., 1001, 3120, 4065). Set item_type = "contract_work".
- **VARIATION WORKS**: Approved or unapproved scope changes. Ref codes are typically 1-3 digits (e.g., 1, 2, 15). Set item_type = "variation". Descriptions often start with "(U)" for unapproved variations.
- **PROVISIONAL SUMS**: Items described as "Provisional sum" or "PS". Set item_type = "provisional_sum".
- Sections are separated by subtotal rows — do NOT extract subtotal rows as line items.
- Capture the section header (e.g., "Contract Works", "Variation Works") in the `section_title` field for each item.

**Multi-line descriptions:**
If a row has text in the description column but no ref code and no financial values, it is a continuation of the previous item's description — concatenate it with a space.

**Known quirks:**
- Merged cells in header rows — ignore, use column position
- Decimal format: 1,234.56 (comma thousands, dot decimal)
- Negative values in parentheses: (1,234.56) = -1234.56
- Some WBPRO exports include a "Section" column before Ref — detect and adjust column positions
- Subtotal rows have descriptions like "Sub Total", "Total", or "Gross Amount" with no ref code — skip these

### Categorisation Guidance

When matching claim items to WBS subcategories:

- Items from the "CONTRACT WORKS" section are trade items — match to trade categories (DM, DR, CP, SS, FR, EW, IP, CF, HV, FP, PL, MG, etc.) primarily by contract_sum, then by description.
- Items from the "VARIATION WORKS" section should be matched under the VR (Variations) parent category.
- Items described as "Provisional Sum" or "PS" should be matched under the PS (Provisional Sums) parent category.
- WBPRO ref codes with close numbers (e.g., 3120, 3160, 3210) often belong to related trade categories in the original contract — but do NOT assume the same parent. Always check contract_sum first.
