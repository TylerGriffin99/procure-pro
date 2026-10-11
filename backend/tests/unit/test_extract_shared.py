from app.constants.enums import ClaimItemType
from app.harness.extract_shared import extract_metadata, summary_totals
from app.harness.schemas import ParsedClaimItem


def test_extract_metadata_matches_the_claim_no_form():
    text = "CONTRACTOR PROGRESS CLAIM\nClaim No. 5\nPeriod From: 01/10/2025"
    metadata = extract_metadata(text)
    assert metadata.claim_number == "5"
    assert metadata.period_from == "01/10/2025"


def test_extract_metadata_matches_the_claim_number_form():
    assert extract_metadata("Claim Number: 12").claim_number == "12"


def test_extract_metadata_reads_every_field():
    text = "Claim No: 3\nPeriod From - 01/10/2025\nPeriod To: 31/10/2025\nPayment Due: 18/12/2025"
    metadata = extract_metadata(text)
    assert metadata.model_dump() == {
        "claim_number": "3",
        "period_from": "01/10/2025",
        "period_to": "31/10/2025",
        "payment_due": "18/12/2025",
    }


def test_extract_metadata_leaves_missing_fields_unset():
    assert extract_metadata("Nothing useful here").model_dump(exclude_none=True) == {}


def test_summary_totals_sums_contract_work_and_all_items():
    items = [
        ParsedClaimItem(item_index=0, item_type=ClaimItemType.contract_work, contract_value="100.00", ptd="10.00"),
        ParsedClaimItem(item_index=1, item_type=ClaimItemType.variation, contract_value="50.50", ptd="5.25"),
        ParsedClaimItem(item_index=2, item_type=ClaimItemType.provisional_sum, contract_value="20.00", ptd="0.00"),
    ]
    assert summary_totals(items).model_dump(exclude_none=True) == {
        "original_contract_total": "100.00",
        "revised_contract_total": "170.50",
        "claimed_amount": "15.25",
    }


def test_summary_totals_of_nothing_is_zero():
    assert summary_totals([]).model_dump(exclude_none=True) == {
        "original_contract_total": "0.00",
        "revised_contract_total": "0.00",
        "claimed_amount": "0.00",
    }
