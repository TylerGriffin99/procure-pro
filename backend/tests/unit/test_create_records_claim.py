import uuid
from decimal import Decimal

from app.constants.enums import ClaimItemType
from app.harness.executors.create_records.claim import claim_line_values
from app.harness.schemas import ClaimLinks, ParsedClaimItem, VpsLinks

USER = uuid.uuid4()


def test_claim_line_values_parses_money_and_attaches_links():
    wbs_id, ps_id = uuid.uuid4(), uuid.uuid4()
    links = ClaimLinks(
        wbs={0: wbs_id}, vps=VpsLinks(variations={}, provisional_sums={1: ps_id}), confidence={0: Decimal("0.9")}
    )
    cw = ParsedClaimItem(item_index=0, ref_code="1.1", description="Dig", contract_value="1,000.00", current="(5)")
    ps = ParsedClaimItem(item_index=1, item_type=ClaimItemType.provisional_sum, contract_value="bad")

    first = claim_line_values(0, cw, links, USER)
    second = claim_line_values(1, ps, links, USER)

    assert (first.contract_value, first.current, first.balance) == (Decimal("1000.00"), Decimal("-5"), Decimal("0"))
    assert (first.suggested_wbs_code_id, first.categorisation_confidence, first.sort_order) == (
        wbs_id,
        Decimal("0.9"),
        0,
    )
    assert (second.provisional_sum_id, second.contract_value, second.categorisation_confidence) == (
        ps_id,
        Decimal("0"),
        Decimal("0"),
    )
