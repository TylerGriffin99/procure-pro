"""
Paparoa Fire Station — project setup and expected outputs for Claim 1.

This is a NON-WBPRO format claim (generic). The harness uses LLM extraction
for Phase 2 instead of the deterministic WBPRO parser.

Contract: Paparoa rural fire station
Client: Fire & Emergency New Zealand
Contractor: Guyco Construction Ltd
"""

# ── WBS codes ──────────────────────────────────────────────────────────────
# fmt: off
WBS_CODES = [
    # Categories
    {"code": "PG", "description": "Preliminaries & General",       "level": "category", "sort_order": 0},
    {"code": "DM", "description": "Demolition & Excavation",       "level": "category", "sort_order": 10},
    {"code": "ST", "description": "Structure",                     "level": "category", "sort_order": 20},
    {"code": "EN", "description": "Enclosure",                     "level": "category", "sort_order": 30},
    {"code": "IN", "description": "Interior",                      "level": "category", "sort_order": 40},
    {"code": "FN", "description": "Finishes",                      "level": "category", "sort_order": 50},
    {"code": "SV", "description": "Services",                      "level": "category", "sort_order": 60},
    {"code": "SW", "description": "Site Works",                    "level": "category", "sort_order": 70},
    {"code": "MG", "description": "Margin",                        "level": "category", "sort_order": 80},
    {"code": "PS", "description": "Provisional Sums",              "level": "category", "sort_order": 90},
    {"code": "VR", "description": "Variations",                    "level": "category", "sort_order": 100},

    # Subcategories — Preliminaries & General
    {"code": "PG-01", "description": "Preliminaries",                    "parent_code": "PG", "sort_order": 1,  "contract_sum": "71254.00"},

    # Subcategories — Demolition & Excavation
    {"code": "DM-01", "description": "Demolition",                       "parent_code": "DM", "sort_order": 11, "contract_sum": "1250.00"},
    {"code": "DM-02", "description": "Excavation",                       "parent_code": "DM", "sort_order": 12, "contract_sum": "45750.00"},

    # Subcategories — Structure
    {"code": "ST-01", "description": "Concrete",                         "parent_code": "ST", "sort_order": 21, "contract_sum": "128809.00"},
    {"code": "ST-02", "description": "Steel reinforcement",              "parent_code": "ST", "sort_order": 22, "contract_sum": "38896.00"},
    {"code": "ST-03", "description": "Structural steel and metalwork",   "parent_code": "ST", "sort_order": 23, "contract_sum": "56400.00"},
    {"code": "ST-04", "description": "Carpentry",                        "parent_code": "ST", "sort_order": 24, "contract_sum": "159161.00"},
    {"code": "ST-05", "description": "Insulation",                       "parent_code": "ST", "sort_order": 25, "contract_sum": "4670.00"},

    # Subcategories — Enclosure
    {"code": "EN-01", "description": "Roofing and wall cladding",        "parent_code": "EN", "sort_order": 31, "contract_sum": "61625.00"},
    {"code": "EN-02", "description": "Aluminium windows and doors",      "parent_code": "EN", "sort_order": 32, "contract_sum": "23085.00"},
    {"code": "EN-03", "description": "Appliance bay doors",              "parent_code": "EN", "sort_order": 33, "contract_sum": "88000.00"},
    {"code": "EN-04", "description": "Aluminium roller shutter",         "parent_code": "EN", "sort_order": 34, "contract_sum": "7660.00"},

    # Subcategories — Interior
    {"code": "IN-01", "description": "Plasterboard linings and stopping", "parent_code": "IN", "sort_order": 41, "contract_sum": "22610.00"},
    {"code": "IN-02", "description": "Invibe linings",                    "parent_code": "IN", "sort_order": 42, "contract_sum": "11604.00"},
    {"code": "IN-03", "description": "Joinery - cabinetry",              "parent_code": "IN", "sort_order": 43, "contract_sum": "37842.00"},
    {"code": "IN-04", "description": "Joinery - timber doors",           "parent_code": "IN", "sort_order": 44, "contract_sum": "29971.00"},
    {"code": "IN-05", "description": "Suspended ceiling",                "parent_code": "IN", "sort_order": 45, "contract_sum": "15600.00"},

    # Subcategories — Finishes
    {"code": "FN-01", "description": "Floor coverings",                  "parent_code": "FN", "sort_order": 51, "contract_sum": "20927.00"},
    {"code": "FN-02", "description": "Painting",                         "parent_code": "FN", "sort_order": 52, "contract_sum": "25330.00"},

    # Subcategories — Services
    {"code": "SV-01", "description": "Plumbing",                         "parent_code": "SV", "sort_order": 61, "contract_sum": "36465.00"},
    {"code": "SV-02", "description": "Drainage",                         "parent_code": "SV", "sort_order": 62, "contract_sum": "105740.00"},
    {"code": "SV-03", "description": "Mechanical services",              "parent_code": "SV", "sort_order": 63, "contract_sum": "68425.00"},
    {"code": "SV-04", "description": "Electrical services",              "parent_code": "SV", "sort_order": 64, "contract_sum": "104482.00"},
    {"code": "SV-05", "description": "Fire protection",                  "parent_code": "SV", "sort_order": 65, "contract_sum": "19857.00"},
    {"code": "SV-06", "description": "Data",                             "parent_code": "SV", "sort_order": 66, "contract_sum": "7400.00"},
    {"code": "SV-07", "description": "Security",                         "parent_code": "SV", "sort_order": 67, "contract_sum": "8920.00"},

    # Subcategories — Site Works
    {"code": "SW-01", "description": "Site works",                       "parent_code": "SW", "sort_order": 71, "contract_sum": "67898.00"},
    {"code": "SW-02", "description": "Perimeter timber fencing",         "parent_code": "SW", "sort_order": 72, "contract_sum": "18564.00"},
    {"code": "SW-03", "description": "Station signage",                  "parent_code": "SW", "sort_order": 73, "contract_sum": "6885.00"},
    {"code": "SW-04", "description": "Siren pole",                       "parent_code": "SW", "sort_order": 74, "contract_sum": "9250.00"},
    {"code": "SW-05", "description": "Motorised gates",                  "parent_code": "SW", "sort_order": 75, "contract_sum": "17500.00"},

    # Subcategories — Margin
    {"code": "MG-01", "description": "Contractor's margin",              "parent_code": "MG", "sort_order": 81, "contract_sum": "39654.90"},

    # Subcategories — PS and VR (aggregate placeholders)
    {"code": "PS-01", "description": "Provisional Sums",                 "parent_code": "PS", "sort_order": 91, "contract_sum": "112000.00"},
    {"code": "VR-01", "description": "Variations",                       "parent_code": "VR", "sort_order": 101, "contract_sum": "0.00"},
]
# fmt: on


