#!/usr/bin/env python3
"""
Seed the Paparoa Fire Station project with WBS codes matching the
payment claim PDF (PC01 AUG25).

Usage:
    python scripts/seed_paparoa.py                     # defaults to localhost:8000
    python scripts/seed_paparoa.py http://localhost:8000
"""

import json
import sys
import urllib.parse
import urllib.request

BASE_URL = sys.argv[1].rstrip("/") if len(sys.argv) > 1 else "http://localhost:8000"

# ── WBS codes ────────────────────────────────────────────────────────────────
# fmt: off
WBS_CODES = [
    # ── Categories ──
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

    # ── Preliminaries & General ──
    {"code": "PG-01", "description": "Preliminaries",                      "parent_code": "PG", "sort_order": 1,  "contract_sum": "71254.00"},

    # ── Demolition & Excavation ──
    {"code": "DM-01", "description": "Demolition",                         "parent_code": "DM", "sort_order": 11, "contract_sum": "1250.00"},
    {"code": "DM-02", "description": "Excavation",                         "parent_code": "DM", "sort_order": 12, "contract_sum": "45750.00"},

    # ── Structure ──
    {"code": "ST-01", "description": "Concrete",                           "parent_code": "ST", "sort_order": 21, "contract_sum": "128809.00"},
    {"code": "ST-02", "description": "Steel reinforcement",                "parent_code": "ST", "sort_order": 22, "contract_sum": "38896.00"},
    {"code": "ST-03", "description": "Structural steel and metalwork",     "parent_code": "ST", "sort_order": 23, "contract_sum": "56400.00"},
    {"code": "ST-04", "description": "Carpentry",                          "parent_code": "ST", "sort_order": 24, "contract_sum": "159161.00"},
    {"code": "ST-05", "description": "Insulation",                         "parent_code": "ST", "sort_order": 25, "contract_sum": "4670.00"},

    # ── Enclosure ──
    {"code": "EN-01", "description": "Roofing and wall cladding",          "parent_code": "EN", "sort_order": 31, "contract_sum": "61625.00"},
    {"code": "EN-02", "description": "Aluminium windows and doors",        "parent_code": "EN", "sort_order": 32, "contract_sum": "23085.00"},
    {"code": "EN-03", "description": "Appliance bay doors",                "parent_code": "EN", "sort_order": 33, "contract_sum": "88000.00"},
    {"code": "EN-04", "description": "Aluminium roller shutter",           "parent_code": "EN", "sort_order": 34, "contract_sum": "7660.00"},

    # ── Interior ──
    {"code": "IN-01", "description": "Plasterboard linings and stopping",  "parent_code": "IN", "sort_order": 41, "contract_sum": "22610.00"},
    {"code": "IN-02", "description": "Invibe linings",                     "parent_code": "IN", "sort_order": 42, "contract_sum": "11604.00"},
    {"code": "IN-03", "description": "Joinery - cabinetry",                "parent_code": "IN", "sort_order": 43, "contract_sum": "37842.00"},
    {"code": "IN-04", "description": "Joinery - timber doors",             "parent_code": "IN", "sort_order": 44, "contract_sum": "29971.00"},
    {"code": "IN-05", "description": "Suspended ceiling",                  "parent_code": "IN", "sort_order": 45, "contract_sum": "15600.00"},

    # ── Finishes ──
    {"code": "FN-01", "description": "Floor coverings",                    "parent_code": "FN", "sort_order": 51, "contract_sum": "20927.00"},
    {"code": "FN-02", "description": "Painting",                           "parent_code": "FN", "sort_order": 52, "contract_sum": "25330.00"},

    # ── Services ──
    {"code": "SV-01", "description": "Plumbing",                           "parent_code": "SV", "sort_order": 61, "contract_sum": "36465.00"},
    {"code": "SV-02", "description": "Drainage",                           "parent_code": "SV", "sort_order": 62, "contract_sum": "105740.00"},
    {"code": "SV-03", "description": "Mechanical services",                "parent_code": "SV", "sort_order": 63, "contract_sum": "68425.00"},
    {"code": "SV-04", "description": "Electrical services",                "parent_code": "SV", "sort_order": 64, "contract_sum": "104482.00"},
    {"code": "SV-05", "description": "Fire protection",                    "parent_code": "SV", "sort_order": 65, "contract_sum": "19857.00"},
    {"code": "SV-06", "description": "Data",                               "parent_code": "SV", "sort_order": 66, "contract_sum": "7400.00"},
    {"code": "SV-07", "description": "Security",                           "parent_code": "SV", "sort_order": 67, "contract_sum": "8920.00"},

    # ── Site Works ──
    {"code": "SW-01", "description": "Site works",                         "parent_code": "SW", "sort_order": 71, "contract_sum": "67898.00"},
    {"code": "SW-02", "description": "Perimeter timber fencing",           "parent_code": "SW", "sort_order": 72, "contract_sum": "18564.00"},
    {"code": "SW-03", "description": "Station signage",                    "parent_code": "SW", "sort_order": 73, "contract_sum": "6885.00"},
    {"code": "SW-04", "description": "Siren pole",                         "parent_code": "SW", "sort_order": 74, "contract_sum": "9250.00"},
    {"code": "SW-05", "description": "Motorised gates",                    "parent_code": "SW", "sort_order": 75, "contract_sum": "17500.00"},

    # ── Margin ──
    {"code": "MG-01", "description": "Contractor's margin",                "parent_code": "MG", "sort_order": 81, "contract_sum": "39654.90"},

    # ── Provisional Sums (individual items from PDF) ──
    {"code": "PS-01", "description": "Construction camera",                                   "parent_code": "PS", "sort_order": 91,  "contract_sum": "7000.00"},
    {"code": "PS-02", "description": "Planting and soft landscaping",                          "parent_code": "PS", "sort_order": 92,  "contract_sum": "15000.00"},
    {"code": "PS-03", "description": "Northpower service charges",                             "parent_code": "PS", "sort_order": 93,  "contract_sum": "30000.00"},
    {"code": "PS-04", "description": "Dewatering charges",                                     "parent_code": "PS", "sort_order": 94,  "contract_sum": "5000.00"},
    {"code": "PS-05", "description": "Unforeseen ground conditions",                           "parent_code": "PS", "sort_order": 95,  "contract_sum": "20000.00"},
    {"code": "PS-06", "description": "Unforeseen adjustments to existing underground services", "parent_code": "PS", "sort_order": 96, "contract_sum": "15000.00"},
    {"code": "PS-07", "description": "Draft pump works",                                       "parent_code": "PS", "sort_order": 97,  "contract_sum": "20000.00"},

    # ── Variations ──
    {"code": "VR-01", "description": "Variations",                         "parent_code": "VR", "sort_order": 101, "contract_sum": "0.00"},
]
# fmt: on

# ── Project payload ──────────────────────────────────────────────────────────
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


def get_token():
    form = urllib.parse.urlencode(
        {"username": "tylergriffin70@gmail.com", "password": "Test@123"}
    ).encode()
    req = urllib.request.Request(
        f"{BASE_URL}/api/v1/auth/login",
        data=form,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())["access_token"]


def main():
    token = get_token()
    print("Authenticated.")

    url = f"{BASE_URL}/api/v1/projects"
    data = json.dumps(PROJECT).encode()
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {token}"}
    req = urllib.request.Request(url, data=data, headers=headers)

    try:
        with urllib.request.urlopen(req) as resp:
            body = json.loads(resp.read())
            print(f"Created project: {body['id']}")
            print(f"  Name: {body['name']}")
            print(f"  WBS codes: {len(body.get('wbs_codes', []))}")
            print(f"\nProject ID: {body['id']}")
    except urllib.error.HTTPError as e:
        print(f"HTTP {e.code}: {e.read().decode()}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
