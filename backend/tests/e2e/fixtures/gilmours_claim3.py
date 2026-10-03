"""
Expected outputs for Gilmours Central Progress Claim No. 3.

These fixtures define the exact values the system must produce when Claim No. 3
is uploaded after Claims 1 and 2 have been assessed and finalised (matching PR1
and PR2 respectively).

Reference documents:
  - claim/Gilmours/claims/Gilmours Central_Progress Claim No. 3.pdf  (contractor input)
  - claim/Gilmours/payment_recomendations/Gilmours Central Seismic PR No 3 12Nov25.pdf  (desired QS output)
"""

# ── PR2 approval data ──────────────────────────────────────────────────────
# After auto-creating the assessment for Claim 2, the QS approves items to
# match Payment Recommendation No. 2.  Contract works and PS items are
# accepted at auto values.  Variation 3 is reduced.

PR2_VAR3_RECOMMENDED = "34434.17"


# ── Expected finalised assessment 2 summary ────────────────────────────────
# These values carry forward into assessment 3 as previously_certified.
ASSESSMENT_2_EXPECTED = {
    "contract_sum": "4172492.92",
    "total_recommended": "255950.85",
    "total_retention": "22797.54",
    "total_payment_to_date": "233153.31",
    "previously_certified": "61728.65",
    "recommended_this_period": "171424.66",
}


# ── Expected claim 3 line items ────────────────────────────────────────────
EXPECTED_CLAIM_3_ITEM_COUNT = 44  # 25 contract + 4 PS + 15 variations

