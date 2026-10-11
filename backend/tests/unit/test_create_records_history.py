import uuid
from decimal import Decimal
from types import SimpleNamespace

from app.constants.enums import ClaimItemType, LineItemStatus, WBSLevel
from app.harness.executors.create_records.history import build_history
from app.harness.schemas import HistorySource
from app.schemas.assessment_aggregate import AssessmentAggregate

USER = uuid.uuid4()
WBS_ID, VAR_ID, PS_ID = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()


def line(item_type, *, current="0", previous=None, sort_order=0, **links):
    return SimpleNamespace(
        id=uuid.uuid4(),
        item_type=item_type,
        description=f"{item_type} line",
        current=Decimal(current),
        previous=None if previous is None else Decimal(previous),
        sort_order=sort_order,
        suggested_wbs_code_id=links.get("wbs"),
        variation_id=links.get("variation"),
        provisional_sum_id=links.get("ps"),
    )


def group(**fields):
    return SimpleNamespace(
        total_recommended=Decimal(fields.pop("rec")), contractor_claim_to_date=Decimal(fields.pop("claim")), **fields
    )


def source(claim_lines, previous=None, latest=None):
    return HistorySource(
        claim_lines=claim_lines,
        previous=previous,
        latest=latest,
        wbs_codes=[
            SimpleNamespace(
                id=WBS_ID,
                level=WBSLevel.subcategory,
                contract_sum=Decimal("1000"),
                sort_order=0,
                description="Earthworks",
            ),
            SimpleNamespace(
                id=uuid.uuid4(), level=WBSLevel.subcategory, contract_sum=None, sort_order=1, description="No sum"
            ),
            SimpleNamespace(
                id=uuid.uuid4(), level=WBSLevel.category, contract_sum=Decimal("5"), sort_order=2, description="Cat"
            ),
        ],
        variations=[SimpleNamespace(id=VAR_ID, contractor_submission=Decimal("400"))],
        provisional_sums=[SimpleNamespace(id=PS_ID, contract_sum=Decimal("0"))],
        user_id=USER,
    )


def previous_aggregate():
    return AssessmentAggregate.model_construct(
        assessment=None,
        wbs_groups=[group(wbs_code_id=WBS_ID, rec="300", claim="500"), group(wbs_code_id=None, rec="9", claim="9")],
        variation_groups=[group(variation_id=VAR_ID, rec="100", claim="200")],
        ps_groups=[group(provisional_sum_id=PS_ID, rec="50", claim="60")],
    )


def test_first_claim_builds_zero_history_and_current_rows():
    lines = [
        line(ClaimItemType.contract_work, current="70", sort_order=0, wbs=WBS_ID),
        line(ClaimItemType.contract_work, current="0", sort_order=1),
        line(ClaimItemType.variation, current="20", sort_order=2, variation=VAR_ID),
        line(ClaimItemType.provisional_sum, current="5", sort_order=3),
    ]
    rows = build_history(source(lines))

    [wbs_history, cw1, cw2] = rows.line_items
    assert (wbs_history.master_id, wbs_history.sort_order, wbs_history.description) == (WBS_ID, 0, "Earthworks")
    assert wbs_history.total_recommended == Decimal("0") and wbs_history.status == LineItemStatus.approved
    assert (cw1.master_id, cw1.sort_order, cw1.recommended_this_period, cw1.status) == (
        WBS_ID,
        1,
        Decimal("70"),
        LineItemStatus.unapproved,
    )
    assert (cw2.master_id, cw2.sort_order, cw2.status) == (None, 2, LineItemStatus.approved)
    assert [r.claim_line_item_id for r in rows.variation_items] == [None, lines[2].id]
    assert [r.claim_line_item_id for r in rows.provisional_sum_items] == [None]  # unlinked PS line has no row


def test_history_carries_previous_totals_comments_and_contractor_acceptance():
    lines = [
        line(ClaimItemType.contract_work, previous="450", wbs=WBS_ID),
        line(ClaimItemType.variation, previous="250", variation=VAR_ID),
    ]
    latest = SimpleNamespace(
        line_items=[SimpleNamespace(wbs_code_id=WBS_ID, comments="keep", claim_line_item_id=None)],
        variation_items=[SimpleNamespace(variation_id=VAR_ID, comments="linked", claim_line_item_id=uuid.uuid4())],
        provisional_sum_items=[],
    )
    rows = build_history(source(lines, previous_aggregate(), latest))

    wbs_history = rows.line_items[0]
    assert wbs_history.previously_paid == Decimal("300")
    assert wbs_history.contractor_claim_to_date == Decimal("450")  # contractor accepted the lower figure
    assert wbs_history.variance_to_claim == Decimal("-150")
    assert wbs_history.percentage == Decimal("30")
    assert wbs_history.comments == "keep"

    var_history = rows.variation_items[0]
    assert var_history.contractor_claim_to_date == Decimal("200")  # 250 is not lower, so no acceptance
    assert var_history.percentage == Decimal("25")
    assert var_history.comments is None  # claim-linked rows do not carry comments forward

    ps_history = rows.provisional_sum_items[0]
    assert (ps_history.total_recommended, ps_history.percentage) == (Decimal("50"), Decimal("0"))
