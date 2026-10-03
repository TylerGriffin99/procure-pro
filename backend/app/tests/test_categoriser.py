import pytest

from app.utils.categoriser import match_items_to_wbs


def test_match_basic_items():
    wbs_codes = [
        {"code": "04-01", "description": "Demolition"},
        {"code": "04-02", "description": "Bulk Excavation"},
        {"code": "04-04", "description": "Drainage"},
        {"code": "04-05", "description": "Car Park & Yard"},
        {"code": "05-01", "description": "Substructure"},
        {"code": "05-02", "description": "Frame"},
        {"code": "05-07", "description": "External Walls & Exterior Finishes"},
        {"code": "06-14", "description": "Ceiling Finishes"},
        {"code": "06-19", "description": "HVAC"},
        {"code": "06-20", "description": "Fire Protection"},
        {"code": "08-01", "description": "Preliminary & General"},
        {"code": "08-02", "description": "Margin"},
    ]

    claim_items = [
        {"description": "Demolition works", "ref_code": "3160"},
        {"description": "Excavation and siteworks", "ref_code": "3120"},
        {"description": "Structural Steel", "ref_code": "3510"},
        {"description": "Fire Sprinkler Alteration", "ref_code": "4130"},
        {"description": "Scaffolding and Encapsulation", "ref_code": "4065"},
        {"description": "Preliminary and General", "ref_code": "5410"},
        {"description": "Contract Margin", "ref_code": "9000"},
        {"description": "Suspended Ceilings", "ref_code": "4225"},
        {"description": "Relocation of stormwater, sewer and water", "ref_code": "4115"},
        {"description": "Metal wall cladding", "ref_code": "4035"},
    ]

    matches = match_items_to_wbs(claim_items, wbs_codes)

    # Verify key matches
    assert matches["3160"] == "04-01"  # Demolition works -> Demolition
    assert matches["3510"] == "05-02"  # Structural Steel -> Frame
    assert matches["4130"] == "06-20"  # Fire Sprinkler -> Fire Protection
    assert matches["5410"] == "08-01"  # Preliminary and General -> Preliminary & General
    assert matches["9000"] == "08-02"  # Contract Margin -> Margin
    assert matches["4225"] == "06-14"  # Suspended Ceilings -> Ceiling Finishes
    assert matches["4035"] == "05-07"  # Metal wall cladding -> External Walls
