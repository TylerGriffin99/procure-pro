import os
from pathlib import Path

import pytest

from app.utils.pdf_parser import parse_wbpro_claim

CLAIM_1_PATH = Path(__file__).parent.parent.parent.parent / "claim" / "Gilmours" / "claims" / "Gilmours Central_Progress Claim No. 1.pdf"
CLAIM_8_PATH = Path(__file__).parent.parent.parent.parent / "claim" / "Gilmours" / "claims" / "Gilmours Central_Progress Claim No. 8.pdf"


@pytest.mark.skipif(not CLAIM_1_PATH.exists(), reason="Sample PDF not available")
def test_parse_claim_1():
    result = parse_wbpro_claim(str(CLAIM_1_PATH))

    assert result["claim_number"] == 1
    assert result["contractor_name"] == "Kynoch Construction Ltd"
    assert result["project_name"] == "Gilmours Central - Seismic Upgrade"

    contract_items = [i for i in result["line_items"] if i["item_type"] in ("contract_work", "provisional_sum")]
    assert len(contract_items) >= 25  # 29 contract work items across pages 1-2

    variations = [i for i in result["line_items"] if i["item_type"] == "variation"]
    assert len(variations) >= 3  # 3 variation items

    # Spot check: Provisional sum - Removal and reinstatement of fence
    fence = next(i for i in contract_items if "3390" in (i.get("ref_code") or ""))
    assert float(fence["contract_value"]) == 15000.00
    assert float(fence["ptd"]) == 7114.38
    assert float(fence["current"]) == 7114.38

    # Spot check: summary
    assert float(result["summary"]["original_contract_total"]) == 4172492.92
    assert float(result["summary"]["claimed_amount"]) == 66801.52


@pytest.mark.skipif(not CLAIM_8_PATH.exists(), reason="Sample PDF not available")
def test_parse_claim_8():
    result = parse_wbpro_claim(str(CLAIM_8_PATH))

    assert result["claim_number"] == 8

    contract_items = [i for i in result["line_items"] if i["item_type"] in ("contract_work", "provisional_sum")]
    variations = [i for i in result["line_items"] if i["item_type"] == "variation"]

    # Claim 8 has many more variations (30+)
    assert len(variations) >= 25

    # Spot check: Structural Steel
    steel = next(i for i in contract_items if "3510" in (i.get("ref_code") or ""))
    assert float(steel["contract_value"]) == 1184000.00
    assert float(steel["current"]) == 129005.20

    # Summary
    assert float(result["summary"]["claimed_amount"]) == 370302.05
