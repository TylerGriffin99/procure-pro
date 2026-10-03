"""
Expected outputs for Gilmours Central Progress Claim No. 2.

These fixtures define the exact values the system must produce when Claim No. 2
is uploaded after Claim No. 1 has been assessed and finalised (matching PR1).

Reference documents:
  - claim/Gilmours/claims/Gilmours Central_Progress Claim No. 2.pdf  (contractor input)
  - claim/Gilmours/payment_recomendations/Gilmours Central Seismic PR No 2 10Oct25.pdf  (desired QS output)
"""

# ── PR1 approval data ──────────────────────────────────────────────────────
# After auto-creating the assessment for Claim 1, the QS approves items to
# match Payment Recommendation No. 1.  Items with zero claims are auto-approved.

# Contract work items: approve unapproved items at their claimed amounts
PR1_CONTRACT_WORK_APPROVALS = {
    "General": "6250.00",
    "Temp driveway": "35395.50",
    "General Margin": "6250.00",
}

# PS1 (fence removal): QS reduces from 7114.38 to 5384.38
PR1_PS_RECOMMENDED = "5384.38"

# Variations: approve at their auto-calculated amounts (no QS reduction)
# Var 2 (Manawatu): 10069.49, Var 3 (cost transfer): 5238.02


# ── Expected finalised assessment 1 summary ────────────────────────────────
ASSESSMENT_1_EXPECTED = {
    "total_recommended": "68587.39",       # 47895.50 + 5384.38 + 15307.51
    "total_retention": "6858.74",          # 10% of 68587.39
    "total_payment_to_date": "61728.65",   # 68587.39 - 6858.74
    "previously_certified": "0",
    "recommended_this_period": "61728.65",
}


# ── Expected claim 2 line items ────────────────────────────────────────────
EXPECTED_CLAIM_2_ITEM_COUNT = 35  # 25 contract + 4 PS + 6 variations