# ── Project setup ──────────────────────────────────────────────────────────
PROJECT = {
    "name": "Paparoa Rural Fire Station",
    "project_number": "PAP-001",
    "client_name": "Fire & Emergency New Zealand",
    "client_contact": "Mal Tipton",
    "contractor_name": "Guyco Construction Ltd",
    "contract_sum": "1473484.90",
    "gst_rate": "0.1500",
    "end_client_name": "Fire & Emergency New Zealand",
    "end_client_representative": "Mal Tipton",
    "end_client_address": "Spark Central, Level 7\n42-52 Willis St\nWellington 6011",
    "provisional_sum_total": "112000.00",
    "retention_tiers": [
        {"tier_order": 1, "percentage": "0.1000", "up_to_amount": None},
    ],
    "wbs_codes": WBS_CODES,
}


# ── Expected values for Claim 1 ───────────────────────────────────────────
EXPECTED_CLAIM_NUMBER = 1
EXPECTED_CONTRACT_WORK_MIN = 28
EXPECTED_CONTRACT_WORK_MAX = 35
EXPECTED_PROVISIONAL_SUM_MIN = 5
EXPECTED_PROVISIONAL_SUM_MAX = 10
EXPECTED_VARIATION_MIN = 3
EXPECTED_VARIATION_MAX = 7
EXPECTED_NONZERO_CONTRACT_ITEMS = 6
