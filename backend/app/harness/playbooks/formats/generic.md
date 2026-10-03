## Generic Claim Format

This document does not match any known format. Apply these general rules.

### Extraction Guidance

**Column identification:**
Find the main data table and identify columns by header text:

| Header text contains | Maps to |
|---------------------|---------|
| "Ref", "No.", "Item", "Code" | ref_code |
| "Description", "Item Description", "Works" | description |
| "Contract", "Original", "Value", "Sum" | contract_value |
| "%", "Percent", "Complete" | percentage |
| "PTD", "Claimed to Date", "Total Claimed", "Cumulative" | ptd |
| "Previous", "Prior", "Last" | previous |
| "Current", "This Period", "This Claim" | current |
| "Balance", "Remaining" | balance |

**Missing columns:**
If the document does not have all 8 financial columns, map what exists and set missing fields to "0.00". Common patterns:
- Simple invoices with only description + amount: map amount to `current`, set all others to "0.00"
- Progress claims with only PTD + current: set `contract_value` and others to "0.00"

**Item type classification:**
Without format-specific ref code patterns, classify by section context:
- Items under a "Variations" or "Change Orders" heading → "variation"
- Items under a "Provisional Sums" heading → "provisional_sum"
- Everything else → "contract_work"

**Confidence:**
Set lower confidence (0.5-0.7) for items where column mapping is uncertain.

### Categorisation Guidance

Without format-specific signals, rely on:
1. Contract sum matching (primary) — exact or near-exact match between claim contract_value and WBS subcategory contract_sum
2. Description similarity (secondary) — match trade descriptions to WBS subcategory descriptions