EXPECTED_CLAIM_2_LINE_ITEMS = [
    {"item_type": "contract_work",   "ref_code": "3120", "description": "Excavation and siteworks",                        "contract_value": "64504.78",   "ptd": "0.00",      "previous": "0.00",      "current": "0.00",      "balance": "64504.78"},
    {"item_type": "contract_work",   "ref_code": "3160", "description": "Demolition works",                                "contract_value": "120480.00",  "ptd": "0.00",      "previous": "0.00",      "current": "0.00",      "balance": "120480.00"},
    {"item_type": "contract_work",   "ref_code": "3210", "description": "Concrete and Formwork",                           "contract_value": "256840.78",  "ptd": "0.00",      "previous": "0.00",      "current": "0.00",      "balance": "256840.78"},
    {"item_type": "contract_work",   "ref_code": "3230", "description": "Pile Drilling",                                   "contract_value": "62257.00",   "ptd": "0.00",      "previous": "0.00",      "current": "0.00",      "balance": "62257.00"},
    {"item_type": "contract_work",   "ref_code": "3350", "description": "Ply barrier under birdcage",                      "contract_value": "22500.00",   "ptd": "0.00",      "previous": "0.00",      "current": "0.00",      "balance": "22500.00"},
    {"item_type": "contract_work",   "ref_code": "3420", "description": "Reinforcing steel",                               "contract_value": "104865.35",  "ptd": "0.00",      "previous": "0.00",      "current": "0.00",      "balance": "104865.35"},
    {"item_type": "contract_work",   "ref_code": "3510", "description": "Structural Steel",                                "contract_value": "1184000.00", "ptd": "0.00",      "previous": "0.00",      "current": "0.00",      "balance": "1184000.00"},
    {"item_type": "contract_work",   "ref_code": "3730", "description": "Alum joinery and automatic doors",                "contract_value": "8344.00",    "ptd": "0.00",      "previous": "0.00",      "current": "0.00",      "balance": "8344.00"},
    {"item_type": "contract_work",   "ref_code": "3855", "description": "Temporary fencing and hoarding",                  "contract_value": "40160.00",   "ptd": "0.00",      "previous": "0.00",      "current": "0.00",      "balance": "40160.00"},
    {"item_type": "contract_work",   "ref_code": "4010", "description": "Removal and reinstatement of PIR panels",         "contract_value": "27944.00",   "ptd": "0.00",      "previous": "0.00",      "current": "0.00",      "balance": "27944.00"},
    {"item_type": "contract_work",   "ref_code": "4035", "description": "Metal wall cladding",                             "contract_value": "47537.47",   "ptd": "0.00",      "previous": "0.00",      "current": "0.00",      "balance": "47537.47"},
    {"item_type": "contract_work",   "ref_code": "4065", "description": "Scaffolding and Encapsulation",                   "contract_value": "893343.50",  "ptd": "0.00",      "previous": "0.00",      "current": "0.00",      "balance": "893343.50"},
    {"item_type": "contract_work",   "ref_code": "4115", "description": "Relocation of stormwater, sewer and water",       "contract_value": "156773.92",  "ptd": "124535.00", "previous": "0.00",      "current": "124535.00", "balance": "32238.92"},
    {"item_type": "contract_work",   "ref_code": "4120", "description": "Removal and reinstatement of aircon units",       "contract_value": "14298.00",   "ptd": "0.00",      "previous": "0.00",      "current": "0.00",      "balance": "14298.00"},
    {"item_type": "contract_work",   "ref_code": "4125", "description": "Removal and reinstatement of chiller units",      "contract_value": "6490.25",    "ptd": "0.00",      "previous": "0.00",      "current": "0.00",      "balance": "6490.25"},
    {"item_type": "contract_work",   "ref_code": "4130", "description": "Fire Sprinkler Alteration",                       "contract_value": "200000.00",  "ptd": "0.00",      "previous": "0.00",      "current": "0.00",      "balance": "200000.00"},
    {"item_type": "contract_work",   "ref_code": "4165", "description": "Temporary lighting below birdcage",               "contract_value": "35429.00",   "ptd": "0.00",      "previous": "0.00",      "current": "0.00",      "balance": "35429.00"},
    {"item_type": "contract_work",   "ref_code": "4225", "description": "Suspended Ceilings",                              "contract_value": "68026.70",   "ptd": "0.00",      "previous": "0.00",      "current": "0.00",      "balance": "68026.70"},
    {"item_type": "contract_work",   "ref_code": "4325", "description": "Concrete driveway - 200mm thick",                 "contract_value": "30800.00",   "ptd": "0.00",      "previous": "0.00",      "current": "0.00",      "balance": "30800.00"},
    {"item_type": "contract_work",   "ref_code": "4355", "description": "Asphalt prep and hotmix",                         "contract_value": "24860.00",   "ptd": "0.00",      "previous": "0.00",      "current": "0.00",      "balance": "24860.00"},
    {"item_type": "contract_work",   "ref_code": "5020", "description": "Temporary office - in store",                     "contract_value": "37607.20",   "ptd": "0.00",      "previous": "0.00",      "current": "0.00",      "balance": "37607.20"},
    {"item_type": "contract_work",   "ref_code": "5040", "description": "Temporary Driveway",                              "contract_value": "50565.00",   "ptd": "35395.50",  "previous": "35395.50",  "current": "0.00",      "balance": "15169.50"},
    {"item_type": "contract_work",   "ref_code": "5090", "description": "Temporary ablution blocks, office and lunchroom",  "contract_value": "54865.97",   "ptd": "8281.79",   "previous": "0.00",      "current": "8281.79",   "balance": "46584.18"},
    {"item_type": "contract_work",   "ref_code": "5410", "description": "Preliminary and General",                         "contract_value": "250000.00",  "ptd": "10000.00",  "previous": "6250.00",   "current": "3750.00",   "balance": "240000.00"},
    {"item_type": "contract_work",   "ref_code": "9000", "description": "Contract Margin",                                 "contract_value": "250000.00",  "ptd": "10000.00",  "previous": "6250.00",   "current": "3750.00",   "balance": "240000.00"},
    {"item_type": "provisional_sum", "ref_code": "3390", "description": "Provisional sum - Removal and reinstatement of fen", "contract_value": "15000.00", "ptd": "5384.38",   "previous": "5384.38",   "current": "0.00",      "balance": "9615.62"},
    {"item_type": "provisional_sum", "ref_code": "3810", "description": "Provisional sum - Carpentry General",             "contract_value": "80000.00",   "ptd": "0.00",      "previous": "0.00",      "current": "0.00",      "balance": "80000.00"},
    {"item_type": "provisional_sum", "ref_code": "4810", "description": "Provisional sum - Remedial works to interior walls", "contract_value": "25000.00", "ptd": "0.00",      "previous": "0.00",      "current": "0.00",      "balance": "25000.00"},
    {"item_type": "provisional_sum", "ref_code": "4850", "description": "Provisional sum - Services",                      "contract_value": "40000.00",   "ptd": "0.00",      "previous": "0.00",      "current": "0.00",      "balance": "40000.00"},
    {"item_type": "variation",       "ref_code": "1",    "description": "(U) Birdnetting in ambient area",                 "contract_value": "11169.55",   "ptd": "0.00",      "previous": "0.00",      "current": "0.00",      "balance": "11169.55"},
    {"item_type": "variation",       "ref_code": "2",    "description": "(U) Manawatu security fencing",                   "contract_value": "10069.49",   "ptd": "10069.49",  "previous": "10069.49",  "current": "0.00",      "balance": "0.00"},
    {"item_type": "variation",       "ref_code": "3",    "description": "(U) Cost transfer from extension contract",       "contract_value": "194158.11",  "ptd": "36590.97",  "previous": "5238.02",   "current": "31352.95",  "balance": "157567.14"},
    {"item_type": "variation",       "ref_code": "4",    "description": "(U) Move mechanical duct - as requested by ops team", "contract_value": "1476.09", "ptd": "1476.09",   "previous": "0.00",      "current": "1476.09",   "balance": "0.00"},
    {"item_type": "variation",       "ref_code": "5",    "description": "(U) Tidy existing cabling in canopy area",        "contract_value": "4322.01",    "ptd": "4322.01",   "previous": "0.00",      "current": "4322.01",   "balance": "0.00"},
    {"item_type": "variation",       "ref_code": "6",    "description": "(U) Additional excavation - Temporary driveway",  "contract_value": "12052.42",   "ptd": "12052.42",  "previous": "0.00",      "current": "12052.42",  "balance": "0.00"},
]


