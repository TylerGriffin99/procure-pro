"""
Expected outputs for Gilmours Central Progress Claim No. 1.

These fixtures define the exact values that the harness pipeline must produce.
Fields are keyed by description (for assessment items) or ref_code (for claim items)
since UUIDs are generated fresh each test run.
"""

# ── Expected claim line items ───────────────────────────────────────────────
# Keyed by (item_type, ref_code). Each entry has the deterministic fields.
# fmt: off
EXPECTED_CLAIM_LINE_ITEMS = [
    {"item_type": "contract_work",   "ref_code": "3120", "description": "Excavation and siteworks",                        "contract_value": "64504.78",   "percentage": "0.0000",   "ptd": "0.00",      "previous": "0.00",    "current": "0.00",     "balance": "64504.78"},
    {"item_type": "contract_work",   "ref_code": "3160", "description": "Demolition works",                                "contract_value": "120480.00",  "percentage": "0.0000",   "ptd": "0.00",      "previous": "0.00",    "current": "0.00",     "balance": "120480.00"},
    {"item_type": "contract_work",   "ref_code": "3210", "description": "Concrete and Formwork",                           "contract_value": "256840.78",  "percentage": "0.0000",   "ptd": "0.00",      "previous": "0.00",    "current": "0.00",     "balance": "256840.78"},
    {"item_type": "contract_work",   "ref_code": "3230", "description": "Pile Drilling",                                   "contract_value": "62257.00",   "percentage": "0.0000",   "ptd": "0.00",      "previous": "0.00",    "current": "0.00",     "balance": "62257.00"},
    {"item_type": "contract_work",   "ref_code": "3350", "description": "Ply barrier under birdcage",                      "contract_value": "22500.00",   "percentage": "0.0000",   "ptd": "0.00",      "previous": "0.00",    "current": "0.00",     "balance": "22500.00"},
    {"item_type": "contract_work",   "ref_code": "3420", "description": "Reinforcing steel",                               "contract_value": "104865.35",  "percentage": "0.0000",   "ptd": "0.00",      "previous": "0.00",    "current": "0.00",     "balance": "104865.35"},
    {"item_type": "contract_work",   "ref_code": "3510", "description": "Structural Steel",                                "contract_value": "1184000.00", "percentage": "0.0000",   "ptd": "0.00",      "previous": "0.00",    "current": "0.00",     "balance": "1184000.00"},
    {"item_type": "contract_work",   "ref_code": "3730", "description": "Alum joinery and automatic doors",                "contract_value": "8344.00",    "percentage": "0.0000",   "ptd": "0.00",      "previous": "0.00",    "current": "0.00",     "balance": "8344.00"},
    {"item_type": "contract_work",   "ref_code": "3855", "description": "Temporary fencing and hoarding",                  "contract_value": "40160.00",   "percentage": "0.0000",   "ptd": "0.00",      "previous": "0.00",    "current": "0.00",     "balance": "40160.00"},
    {"item_type": "contract_work",   "ref_code": "4010", "description": "Removal and reinstatement of PIR panels",         "contract_value": "27944.00",   "percentage": "0.0000",   "ptd": "0.00",      "previous": "0.00",    "current": "0.00",     "balance": "27944.00"},
    {"item_type": "contract_work",   "ref_code": "4035", "description": "Metal wall cladding",                             "contract_value": "47537.47",   "percentage": "0.0000",   "ptd": "0.00",      "previous": "0.00",    "current": "0.00",     "balance": "47537.47"},
    {"item_type": "contract_work",   "ref_code": "4065", "description": "Scaffolding and Encapsulation",                   "contract_value": "893343.50",  "percentage": "0.0000",   "ptd": "0.00",      "previous": "0.00",    "current": "0.00",     "balance": "893343.50"},
    {"item_type": "contract_work",   "ref_code": "4115", "description": "Relocation of stormwater, sewer and water",       "contract_value": "156773.92",  "percentage": "0.0000",   "ptd": "0.00",      "previous": "0.00",    "current": "0.00",     "balance": "156773.92"},
    {"item_type": "contract_work",   "ref_code": "4120", "description": "Removal and reinstatement of aircon units",       "contract_value": "14298.00",   "percentage": "0.0000",   "ptd": "0.00",      "previous": "0.00",    "current": "0.00",     "balance": "14298.00"},
    {"item_type": "contract_work",   "ref_code": "4125", "description": "Removal and reinstatement of chiller units",      "contract_value": "6490.25",    "percentage": "0.0000",   "ptd": "0.00",      "previous": "0.00",    "current": "0.00",     "balance": "6490.25"},
    {"item_type": "contract_work",   "ref_code": "4130", "description": "Fire Sprinkler Alteration",                       "contract_value": "200000.00",  "percentage": "0.0000",   "ptd": "0.00",      "previous": "0.00",    "current": "0.00",     "balance": "200000.00"},
    {"item_type": "contract_work",   "ref_code": "4165", "description": "Temporary lighting below birdcage",               "contract_value": "35429.00",   "percentage": "0.0000",   "ptd": "0.00",      "previous": "0.00",    "current": "0.00",     "balance": "35429.00"},
    {"item_type": "contract_work",   "ref_code": "4225", "description": "Suspended Ceilings",                              "contract_value": "68026.70",   "percentage": "0.0000",   "ptd": "0.00",      "previous": "0.00",    "current": "0.00",     "balance": "68026.70"},
    {"item_type": "contract_work",   "ref_code": "4325", "description": "Concrete driveway - 200mm thick",                 "contract_value": "30800.00",   "percentage": "0.0000",   "ptd": "0.00",      "previous": "0.00",    "current": "0.00",     "balance": "30800.00"},
    {"item_type": "contract_work",   "ref_code": "4355", "description": "Asphalt prep and hotmix",                         "contract_value": "24860.00",   "percentage": "0.0000",   "ptd": "0.00",      "previous": "0.00",    "current": "0.00",     "balance": "24860.00"},
    {"item_type": "contract_work",   "ref_code": "5020", "description": "Temporary office - in store",                     "contract_value": "37607.20",   "percentage": "0.0000",   "ptd": "0.00",      "previous": "0.00",    "current": "0.00",     "balance": "37607.20"},
    {"item_type": "contract_work",   "ref_code": "5040", "description": "Temporary Driveway",                              "contract_value": "50565.00",   "percentage": "70.0000",  "ptd": "35395.50",  "previous": "0.00",    "current": "35395.50", "balance": "15169.50"},
    {"item_type": "contract_work",   "ref_code": "5090", "description": "Temporary ablution blocks, office and lunchroom",  "contract_value": "54865.97",   "percentage": "0.0000",   "ptd": "0.00",      "previous": "0.00",    "current": "0.00",     "balance": "54865.97"},
    {"item_type": "contract_work",   "ref_code": "5410", "description": "Preliminary and General",                         "contract_value": "250000.00",  "percentage": "2.5000",   "ptd": "6250.00",   "previous": "0.00",    "current": "6250.00",  "balance": "243750.00"},
    {"item_type": "contract_work",   "ref_code": "9000", "description": "Contract Margin",                                 "contract_value": "250000.00",  "percentage": "2.5000",   "ptd": "6250.00",   "previous": "0.00",    "current": "6250.00",  "balance": "243750.00"},
    {"item_type": "provisional_sum", "ref_code": "3390", "description": "Provisional sum - Removal and reinstatement of fen", "contract_value": "15000.00", "percentage": "47.4300",  "ptd": "7114.38",   "previous": "0.00",    "current": "7114.38",  "balance": "7885.62"},
    {"item_type": "provisional_sum", "ref_code": "3810", "description": "Provisional sum - Carpentry General",             "contract_value": "80000.00",   "percentage": "0.0000",   "ptd": "0.00",      "previous": "0.00",    "current": "0.00",     "balance": "80000.00"},
    {"item_type": "provisional_sum", "ref_code": "4810", "description": "Provisional sum - Remedial works to interior walls", "contract_value": "25000.00", "percentage": "0.0000",   "ptd": "0.00",      "previous": "0.00",    "current": "0.00",     "balance": "25000.00"},
    {"item_type": "provisional_sum", "ref_code": "4850", "description": "Provisional sum - Services",                      "contract_value": "40000.00",   "percentage": "0.0000",   "ptd": "0.00",      "previous": "0.00",    "current": "0.00",     "balance": "40000.00"},
    {"item_type": "variation",       "ref_code": "1",    "description": "(U) Birdnetting in ambient area",                 "contract_value": "11169.55",   "percentage": "0.0000",   "ptd": "0.00",      "previous": "0.00",    "current": "0.00",     "balance": "11169.55"},
    {"item_type": "variation",       "ref_code": "2",    "description": "(U) Manawatu security fencing",                   "contract_value": "10069.49",   "percentage": "100.0000", "ptd": "10069.49",  "previous": "0.00",    "current": "10069.49", "balance": "0.00"},
    {"item_type": "variation",       "ref_code": "3",    "description": "(U) Cost transfer from extension contract",       "contract_value": "194158.11",  "percentage": "2.7000",   "ptd": "5238.02",   "previous": "0.00",    "current": "5238.02",  "balance": "188920.09"},
]
# fmt: on