# fmt: off
EXPECTED_CLAIM_3_LINE_ITEMS = [
    # Contract work (25 items)
    {"item_type": "contract_work",   "ref_code": "3120", "description": "Excavation and siteworks",                        "contract_value": "64504.78",   "ptd": "9244.00",      "previous": "0.00",       "current": "9244.00",    "balance": "55260.78"},
    {"item_type": "contract_work",   "ref_code": "3160", "description": "Demolition works",                                "contract_value": "120480.00",  "ptd": "0.00",         "previous": "0.00",       "current": "0.00",       "balance": "120480.00"},
    {"item_type": "contract_work",   "ref_code": "3210", "description": "Concrete and Formwork",                           "contract_value": "256840.78",  "ptd": "9759.95",      "previous": "0.00",       "current": "9759.95",    "balance": "247080.83"},
    {"item_type": "contract_work",   "ref_code": "3230", "description": "Pile Drilling",                                   "contract_value": "62257.00",   "ptd": "62257.00",     "previous": "0.00",       "current": "62257.00",   "balance": "0.00"},
    {"item_type": "contract_work",   "ref_code": "3350", "description": "Ply barrier under birdcage",                      "contract_value": "22500.00",   "ptd": "3450.00",      "previous": "0.00",       "current": "3450.00",    "balance": "19050.00"},
    {"item_type": "contract_work",   "ref_code": "3420", "description": "Reinforcing steel",                               "contract_value": "104865.35",  "ptd": "50258.40",     "previous": "0.00",       "current": "50258.40",   "balance": "54606.95"},
    {"item_type": "contract_work",   "ref_code": "3510", "description": "Structural Steel",                                "contract_value": "1184000.00", "ptd": "0.00",         "previous": "0.00",       "current": "0.00",       "balance": "1184000.00"},
    {"item_type": "contract_work",   "ref_code": "3730", "description": "Alum joinery and automatic doors",                "contract_value": "8344.00",    "ptd": "0.00",         "previous": "0.00",       "current": "0.00",       "balance": "8344.00"},
    {"item_type": "contract_work",   "ref_code": "3855", "description": "Temporary fencing and hoarding",                  "contract_value": "40160.00",   "ptd": "7650.00",      "previous": "0.00",       "current": "7650.00",    "balance": "32510.00"},
    {"item_type": "contract_work",   "ref_code": "4010", "description": "Removal and reinstatement of PIR panels",         "contract_value": "27944.00",   "ptd": "0.00",         "previous": "0.00",       "current": "0.00",       "balance": "27944.00"},
    {"item_type": "contract_work",   "ref_code": "4035", "description": "Metal wall cladding",                             "contract_value": "47537.47",   "ptd": "0.00",         "previous": "0.00",       "current": "0.00",       "balance": "47537.47"},
    {"item_type": "contract_work",   "ref_code": "4065", "description": "Scaffolding and Encapsulation",                   "contract_value": "893343.50",  "ptd": "105000.00",    "previous": "0.00",       "current": "105000.00",  "balance": "788343.50"},
    {"item_type": "contract_work",   "ref_code": "4115", "description": "Relocation of stormwater, sewer and water",       "contract_value": "156773.92",  "ptd": "124535.00",    "previous": "124535.00",  "current": "0.00",       "balance": "32238.92"},
    {"item_type": "contract_work",   "ref_code": "4120", "description": "Removal and reinstatement of aircon units",       "contract_value": "14298.00",   "ptd": "0.00",         "previous": "0.00",       "current": "0.00",       "balance": "14298.00"},
    {"item_type": "contract_work",   "ref_code": "4125", "description": "Removal and reinstatement of chiller units",      "contract_value": "6490.25",    "ptd": "0.00",         "previous": "0.00",       "current": "0.00",       "balance": "6490.25"},
    {"item_type": "contract_work",   "ref_code": "4130", "description": "Fire Sprinkler Alteration",                       "contract_value": "200000.00",  "ptd": "11003.61",     "previous": "0.00",       "current": "11003.61",   "balance": "188996.39"},
    {"item_type": "contract_work",   "ref_code": "4165", "description": "Temporary lighting below birdcage",               "contract_value": "35429.00",   "ptd": "0.00",         "previous": "0.00",       "current": "0.00",       "balance": "35429.00"},
    {"item_type": "contract_work",   "ref_code": "4225", "description": "Suspended Ceilings",                              "contract_value": "68026.70",   "ptd": "0.00",         "previous": "0.00",       "current": "0.00",       "balance": "68026.70"},
    {"item_type": "contract_work",   "ref_code": "4325", "description": "Concrete driveway - 200mm thick",                 "contract_value": "30800.00",   "ptd": "0.00",         "previous": "0.00",       "current": "0.00",       "balance": "30800.00"},
    {"item_type": "contract_work",   "ref_code": "4355", "description": "Asphalt prep and hotmix",                         "contract_value": "24860.00",   "ptd": "0.00",         "previous": "0.00",       "current": "0.00",       "balance": "24860.00"},
    {"item_type": "contract_work",   "ref_code": "5020", "description": "Temporary office - in store",                     "contract_value": "37607.20",   "ptd": "0.00",         "previous": "0.00",       "current": "0.00",       "balance": "37607.20"},
    {"item_type": "contract_work",   "ref_code": "5040", "description": "Temporary Driveway",                              "contract_value": "50565.00",   "ptd": "35395.50",     "previous": "35395.50",   "current": "0.00",       "balance": "15169.50"},
    {"item_type": "contract_work",   "ref_code": "5090", "description": "Temporary ablution blocks, office and lunchroom",  "contract_value": "54865.97",   "ptd": "11837.77",     "previous": "8281.79",    "current": "3555.98",    "balance": "43028.20"},
    {"item_type": "contract_work",   "ref_code": "5410", "description": "Preliminary and General",                         "contract_value": "250000.00",  "ptd": "18750.00",     "previous": "10000.00",   "current": "8750.00",    "balance": "231250.00"},
    {"item_type": "contract_work",   "ref_code": "9000", "description": "Contract Margin",                                 "contract_value": "250000.00",  "ptd": "18750.00",     "previous": "10000.00",   "current": "8750.00",    "balance": "231250.00"},
    # Provisional sums (4 items)
    {"item_type": "provisional_sum", "ref_code": "3390", "description": "Provisional sum - Removal and reinstatement of fen", "contract_value": "15000.00", "ptd": "5384.38",      "previous": "5384.38",    "current": "0.00",       "balance": "9615.62"},
    {"item_type": "provisional_sum", "ref_code": "3810", "description": "Provisional sum - Carpentry General",             "contract_value": "80000.00",   "ptd": "2454.38",      "previous": "0.00",       "current": "2454.38",    "balance": "77545.62"},
    {"item_type": "provisional_sum", "ref_code": "4810", "description": "Provisional sum - Remedial works to interior walls", "contract_value": "25000.00", "ptd": "0.00",         "previous": "0.00",       "current": "0.00",       "balance": "25000.00"},
    {"item_type": "provisional_sum", "ref_code": "4850", "description": "Provisional sum - Services",                      "contract_value": "40000.00",   "ptd": "0.00",         "previous": "0.00",       "current": "0.00",       "balance": "40000.00"},
    # Variations (15 items)
    {"item_type": "variation",       "ref_code": "1",    "description": "(U) Birdnetting in ambient area",                 "contract_value": "11169.55",   "ptd": "11169.55",     "previous": "0.00",       "current": "11169.55",   "balance": "0.00"},
    {"item_type": "variation",       "ref_code": "2",    "description": "(U) Manawatu security fencing",                   "contract_value": "10069.49",   "ptd": "10069.49",     "previous": "10069.49",   "current": "0.00",       "balance": "0.00"},
    {"item_type": "variation",       "ref_code": "3",    "description": "(U) Cost transfer from extension contract",       "contract_value": "47328.73",   "ptd": "36590.97",     "previous": "36590.97",   "current": "0.00",       "balance": "10737.76"},
    {"item_type": "variation",       "ref_code": "4",    "description": "(U) Move mechanical duct - as requested by ops team", "contract_value": "1476.09", "ptd": "1476.09",      "previous": "1476.09",    "current": "0.00",       "balance": "0.00"},
    {"item_type": "variation",       "ref_code": "5",    "description": "(U) Tidy existing cabling in canopy area",        "contract_value": "4322.01",    "ptd": "4322.01",      "previous": "4322.01",    "current": "0.00",       "balance": "0.00"},
    {"item_type": "variation",       "ref_code": "6",    "description": "(U) Additional excavation - Temporary driveway",  "contract_value": "10974.02",   "ptd": "10974.02",     "previous": "9895.62",    "current": "1078.40",    "balance": "0.00"},
    {"item_type": "variation",       "ref_code": "7",    "description": "(U) Remove existing roof static line",            "contract_value": "231.00",     "ptd": "231.00",       "previous": "0.00",       "current": "231.00",     "balance": "0.00"},
    {"item_type": "variation",       "ref_code": "8",    "description": "(U) Structural steel - Construction drawing changes", "contract_value": "102009.77", "ptd": "0.00",       "previous": "0.00",       "current": "0.00",       "balance": "102009.77"},
    {"item_type": "variation",       "ref_code": "9",    "description": "(U) Silvester Clark - Temporary Propping Design", "contract_value": "1896.51",    "ptd": "1896.51",      "previous": "0.00",       "current": "1896.51",    "balance": "0.00"},
    {"item_type": "variation",       "ref_code": "10",   "description": "(U) Earthing - Kiosk",                            "contract_value": "2401.07",    "ptd": "0.00",         "previous": "0.00",       "current": "0.00",       "balance": "2401.07"},
    {"item_type": "variation",       "ref_code": "11",   "description": "(U) Septic tank cleaning",                        "contract_value": "2842.33",    "ptd": "2842.33",      "previous": "0.00",       "current": "2842.33",    "balance": "0.00"},
    {"item_type": "variation",       "ref_code": "12",   "description": "(U) Additional excavation - Terra Civil",         "contract_value": "47682.90",   "ptd": "47682.90",     "previous": "0.00",       "current": "47682.90",   "balance": "0.00"},
    {"item_type": "variation",       "ref_code": "13",   "description": "(U) Temporary road maintenance",                  "contract_value": "3228.22",    "ptd": "3228.22",      "previous": "0.00",       "current": "3228.22",    "balance": "0.00"},
    {"item_type": "variation",       "ref_code": "14",   "description": "(U) Additional grating and steel for roof platform", "contract_value": "12092.77", "ptd": "0.00",        "previous": "0.00",       "current": "0.00",       "balance": "12092.77"},
    {"item_type": "variation",       "ref_code": "15",   "description": "(U) Footing - Additional width excavated",        "contract_value": "16952.61",   "ptd": "16952.61",     "previous": "0.00",       "current": "16952.61",   "balance": "0.00"},
]
# fmt: on