# ── Expected auto-created assessment 2 line items ──────────────────────────
# These are the WBS-level history carrier rows (claim_line_item_id = NULL).
# They carry previously_paid from the finalised assessment 1.
# contract_sum has been removed from AssessmentLineItemResponse and now lives
# on the WBS group level in the aggregated response.
# recommended_this_period is always 0 on history rows.
# Current-period claim amounts live on separate per-claim-item rows (tested
# via self-consistency, not fixtures).
EXPECTED_ASSESSMENT_2_HISTORY_ROWS = [
    {"description": "Demolition existing structure",              "contractor_claim_to_date": "0.00",     "total_recommended": "0.00",      "previously_paid": "0.00",     "recommended_this_period": "0.00", "status": "approved", "sort_order": 0},
    {"description": "Removal and reinstatement of PIR",           "contractor_claim_to_date": "0.00",     "total_recommended": "0.00",      "previously_paid": "0.00",     "recommended_this_period": "0.00", "status": "approved", "sort_order": 1},
    {"description": "Removal and reinstatement of chiller units", "contractor_claim_to_date": "0.00",     "total_recommended": "0.00",      "previously_paid": "0.00",     "recommended_this_period": "0.00", "status": "approved", "sort_order": 2},
    {"description": "Temp lighting to birdcage - setup",          "contractor_claim_to_date": "0.00",     "total_recommended": "0.00",      "previously_paid": "0.00",     "recommended_this_period": "0.00", "status": "approved", "sort_order": 3},
    {"description": "Bulk Excavation",                            "contractor_claim_to_date": "0.00",     "total_recommended": "0.00",      "previously_paid": "0.00",     "recommended_this_period": "0.00", "status": "approved", "sort_order": 4},
    {"description": "Relocation of stormwater, sewer and water",  "contractor_claim_to_date": "0.00",     "total_recommended": "0.00",      "previously_paid": "0.00",     "recommended_this_period": "0.00", "status": "approved", "sort_order": 5},
    {"description": "Concrete driveway",                          "contractor_claim_to_date": "0.00",     "total_recommended": "0.00",      "previously_paid": "0.00",     "recommended_this_period": "0.00", "status": "approved", "sort_order": 6},
    {"description": "Asphalt prep and hotmix",                    "contractor_claim_to_date": "0.00",     "total_recommended": "0.00",      "previously_paid": "0.00",     "recommended_this_period": "0.00", "status": "approved", "sort_order": 7},
    {"description": "General substructure works",                 "contractor_claim_to_date": "0.00",     "total_recommended": "0.00",      "previously_paid": "0.00",     "recommended_this_period": "0.00", "status": "approved", "sort_order": 8},
    {"description": "Pile drilling",                              "contractor_claim_to_date": "0.00",     "total_recommended": "0.00",      "previously_paid": "0.00",     "recommended_this_period": "0.00", "status": "approved", "sort_order": 9},
    {"description": "Reinforcing steel",                          "contractor_claim_to_date": "0.00",     "total_recommended": "0.00",      "previously_paid": "0.00",     "recommended_this_period": "0.00", "status": "approved", "sort_order": 10},
    {"description": "Steel",                                      "contractor_claim_to_date": "0.00",     "total_recommended": "0.00",      "previously_paid": "0.00",     "recommended_this_period": "0.00", "status": "approved", "sort_order": 11},
    {"description": "Works to external walls",                    "contractor_claim_to_date": "0.00",     "total_recommended": "0.00",      "previously_paid": "0.00",     "recommended_this_period": "0.00", "status": "approved", "sort_order": 12},
    {"description": "Redecoration",                               "contractor_claim_to_date": "0.00",     "total_recommended": "0.00",      "previously_paid": "0.00",     "recommended_this_period": "0.00", "status": "approved", "sort_order": 13},
    {"description": "Suspended ceilings",                         "contractor_claim_to_date": "0.00",     "total_recommended": "0.00",      "previously_paid": "0.00",     "recommended_this_period": "0.00", "status": "approved", "sort_order": 14},
    {"description": "Removal and reinstatement of aircon units",  "contractor_claim_to_date": "0.00",     "total_recommended": "0.00",      "previously_paid": "0.00",     "recommended_this_period": "0.00", "status": "approved", "sort_order": 15},
    {"description": "Fire Sprinkler Alteration",                  "contractor_claim_to_date": "0.00",     "total_recommended": "0.00",      "previously_paid": "0.00",     "recommended_this_period": "0.00", "status": "approved", "sort_order": 16},
    {"description": "General",                                    "contractor_claim_to_date": "6250.00",  "total_recommended": "6250.00",   "previously_paid": "6250.00",  "recommended_this_period": "0.00", "status": "approved", "sort_order": 17},
    {"description": "Temp fencing and hoarding",                  "contractor_claim_to_date": "0.00",     "total_recommended": "0.00",      "previously_paid": "0.00",     "recommended_this_period": "0.00", "status": "approved", "sort_order": 18},
    {"description": "Scaffolding and Encapsulation",              "contractor_claim_to_date": "0.00",     "total_recommended": "0.00",      "previously_paid": "0.00",     "recommended_this_period": "0.00", "status": "approved", "sort_order": 19},
    {"description": "Ply barriers to birdcage",                   "contractor_claim_to_date": "0.00",     "total_recommended": "0.00",      "previously_paid": "0.00",     "recommended_this_period": "0.00", "status": "approved", "sort_order": 20},
    {"description": "Temp ablution blocks",                       "contractor_claim_to_date": "0.00",     "total_recommended": "0.00",      "previously_paid": "0.00",     "recommended_this_period": "0.00", "status": "approved", "sort_order": 21},
    {"description": "Temp office",                                "contractor_claim_to_date": "0.00",     "total_recommended": "0.00",      "previously_paid": "0.00",     "recommended_this_period": "0.00", "status": "approved", "sort_order": 22},
    {"description": "Temp driveway",                              "contractor_claim_to_date": "35395.50", "total_recommended": "35395.50",  "previously_paid": "35395.50", "recommended_this_period": "0.00", "status": "approved", "sort_order": 23},
    {"description": "Temp lighting to birdcage - setup",          "contractor_claim_to_date": "0.00",     "total_recommended": "0.00",      "previously_paid": "0.00",     "recommended_this_period": "0.00", "status": "approved", "sort_order": 24},
    {"description": "General Margin",                             "contractor_claim_to_date": "6250.00",  "total_recommended": "6250.00",   "previously_paid": "6250.00",  "recommended_this_period": "0.00", "status": "approved", "sort_order": 25},
    {"description": "Provisional Sums",                           "contractor_claim_to_date": "0.00",     "total_recommended": "0.00",      "previously_paid": "0.00",     "recommended_this_period": "0.00", "status": "approved", "sort_order": 26},
    {"description": "Variations",                                 "contractor_claim_to_date": "0.00",     "total_recommended": "0.00",      "previously_paid": "0.00",     "recommended_this_period": "0.00", "status": "approved", "sort_order": 27},
]

