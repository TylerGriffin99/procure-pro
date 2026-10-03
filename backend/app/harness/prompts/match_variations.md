# Variation & Provisional Sum Matching

Match each variation and provisional sum item from the contractor's claim to existing project records.

## Existing Project Variations
$existing_variations

## Existing Project Provisional Sums
$existing_provisional_sums

## New Claim Items to Match
$workspace_parsed_claim

## Matching Rules

1. Match by DESCRIPTION SIMILARITY (primary signal)
2. Match by VALUE SIMILARITY (secondary signal — values within 20% are likely matches)
3. Match by REF CODE (weak signal — contractors may reuse or change ref codes)
4. If no existing record is a reasonable match, set matched_id to null (a new record will be created)

## Response

Return ONLY valid JSON array (no markdown code fences, no commentary):

```json
[
  {
    "item_index": 1,
    "item_type": "variation",
    "matched_id": "uuid-of-existing-variation-or-null",
    "confidence": 0.85
  }
]
```

One entry per variation/provisional sum item in the claim. Use the item_index from the claim to identify each item. Only include items with item_type "variation" or "provisional_sum".