# ── Expected auto-created assessment 3 line items ──────────────────────────
# These are the values BEFORE QS review, auto-calculated from claim 3 data
# and the finalised assessment 2.  previously_paid comes from assessment 2
# total_recommended for each WBS subcategory.
# fmt: off
EXPECTED_ASSESSMENT_3_LINE_ITEMS = [
    {"description": "Demolition existing structure",              "contract_sum": "120480.00",  "contractor_claim_to_date": "0.00",      "total_recommended": "0.00",       "previously_paid": "0.00",       "recommended_this_period": "0.00",       "status": "approved",    "sort_order": 0},
    {"description": "Removal and reinstatement of PIR",           "contract_sum": "27944.00",   "contractor_claim_to_date": "0.00",      "total_recommended": "0.00",       "previously_paid": "0.00",       "recommended_this_period": "0.00",       "status": "approved",    "sort_order": 1},
    {"description": "Removal and reinstatement of chiller units", "contract_sum": "6490.25",    "contractor_claim_to_date": "0.00",      "total_recommended": "0.00",       "previously_paid": "0.00",       "recommended_this_period": "0.00",       "status": "approved",    "sort_order": 2},
    {"description": "Temp lighting to birdcage - setup",          "contract_sum": "14297.75",   "contractor_claim_to_date": "0.00",      "total_recommended": "0.00",       "previously_paid": "0.00",       "recommended_this_period": "0.00",       "status": "approved",    "sort_order": 3},
    {"description": "Bulk Excavation",                            "contract_sum": "64504.78",   "contractor_claim_to_date": "9244.00",   "total_recommended": "9244.00",    "previously_paid": "0.00",       "recommended_this_period": "9244.00",    "status": "unapproved",  "sort_order": 4},
    {"description": "Relocation of stormwater, sewer and water",  "contract_sum": "156773.92",  "contractor_claim_to_date": "124535.00",  "total_recommended": "124535.00",  "previously_paid": "124535.00",  "recommended_this_period": "0.00",       "status": "unapproved",  "sort_order": 5},
    {"description": "Concrete driveway",                          "contract_sum": "30800.00",   "contractor_claim_to_date": "0.00",      "total_recommended": "0.00",       "previously_paid": "0.00",       "recommended_this_period": "0.00",       "status": "approved",    "sort_order": 6},
    {"description": "Asphalt prep and hotmix",                    "contract_sum": "24860.00",   "contractor_claim_to_date": "0.00",      "total_recommended": "0.00",       "previously_paid": "0.00",       "recommended_this_period": "0.00",       "status": "approved",    "sort_order": 7},
    {"description": "General substructure works",                 "contract_sum": "256840.78",  "contractor_claim_to_date": "9759.95",   "total_recommended": "9759.95",    "previously_paid": "0.00",       "recommended_this_period": "9759.95",    "status": "unapproved",  "sort_order": 8},
    {"description": "Pile drilling",                              "contract_sum": "62257.00",   "contractor_claim_to_date": "62257.00",  "total_recommended": "62257.00",   "previously_paid": "0.00",       "recommended_this_period": "62257.00",   "status": "unapproved",  "sort_order": 9},
    {"description": "Reinforcing steel",                          "contract_sum": "104865.35",  "contractor_claim_to_date": "50258.40",  "total_recommended": "50258.40",   "previously_paid": "0.00",       "recommended_this_period": "50258.40",   "status": "unapproved",  "sort_order": 10},
    {"description": "Steel",                                      "contract_sum": "1184000.00", "contractor_claim_to_date": "0.00",      "total_recommended": "0.00",       "previously_paid": "0.00",       "recommended_this_period": "0.00",       "status": "approved",    "sort_order": 11},
    {"description": "Works to external walls",                    "contract_sum": "47537.47",   "contractor_claim_to_date": "0.00",      "total_recommended": "0.00",       "previously_paid": "0.00",       "recommended_this_period": "0.00",       "status": "approved",    "sort_order": 12},
    {"description": "Redecoration",                               "contract_sum": "18344.00",   "contractor_claim_to_date": "0.00",      "total_recommended": "0.00",       "previously_paid": "0.00",       "recommended_this_period": "0.00",       "status": "approved",    "sort_order": 13},
    {"description": "Suspended ceilings",                         "contract_sum": "68026.70",   "contractor_claim_to_date": "0.00",      "total_recommended": "0.00",       "previously_paid": "0.00",       "recommended_this_period": "0.00",       "status": "approved",    "sort_order": 14},
    {"description": "Removal and reinstatement of aircon units",  "contract_sum": "14298.00",   "contractor_claim_to_date": "0.00",      "total_recommended": "0.00",       "previously_paid": "0.00",       "recommended_this_period": "0.00",       "status": "approved",    "sort_order": 15},
    {"description": "Fire Sprinkler Alteration",                  "contract_sum": "200000.00",  "contractor_claim_to_date": "11003.61",  "total_recommended": "11003.61",   "previously_paid": "0.00",       "recommended_this_period": "11003.61",   "status": "unapproved",  "sort_order": 16},
    {"description": "General",                                    "contract_sum": "250000.00",  "contractor_claim_to_date": "18750.00",  "total_recommended": "18750.00",   "previously_paid": "10000.00",   "recommended_this_period": "8750.00",    "status": "unapproved",  "sort_order": 17},
    {"description": "Temp fencing and hoarding",                  "contract_sum": "40160.00",   "contractor_claim_to_date": "7650.00",   "total_recommended": "7650.00",    "previously_paid": "0.00",       "recommended_this_period": "7650.00",    "status": "unapproved",  "sort_order": 18},
    {"description": "Scaffolding and Encapsulation",              "contract_sum": "893343.50",  "contractor_claim_to_date": "105000.00", "total_recommended": "105000.00",  "previously_paid": "0.00",       "recommended_this_period": "105000.00",  "status": "unapproved",  "sort_order": 19},
    {"description": "Ply barriers to birdcage",                   "contract_sum": "22500.00",   "contractor_claim_to_date": "3450.00",   "total_recommended": "3450.00",    "previously_paid": "0.00",       "recommended_this_period": "3450.00",    "status": "unapproved",  "sort_order": 20},
    {"description": "Temp ablution blocks",                       "contract_sum": "54865.97",   "contractor_claim_to_date": "11837.77",  "total_recommended": "11837.77",   "previously_paid": "8281.79",    "recommended_this_period": "3555.98",    "status": "unapproved",  "sort_order": 21},
    {"description": "Temp office",                                "contract_sum": "37607.20",   "contractor_claim_to_date": "0.00",      "total_recommended": "0.00",       "previously_paid": "0.00",       "recommended_this_period": "0.00",       "status": "approved",    "sort_order": 22},
    {"description": "Temp driveway",                              "contract_sum": "50565.00",   "contractor_claim_to_date": "35395.50",  "total_recommended": "35395.50",   "previously_paid": "35395.50",   "recommended_this_period": "0.00",       "status": "unapproved",  "sort_order": 23},
    {"description": "Temp lighting to birdcage - setup",          "contract_sum": "21131.25",   "contractor_claim_to_date": "0.00",      "total_recommended": "0.00",       "previously_paid": "0.00",       "recommended_this_period": "0.00",       "status": "approved",    "sort_order": 24},
    {"description": "General Margin",                             "contract_sum": "250000.00",  "contractor_claim_to_date": "18750.00",  "total_recommended": "18750.00",   "previously_paid": "10000.00",   "recommended_this_period": "8750.00",    "status": "unapproved",  "sort_order": 25},
    {"description": "Provisional Sums",                           "contract_sum": "150000.00",  "contractor_claim_to_date": "0.00",      "total_recommended": "0.00",       "previously_paid": "0.00",       "recommended_this_period": "0.00",       "status": "approved",    "sort_order": 26},
    {"description": "Variations",                                 "contract_sum": "0.00",       "contractor_claim_to_date": "0.00",      "total_recommended": "0.00",       "previously_paid": "0.00",       "recommended_this_period": "0.00",       "status": "approved",    "sort_order": 27},
]
# fmt: on

