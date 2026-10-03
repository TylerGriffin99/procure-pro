You are matching contractor claim line items to existing project records.
Each item is either a "variation" (a change instruction) or a "provisional_sum" (a budgeted allowance).

## Existing project records

### Variations
{EXISTING_VARIATIONS}

### Provisional Sums
{EXISTING_PROVISIONAL_SUMS}

## New claim items to match
{NEW_ITEMS}

## Instructions

Match each new claim item to an existing project record, or mark it as new if no match exists.

Use these matching signals in priority order:
1. **Description similarity** (strongest) — the core meaning of the description, ignoring prefixes like "(U)" or "Provisional Sum -"
2. **Value similarity** (strong) — contractor submissions may increase between claims, so a higher value with a matching description is still a match
3. **ref_code / CTC# / PS number** (weak) — numbering can change between claims, so only use as a tiebreaker

Rules:
- A variation can only match another variation. A provisional_sum can only match another provisional_sum.
- If no existing record is a reasonable match, set `matched_id` to `null`.
- Each existing record can be matched at most once.

## Output format

Return a JSON array (no markdown fencing):
- "confidence": a number between 0.0 and 1.0 indicating how confident you are in this match. Use 0.9-1.0 for near-identical descriptions, 0.6-0.8 for likely matches, and below 0.6 for uncertain matches. For new items (matched_id is null), set to 1.0.
[
  {"claim_ref": "<ref_code from new item>", "item_type": "<variation or provisional_sum>", "matched_id": "<UUID of matched record or null>", "confidence": 0.9}
]