EXPECTED_CLAIM_ITEM_COUNT = 32


# ── Expected assessment line items ──────────────────────────────────────────
# Keyed by description (matches WBS subcategory description).
# These are deterministic because assessment items map 1:1 to WBS subcategories.
# fmt: off
EXPECTED_ASSESSMENT_LINE_ITEMS = [
    {"description": "Demolition existing structure",              "contract_sum": "120480.00",  "contractor_claim_to_date": "0.00",      "total_recommended": "0.00",      "percentage": "0.0000",   "previously_paid": "0.00", "recommended_this_period": "0.00",      "status": "approved",    "sort_order": 0},
    {"description": "Removal and reinstatement of PIR",           "contract_sum": "27944.00",   "contractor_claim_to_date": "0.00",      "total_recommended": "0.00",      "percentage": "0.0000",   "previously_paid": "0.00", "recommended_this_period": "0.00",      "status": "approved",    "sort_order": 1},
    {"description": "Removal and reinstatement of chiller units", "contract_sum": "6490.25",    "contractor_claim_to_date": "0.00",      "total_recommended": "0.00",      "percentage": "0.0000",   "previously_paid": "0.00", "recommended_this_period": "0.00",      "status": "approved",    "sort_order": 2},
    {"description": "Temp lighting to birdcage - setup",          "contract_sum": "14297.75",   "contractor_claim_to_date": "0.00",      "total_recommended": "0.00",      "percentage": "0.0000",   "previously_paid": "0.00", "recommended_this_period": "0.00",      "status": "approved",    "sort_order": 3},
    {"description": "Bulk Excavation",                            "contract_sum": "64504.78",   "contractor_claim_to_date": "0.00",      "total_recommended": "0.00",      "percentage": "0.0000",   "previously_paid": "0.00", "recommended_this_period": "0.00",      "status": "approved",    "sort_order": 4},
    {"description": "Relocation of stormwater, sewer and water",  "contract_sum": "156773.92",  "contractor_claim_to_date": "0.00",      "total_recommended": "0.00",      "percentage": "0.0000",   "previously_paid": "0.00", "recommended_this_period": "0.00",      "status": "approved",    "sort_order": 5},
    {"description": "Concrete driveway",                          "contract_sum": "30800.00",   "contractor_claim_to_date": "0.00",      "total_recommended": "0.00",      "percentage": "0.0000",   "previously_paid": "0.00", "recommended_this_period": "0.00",      "status": "approved",    "sort_order": 6},
    {"description": "Asphalt prep and hotmix",                    "contract_sum": "24860.00",   "contractor_claim_to_date": "0.00",      "total_recommended": "0.00",      "percentage": "0.0000",   "previously_paid": "0.00", "recommended_this_period": "0.00",      "status": "approved",    "sort_order": 7},
    {"description": "General substructure works",                 "contract_sum": "256840.78",  "contractor_claim_to_date": "0.00",      "total_recommended": "0.00",      "percentage": "0.0000",   "previously_paid": "0.00", "recommended_this_period": "0.00",      "status": "approved",    "sort_order": 8},
    {"description": "Pile drilling",                              "contract_sum": "62257.00",   "contractor_claim_to_date": "0.00",      "total_recommended": "0.00",      "percentage": "0.0000",   "previously_paid": "0.00", "recommended_this_period": "0.00",      "status": "approved",    "sort_order": 9},
    {"description": "Reinforcing steel",                          "contract_sum": "104865.35",  "contractor_claim_to_date": "0.00",      "total_recommended": "0.00",      "percentage": "0.0000",   "previously_paid": "0.00", "recommended_this_period": "0.00",      "status": "approved",    "sort_order": 10},
    {"description": "Steel",                                      "contract_sum": "1184000.00", "contractor_claim_to_date": "0.00",      "total_recommended": "0.00",      "percentage": "0.0000",   "previously_paid": "0.00", "recommended_this_period": "0.00",      "status": "approved",    "sort_order": 11},
    {"description": "Works to external walls",                    "contract_sum": "47537.47",   "contractor_claim_to_date": "0.00",      "total_recommended": "0.00",      "percentage": "0.0000",   "previously_paid": "0.00", "recommended_this_period": "0.00",      "status": "approved",    "sort_order": 12},
    {"description": "Redecoration",                               "contract_sum": "18344.00",   "contractor_claim_to_date": "0.00",      "total_recommended": "0.00",      "percentage": "0.0000",   "previously_paid": "0.00", "recommended_this_period": "0.00",      "status": "approved",    "sort_order": 13},
    {"description": "Suspended ceilings",                         "contract_sum": "68026.70",   "contractor_claim_to_date": "0.00",      "total_recommended": "0.00",      "percentage": "0.0000",   "previously_paid": "0.00", "recommended_this_period": "0.00",      "status": "approved",    "sort_order": 14},
    {"description": "Removal and reinstatement of aircon units",  "contract_sum": "14298.00",   "contractor_claim_to_date": "0.00",      "total_recommended": "0.00",      "percentage": "0.0000",   "previously_paid": "0.00", "recommended_this_period": "0.00",      "status": "approved",    "sort_order": 15},
    {"description": "Fire Sprinkler Alteration",                  "contract_sum": "200000.00",  "contractor_claim_to_date": "0.00",      "total_recommended": "0.00",      "percentage": "0.0000",   "previously_paid": "0.00", "recommended_this_period": "0.00",      "status": "approved",    "sort_order": 16},
    {"description": "General",                                    "contract_sum": "250000.00",  "contractor_claim_to_date": "6250.00",   "total_recommended": "6250.00",   "percentage": "2.5000",   "previously_paid": "0.00", "recommended_this_period": "6250.00",   "status": "unapproved",  "sort_order": 17},
    {"description": "Temp fencing and hoarding",                  "contract_sum": "40160.00",   "contractor_claim_to_date": "0.00",      "total_recommended": "0.00",      "percentage": "0.0000",   "previously_paid": "0.00", "recommended_this_period": "0.00",      "status": "approved",    "sort_order": 18},
    {"description": "Scaffolding and Encapsulation",              "contract_sum": "893343.50",  "contractor_claim_to_date": "0.00",      "total_recommended": "0.00",      "percentage": "0.0000",   "previously_paid": "0.00", "recommended_this_period": "0.00",      "status": "approved",    "sort_order": 19},
    {"description": "Ply barriers to birdcage",                   "contract_sum": "22500.00",   "contractor_claim_to_date": "0.00",      "total_recommended": "0.00",      "percentage": "0.0000",   "previously_paid": "0.00", "recommended_this_period": "0.00",      "status": "approved",    "sort_order": 20},
    {"description": "Temp ablution blocks",                       "contract_sum": "54865.97",   "contractor_claim_to_date": "0.00",      "total_recommended": "0.00",      "percentage": "0.0000",   "previously_paid": "0.00", "recommended_this_period": "0.00",      "status": "approved",    "sort_order": 21},
    {"description": "Temp office",                                "contract_sum": "37607.20",   "contractor_claim_to_date": "0.00",      "total_recommended": "0.00",      "percentage": "0.0000",   "previously_paid": "0.00", "recommended_this_period": "0.00",      "status": "approved",    "sort_order": 22},
    {"description": "Temp driveway",                              "contract_sum": "50565.00",   "contractor_claim_to_date": "35395.50",  "total_recommended": "35395.50",  "percentage": "70.0000",  "previously_paid": "0.00", "recommended_this_period": "35395.50",  "status": "unapproved",  "sort_order": 23},
    {"description": "Temp lighting to birdcage - setup",          "contract_sum": "21131.25",   "contractor_claim_to_date": "0.00",      "total_recommended": "0.00",      "percentage": "0.0000",   "previously_paid": "0.00", "recommended_this_period": "0.00",      "status": "approved",    "sort_order": 24},
    {"description": "General Margin",                             "contract_sum": "250000.00",  "contractor_claim_to_date": "6250.00",   "total_recommended": "6250.00",   "percentage": "2.5000",   "previously_paid": "0.00", "recommended_this_period": "6250.00",   "status": "unapproved",  "sort_order": 25},
    {"description": "Provisional Sums",                           "contract_sum": "150000.00",  "contractor_claim_to_date": "0.00",      "total_recommended": "0.00",      "percentage": "0.0000",   "previously_paid": "0.00", "recommended_this_period": "0.00",      "status": "approved",    "sort_order": 26},
    {"description": "Variations",                                 "contract_sum": "0.00",       "contractor_claim_to_date": "0.00",      "total_recommended": "0.00",      "percentage": "0.0000",   "previously_paid": "0.00", "recommended_this_period": "0.00",      "status": "approved",    "sort_order": 27},
]
# fmt: on