EXPECTED_ASSESSMENT_3_LINE_ITEM_COUNT = 28


# ── Expected assessment 3 provisional sum items ───────────────────────────
# PS1 (fence): previously_paid=5384.38 from PR2, current=0 -> total_rec=5384.38
# PS2 (carpentry): previously_paid=0, current=2454.38 -> total_rec=2454.38
# fmt: off
EXPECTED_ASSESSMENT_3_PS_ITEMS = [
    {"contractor_claim_to_date": "0.00",    "total_recommended": "0.00",    "previously_paid": "0.00",    "recommended_this_period": "0.00",    "status": "approved"},
    {"contractor_claim_to_date": "0.00",    "total_recommended": "0.00",    "previously_paid": "0.00",    "recommended_this_period": "0.00",    "status": "approved"},
    {"contractor_claim_to_date": "2454.38", "total_recommended": "2454.38", "previously_paid": "0.00",    "recommended_this_period": "2454.38", "status": "unapproved"},
    {"contractor_claim_to_date": "5384.38", "total_recommended": "5384.38", "previously_paid": "5384.38", "recommended_this_period": "0.00",    "status": "unapproved"},
]
# fmt: on

EXPECTED_ASSESSMENT_3_PS_COUNT = 4


# ── Expected assessment 3 variation items ─────────────────────────────────
# Existing variations carry forward previously_paid from PR2.
# New variations (7-15) have previously_paid=0.
# Var 3: previously_paid=34434.17 (QS-reduced in PR2), total_rec=34434.17 (prev+0 current)
# Var 6: previously_paid=12052.42 (PR2), total_rec=13130.82 (prev+1078.40 current)
# fmt: off
EXPECTED_ASSESSMENT_3_VAR_ITEMS = [
    {"contractor_ref": "1",  "contractor_claim_to_date": "11169.55",  "total_recommended": "11169.55",  "previously_paid": "0.00",      "recommended_this_period": "11169.55",  "status": "unapproved"},
    {"contractor_ref": "2",  "contractor_claim_to_date": "10069.49",  "total_recommended": "10069.49",  "previously_paid": "10069.49",  "recommended_this_period": "0.00",      "status": "unapproved"},
    {"contractor_ref": "3",  "contractor_claim_to_date": "36590.97",  "total_recommended": "34434.17",  "previously_paid": "34434.17",  "recommended_this_period": "0.00",      "status": "unapproved"},
    {"contractor_ref": "4",  "contractor_claim_to_date": "1476.09",   "total_recommended": "1476.09",   "previously_paid": "1476.09",   "recommended_this_period": "0.00",      "status": "unapproved"},
    {"contractor_ref": "5",  "contractor_claim_to_date": "4322.01",   "total_recommended": "4322.01",   "previously_paid": "4322.01",   "recommended_this_period": "0.00",      "status": "unapproved"},
    {"contractor_ref": "6",  "contractor_claim_to_date": "10974.02",  "total_recommended": "13130.82",  "previously_paid": "12052.42",  "recommended_this_period": "1078.40",   "status": "unapproved"},
    {"contractor_ref": "7",  "contractor_claim_to_date": "231.00",    "total_recommended": "231.00",    "previously_paid": "0.00",      "recommended_this_period": "231.00",    "status": "unapproved"},
    {"contractor_ref": "8",  "contractor_claim_to_date": "0.00",      "total_recommended": "0.00",      "previously_paid": "0.00",      "recommended_this_period": "0.00",      "status": "approved"},
    {"contractor_ref": "9",  "contractor_claim_to_date": "1896.51",   "total_recommended": "1896.51",   "previously_paid": "0.00",      "recommended_this_period": "1896.51",   "status": "unapproved"},
    {"contractor_ref": "10", "contractor_claim_to_date": "0.00",      "total_recommended": "0.00",      "previously_paid": "0.00",      "recommended_this_period": "0.00",      "status": "approved"},
    {"contractor_ref": "11", "contractor_claim_to_date": "2842.33",   "total_recommended": "2842.33",   "previously_paid": "0.00",      "recommended_this_period": "2842.33",   "status": "unapproved"},
    {"contractor_ref": "12", "contractor_claim_to_date": "47682.90",  "total_recommended": "47682.90",  "previously_paid": "0.00",      "recommended_this_period": "47682.90",  "status": "unapproved"},
    {"contractor_ref": "13", "contractor_claim_to_date": "3228.22",   "total_recommended": "3228.22",   "previously_paid": "0.00",      "recommended_this_period": "3228.22",   "status": "unapproved"},
    {"contractor_ref": "14", "contractor_claim_to_date": "0.00",      "total_recommended": "0.00",      "previously_paid": "0.00",      "recommended_this_period": "0.00",      "status": "approved"},
    {"contractor_ref": "15", "contractor_claim_to_date": "16952.61",  "total_recommended": "16952.61",  "previously_paid": "0.00",      "recommended_this_period": "16952.61",  "status": "unapproved"},
]
# fmt: on

EXPECTED_ASSESSMENT_3_VAR_COUNT = 15


# ── PR3 approval data ──────────────────────────────────────────────────────
# QS adjustments for Claim 3 to match PR No. 3.
# Contract works and PS items are accepted at auto values.
# Variations 11, 12, and 15 are reduced to 80% of claimed (paid on account).
PR3_VAR11_RECOMMENDED = "2273.86"
PR3_VAR12_RECOMMENDED = "38146.32"
PR3_VAR15_RECOMMENDED = "13562.09"


# ── Expected finalised assessment 3 summary (PR3 totals) ──────────────────
# Calculated using Python Decimal with ROUND_HALF_UP for retention.
# These may differ by +/-0.01 from the PDF (which used different rounding).
ASSESSMENT_3_EXPECTED = {
    "contract_sum": "4172492.92",
    "total_recommended": "609670.12",       # 467891.23 + 7838.76 + 133940.13
    "total_retention": "40483.51",          # 10% of 200k + 5% of 409670.12
    "total_payment_to_date": "569186.61",   # 609670.12 - 40483.51
    "previously_certified": "233153.31",    # from PR2 total_payment_to_date
    "recommended_this_period": "336033.30", # 569186.61 - 233153.31
}