EXPECTED_HISTORY_ROW_COUNT = 28
# Total = 28 history + 25 per-item contract work rows
EXPECTED_ASSESSMENT_2_LINE_ITEM_COUNT = 53


# ── Expected assessment 2 provisional sum items ───────────────────────────
# History carrier rows only (claim_line_item_id = NULL).
# Only PS 3390 (fence) had PR1 activity: approved at 5384.38.
# Per-item rows for all 4 PS items are tested via self-consistency.
EXPECTED_ASSESSMENT_2_PS_HISTORY = [
    {"contractor_claim_to_date": "5384.38", "total_recommended": "5384.38", "previously_paid": "5384.38", "recommended_this_period": "0.00", "status": "approved"},
]

# Total = 1 history + 4 per-item rows
EXPECTED_ASSESSMENT_2_PS_COUNT = 5


# ── Expected assessment 2 variation items ─────────────────────────────────
# History carrier rows only (claim_line_item_id = NULL).
# Only variations with PR1 activity get a history row.
# Var 2 (Manawatu): approved at 10069.49 in PR1
# Var 3 (Cost transfer): approved at 5238.02 in PR1
# Per-item rows for all 6 variations are tested via self-consistency.
EXPECTED_ASSESSMENT_2_VAR_HISTORY = [
    {"contractor_ref": "2", "contractor_claim_to_date": "10069.49", "total_recommended": "10069.49", "previously_paid": "10069.49", "recommended_this_period": "0.00", "status": "approved"},
    {"contractor_ref": "3", "contractor_claim_to_date": "5238.02",  "total_recommended": "5238.02",  "previously_paid": "5238.02",  "recommended_this_period": "0.00", "status": "approved"},
]

# Total = 2 history + 6 per-item rows
EXPECTED_ASSESSMENT_2_VAR_COUNT = 8


# ── PR2 approval data ──────────────────────────────────────────────────────
# QS adjustments for Claim 2 to match PR No. 2.
# Contract works and PS items are accepted at auto values.
# Variation 3 is reduced by 2,156.80 (from 36,590.97 to 34,434.17).
PR2_VAR3_RECOMMENDED = "34434.17"


# ── Expected finalised assessment 2 summary (PR2 totals) ──────────────────
# Calculated using Python Decimal with ROUND_HALF_UP for retention.
# These may differ by ±0.01 from the PDF (which used different rounding).
ASSESSMENT_2_EXPECTED = {
    "contract_sum": "4172492.92",
    "total_recommended": "255950.85",      # 188212.29 + 5384.38 + 62354.18
    "total_retention": "22797.54",         # 10% of 200k + 5% of 55950.85
    "total_payment_to_date": "233153.31",  # 255950.85 - 22797.54
    "previously_certified": "61728.65",    # from PR1
    "recommended_this_period": "171424.66", # 233153.31 - 61728.65
}