EXPECTED_ASSESSMENT_LINE_ITEM_COUNT = 28


# ── Expected assessment provisional sum items ───────────────────────────────
# fmt: off
EXPECTED_ASSESSMENT_PS_ITEMS = [
    {"contractor_claim_to_date": "0.00",    "total_recommended": "0.00",    "percentage": "0.0000",   "previously_paid": "0.00", "recommended_this_period": "0.00",    "status": "approved"},
    {"contractor_claim_to_date": "0.00",    "total_recommended": "0.00",    "percentage": "0.0000",   "previously_paid": "0.00", "recommended_this_period": "0.00",    "status": "approved"},
    {"contractor_claim_to_date": "7114.38", "total_recommended": "7114.38", "percentage": "47.4292",  "previously_paid": "0.00", "recommended_this_period": "7114.38", "status": "unapproved"},
    {"contractor_claim_to_date": "0.00",    "total_recommended": "0.00",    "percentage": "0.0000",   "previously_paid": "0.00", "recommended_this_period": "0.00",    "status": "approved"},
]
# fmt: on

EXPECTED_ASSESSMENT_PS_COUNT = 4


# ── Expected assessment variation items ─────────────────────────────────────
# fmt: off
EXPECTED_ASSESSMENT_VAR_ITEMS = [
    {"contractor_claim_to_date": "0.00",     "total_recommended": "0.00",     "percentage": "0.0000",   "previously_paid": "0.00", "recommended_this_period": "0.00",     "status": "approved"},
    {"contractor_claim_to_date": "5238.02",  "total_recommended": "5238.02",  "percentage": "2.6978",   "previously_paid": "0.00", "recommended_this_period": "5238.02",  "status": "unapproved"},
    {"contractor_claim_to_date": "10069.49", "total_recommended": "10069.49", "percentage": "100.0000", "previously_paid": "0.00", "recommended_this_period": "10069.49", "status": "unapproved"},
]
# fmt: on

