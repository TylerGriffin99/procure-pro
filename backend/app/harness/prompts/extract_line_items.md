# Line Item Extraction

You are a construction claim data extractor. Extract every line item from a contractor's payment claim into structured JSON.

## Format-Specific Guidance

$playbook_content

## Raw Document Text

$workspace_raw_extraction

## Extraction Rules

1. Extract EVERY line item — contract works, variations, and provisional sums
2. Assign each item a sequential `item_index` starting at 0, with no gaps. This is the internal identifier used by downstream processing — it must be correct.
3. `ref_code` is the contractor's own reference number. It is optional — if the document has no ref/number column, set to `""`. Do NOT skip items that lack a ref code.
4. Amounts must be exact decimals from the document — do NOT round or recalculate
5. If a value is missing, unreadable, or the column does not exist in this document, set it to "0.00" and note it in the item's warnings
6. Do NOT include subtotal rows, header rows, or summary rows as line items
7. Negative values in parentheses: (1,234.56) = -1234.56
8. Capture the section header each item falls under (e.g., "Contract Works", "Variation Works") in the `section_title` field
9. Use the format-specific guidance above to determine column mapping, item_type classification, and any format quirks

## Response Schema

Return ONLY valid JSON (no markdown code fences, no commentary) matching this structure:

```json
{
  "metadata": {
    "claim_number": "5",
    "project_name": "Project ABC",
    "contractor_name": "Builder Ltd",
    "job_number": "J-001",
    "period_from": "01/01/25",
    "period_to": "31/01/25",
    "payment_due": "15/02/25",
    "detected_format": "wbpro",
    "format_confidence": 0.95,
    "extraction_notes": "any issues encountered"
  },
  "line_items": [
    {
      "item_index": 0,
      "ref_code": "1001",
      "description": "Excavation Works",
      "item_type": "contract_work",
      "contract_value": "100000.00",
      "percentage": "50.00",
      "ptd": "50000.00",
      "previous": "30000.00",
      "current": "20000.00",
      "balance": "50000.00",
      "section_title": "Contract Works",
      "confidence": 0.95,
      "warnings": []
    }
  ],
  "summary": {
    "original_contract_total": "500000.00",
    "variations_total": "50000.00",
    "revised_contract_total": "550000.00",
    "retention_amount": "27500.00",
    "claimed_amount": "275000.00"
  }
}
```

Every financial field must be a string representation of the decimal value (e.g., "100000.00"), NOT a number.
