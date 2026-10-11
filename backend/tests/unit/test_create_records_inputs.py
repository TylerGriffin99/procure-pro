import logging

import pytest

from app.harness.executors.create_records.inputs import reclassify_provisional_sums, validate_counts
from app.harness.schemas import CreateRecordsInputs, ParsedClaim, ParsedClaimItem, VpsMatch, WbsMatch


def items(*types):
    return [ParsedClaimItem(item_index=i, item_type=t, description=f"item {i}") for i, t in enumerate(types)]


def inputs(line_items, wbs=(), vps=None):
    return CreateRecordsInputs(
        parsed=ParsedClaim(line_items=line_items),
        wbs_matches=[WbsMatch(item_index=i, wbs_code="EX-01", confidence=0.9) for i in wbs],
        vps_matches=None if vps is None else [VpsMatch(item_index=i, item_type="variation", confidence=0.9) for i in vps],
    )


def test_wbs_matches_outside_contract_work_are_dropped():
    result = validate_counts(inputs(items("contract_work", "variation"), wbs=[0, 1], vps=[1]))
    assert [m.item_index for m in result.wbs_matches] == [0]
    assert [m.item_index for m in result.vps_matches] == [1]


def test_wbs_count_mismatch_raises():
    with pytest.raises(ValueError, match="WBS categorisation returned 1 contract_work matches but extraction has 2"):
        validate_counts(inputs(items("contract_work", "contract_work"), wbs=[0]))


def test_empty_wbs_matches_skip_the_count_check():
    assert validate_counts(inputs(items("contract_work"))).wbs_matches == []


def test_vps_count_mismatch_warns_and_keeps_going(caplog):
    with caplog.at_level(logging.WARNING):
        result = validate_counts(inputs(items("variation", "provisional_sum"), vps=[0]))
    assert [m.item_index for m in result.vps_matches] == [0]
    assert "VPS matching returned 1 matches but extraction has 2 variation/PS items" in caplog.text


def test_missing_vps_file_skips_the_vps_check(caplog):
    with caplog.at_level(logging.WARNING):
        assert validate_counts(inputs(items("variation"))).vps_matches is None
    assert caplog.text == ""


@pytest.mark.parametrize(("wbs", "vps", "kind"), [([5], None, "WBS"), ([], [3], "VPS")])
def test_out_of_range_index_raises(wbs, vps, kind):
    with pytest.raises(ValueError, match=f"{kind} match has out-of-range item_index"):
        validate_counts(inputs(items("contract_work", "variation"), wbs=wbs, vps=vps))


def test_validate_counts_returns_new_value():
    original = inputs(items("contract_work", "variation"), wbs=[0, 1])
    validate_counts(original)
    assert len(original.wbs_matches) == 2


def test_provisional_sum_prefix_reclassifies_without_mutating_input():
    parsed = ParsedClaim(
        line_items=[
            ParsedClaimItem(item_index=0, description="Provisional Sum - landscaping"),
            ParsedClaimItem(item_index=1, description="Excavation"),
            ParsedClaimItem(item_index=2, item_type="variation", description="provisional sum looking variation"),
        ]
    )
    result = reclassify_provisional_sums(parsed)
    assert [i.item_type for i in result.line_items] == ["provisional_sum", "contract_work", "variation"]
    assert parsed.line_items[0].item_type == "contract_work"