EXPECTED_ASSESSMENT_VAR_COUNT = 3


# ── WBS codes to create on the project ──────────────────────────────────────
# fmt: off
WBS_CODES = [
    # Categories
    {"code": "DM", "description": "Demolition",                          "level": "category", "sort_order": 0},
    {"code": "DR", "description": "Drainage",                            "level": "category", "sort_order": 10},
    {"code": "CP", "description": "Car Park & Yard",                     "level": "category", "sort_order": 20},
    {"code": "SS", "description": "Substructure",                        "level": "category", "sort_order": 30},
    {"code": "FR", "description": "Frame",                               "level": "category", "sort_order": 40},
    {"code": "EW", "description": "External Walls and Exterior Finishes", "level": "category", "sort_order": 50},
    {"code": "IP", "description": "Internal Partitions & Doors",         "level": "category", "sort_order": 60},
    {"code": "CF", "description": "Ceiling Finishes",                    "level": "category", "sort_order": 70},
    {"code": "HV", "description": "HVAC",                                "level": "category", "sort_order": 80},
    {"code": "FP", "description": "Fire Protection",                     "level": "category", "sort_order": 90},
    {"code": "PL", "description": "Preliminaries",                       "level": "category", "sort_order": 100},
    {"code": "MG", "description": "Margin",                              "level": "category", "sort_order": 110},
    {"code": "PS", "description": "Provisional Sums",                    "level": "category", "sort_order": 120},
    {"code": "VR", "description": "Variations",                          "level": "category", "sort_order": 130},
    # Subcategories
    {"code": "DM-01", "description": "Demolition existing structure",              "parent_code": "DM", "sort_order": 1,   "contract_sum": "120480.00"},
    {"code": "DM-02", "description": "Removal and reinstatement of PIR",           "parent_code": "DM", "sort_order": 2,   "contract_sum": "27944.00"},
    {"code": "DM-03", "description": "Removal and reinstatement of chiller units", "parent_code": "DM", "sort_order": 3,   "contract_sum": "6490.25"},
    {"code": "DM-04", "description": "Temp lighting to birdcage - setup",          "parent_code": "DM", "sort_order": 4,   "contract_sum": "14297.75"},
    {"code": "DM-05", "description": "Bulk Excavation",                            "parent_code": "DM", "sort_order": 5,   "contract_sum": "64504.78"},
    {"code": "DR-01", "description": "Relocation of stormwater, sewer and water",  "parent_code": "DR", "sort_order": 11,  "contract_sum": "156773.92"},
    {"code": "CP-01", "description": "Concrete driveway",                          "parent_code": "CP", "sort_order": 21,  "contract_sum": "30800.00"},
    {"code": "CP-02", "description": "Asphalt prep and hotmix",                    "parent_code": "CP", "sort_order": 22,  "contract_sum": "24860.00"},
    {"code": "SS-01", "description": "General substructure works",                 "parent_code": "SS", "sort_order": 31,  "contract_sum": "256840.78"},
    {"code": "SS-02", "description": "Pile drilling",                              "parent_code": "SS", "sort_order": 32,  "contract_sum": "62257.00"},
    {"code": "SS-03", "description": "Reinforcing steel",                          "parent_code": "SS", "sort_order": 33,  "contract_sum": "104865.35"},
    {"code": "FR-01", "description": "Steel",                                     "parent_code": "FR", "sort_order": 41,  "contract_sum": "1184000.00"},
    {"code": "EW-01", "description": "Works to external walls",                   "parent_code": "EW", "sort_order": 51,  "contract_sum": "47537.47"},
    {"code": "IP-01", "description": "Redecoration",                              "parent_code": "IP", "sort_order": 61,  "contract_sum": "18344.00"},
    {"code": "CF-01", "description": "Suspended ceilings",                        "parent_code": "CF", "sort_order": 71,  "contract_sum": "68026.70"},
    {"code": "HV-01", "description": "Removal and reinstatement of aircon units",  "parent_code": "HV", "sort_order": 81,  "contract_sum": "14298.00"},
    {"code": "FP-01", "description": "Fire Sprinkler Alteration",                 "parent_code": "FP", "sort_order": 91,  "contract_sum": "200000.00"},
    {"code": "PL-01", "description": "General",                                   "parent_code": "PL", "sort_order": 101, "contract_sum": "250000.00"},
    {"code": "PL-02", "description": "Temp fencing and hoarding",                 "parent_code": "PL", "sort_order": 102, "contract_sum": "40160.00"},
    {"code": "PL-03", "description": "Scaffolding and Encapsulation",             "parent_code": "PL", "sort_order": 103, "contract_sum": "893343.50"},
    {"code": "PL-04", "description": "Ply barriers to birdcage",                  "parent_code": "PL", "sort_order": 104, "contract_sum": "22500.00"},
    {"code": "PL-05", "description": "Temp ablution blocks",                      "parent_code": "PL", "sort_order": 105, "contract_sum": "54865.97"},
    {"code": "PL-06", "description": "Temp office",                               "parent_code": "PL", "sort_order": 106, "contract_sum": "37607.20"},
    {"code": "PL-07", "description": "Temp driveway",                             "parent_code": "PL", "sort_order": 107, "contract_sum": "50565.00"},
    {"code": "PL-08", "description": "Temp lighting to birdcage - setup",         "parent_code": "PL", "sort_order": 108, "contract_sum": "21131.25"},
    {"code": "MG-01", "description": "General Margin",                            "parent_code": "MG", "sort_order": 111, "contract_sum": "250000.00"},
    {"code": "PS-01", "description": "Provisional Sums",                          "parent_code": "PS", "sort_order": 121, "contract_sum": "150000.00"},
    {"code": "VR-01", "description": "Variations",                                "parent_code": "VR", "sort_order": 131, "contract_sum": "0.00"},
]
# fmt: on


# ── Project setup ───────────────────────────────────────────────────────────
PROJECT = {
    "name": "Gilmours Central Seismic Strengthening",
    "project_number": "S-02314",
    "client_name": "Foodstuffs North Island",
    "client_contact": "Project Manager",
    "contractor_name": "Kynoch Construction Ltd",
    "contract_sum": "4172492.92",
    "gst_rate": "0.1500",
    "end_client_name": "Foodstuffs North Island",
    "end_client_representative": "Owen Sanders",
    "end_client_address": "Hope River\n251A Main Highway\nEllerslie\nAUCKLAND\n1060",
    "landlord_split_pct": "0.9978",
    "operator_split_pct": "0.0022",
    "provisional_sum_total": "160000.00",
    "retention_tiers": [
        {"tier_order": 1, "percentage": "0.1000", "up_to_amount": "200000.00"},
        {"tier_order": 2, "percentage": "0.0500", "up_to_amount": "800000.00"},
        {"tier_order": 3, "percentage": "0.0175", "up_to_amount": None},
    ],
    "wbs_codes": WBS_CODES,
}
