"""Characterisation: pins today's assessment/claim service behaviour, defects included."""

from decimal import Decimal

import pytest
from sqlalchemy import select

from app.exceptions import BadRequestError, ConflictError
from app.models.assessment import AdjustmentType, AssessmentStatus, LineItemStatus
from app.models.assessment_line_item import AssessmentLineItem
from app.models.assessment_provisional_sum import AssessmentProvisionalSum
from app.models.assessment_variation import AssessmentVariation
from app.models.provisional_sum import ProvisionalSum
from app.models.variation import Variation, VariationStatus
from app.schemas.assessment import (
    AssessmentCreate,
    CloseOutRequest,
    InterimAdjustRequest,
    ReclassifyNewRecord,
    ReclassifyRequest,
)
from app.services import assessment_service, claim_service
from tests.integration.characterisation_fixtures import (
    CLAIMED_TO_DATE,
    RECOMMENDED,
    add_line_item,
    add_provisional_sum_item,
    add_variation_item,
    rows_of,
    seed_assessment,
    seed_claim,
    seed_project,
    seed_provisional_sum,
    seed_scenario,
    seed_user,
    seed_variation,
)

XLSX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


# --- version numbering (D10: max(version) + 1) ---


async def test_second_assessment_today_gets_version_two(db_session):
    user = await seed_user(db_session)
    project = await seed_project(db_session, user)
    claim, _ = await seed_claim(db_session, project, user)
    await db_session.commit()
    data = AssessmentCreate(claim_id=claim.id)

    first = await assessment_service.create_assessment(db_session, project.id, data, user)
    second = await assessment_service.create_assessment(db_session, project.id, data, user)

    assert (first.version, second.version) == (1, 2)


async def test_third_assessment_gets_version_three(db_session):
    user = await seed_user(db_session)
    project = await seed_project(db_session, user)
    claim, _ = await seed_claim(db_session, project, user)
    await db_session.commit()
    data = AssessmentCreate(claim_id=claim.id)
    await assessment_service.create_assessment(db_session, project.id, data, user)
    await assessment_service.create_assessment(db_session, project.id, data, user)

    third = await assessment_service.create_assessment(db_session, project.id, data, user)

    assert third.version == 3


# --- export ---


async def _scenario_with_masters(db):
    s = await seed_scenario(db)
    variation = await seed_variation(db, s.project, s.user)
    ps = await seed_provisional_sum(db, s.project, s.user)
    await add_variation_item(db, s.assessment, variation, s.user, None, comments="Interim - awaiting docs")
    await add_provisional_sum_item(db, s.assessment, ps, s.user, None, is_closed_out=True, comments="Closed Out")
    await db.commit()
    return s, variation, ps


async def test_export_pdf_today(db_session):
    s, _, _ = await _scenario_with_masters(db_session)
    export = await assessment_service.generate_assessment_export(db_session, s.project.id, s.assessment.id, "pdf")
    assert export.content.startswith(b"%PDF")
    assert export.media_type == "application/pdf"


async def test_export_excel_today(db_session):
    s, _, _ = await _scenario_with_masters(db_session)
    export = await assessment_service.generate_assessment_export(db_session, s.project.id, s.assessment.id, "excel")
    assert export.content.startswith(b"PK")
    assert export.media_type == XLSX_MEDIA_TYPE


async def test_export_unknown_format_today_falls_back_to_pdf(db_session):
    s = await seed_scenario(db_session)
    export = await assessment_service.generate_assessment_export(db_session, s.project.id, s.assessment.id, "csv")
    assert export.content.startswith(b"%PDF")
    assert export.media_type == "application/pdf"


# --- finalise / revert ---


async def test_finalise_recomputes_every_persisted_total_and_rolls_up_masters(db_session):
    s, variation, ps = await _scenario_with_masters(db_session)

    result = await assessment_service.finalise_assessment(db_session, s.project.id, s.assessment.id, s.user)

    assert result.status == AssessmentStatus.finalised
    assert result.finalised_at is not None
    assert result.contract_sum == Decimal("1000000.00")
    assert result.total_recommended == RECOMMENDED * 3
    assert result.total_retention == Decimal("2400.00")
    assert result.total_payment_to_date == Decimal("21600.00")
    assert result.recommended_this_period == Decimal("21600.00")
    assert result.adjusted_contract_sum == Decimal("1016000.00")
    assert result.value_claimed_to_date == Decimal("30000.00")
    assert result.adjustments == Decimal("-6000.00")
    assert result.gst_amount == Decimal("3240.00")
    assert result.total_including_gst == Decimal("24840.00")
    await db_session.refresh(variation)
    await db_session.refresh(ps)
    assert variation.status == VariationStatus.unapproved
    assert variation.approved_amount == RECOMMENDED
    assert ps.status == VariationStatus.unapproved
    assert ps.approved_amount == RECOMMENDED


async def test_revert_to_draft_today(db_session):
    s = await seed_scenario(db_session)
    await assessment_service.finalise_assessment(db_session, s.project.id, s.assessment.id, s.user)

    result = await assessment_service.revert_to_draft(db_session, s.project.id, s.assessment.id, s.user)

    assert result.status == AssessmentStatus.draft
    assert result.finalised_at is None


async def test_revert_draft_today_is_bad_request(db_session):
    s = await seed_scenario(db_session)
    with pytest.raises(BadRequestError, match="Assessment is not finalised"):
        await assessment_service.revert_to_draft(db_session, s.project.id, s.assessment.id, s.user)


async def test_revert_with_subsequent_claim_today_conflicts(db_session):
    s = await seed_scenario(db_session)
    await assessment_service.finalise_assessment(db_session, s.project.id, s.assessment.id, s.user)
    await seed_claim(db_session, s.project, s.user, claim_number=2)
    await db_session.commit()

    with pytest.raises(ConflictError, match="a subsequent claim exists"):
        await assessment_service.revert_to_draft(db_session, s.project.id, s.assessment.id, s.user)


# --- reclassify: the seven kind->kind paths not in tests/unit/test_reclassify.py ---


async def _source(db, s, kind):
    if kind == "line-item":
        return s.line_item
    await db.delete(s.line_item)
    if kind == "variation":
        master = await seed_variation(db, s.project, s.user, 7)
        row = await add_variation_item(db, s.assessment, master, s.user, s.cli.id)
    else:
        master = await seed_provisional_sum(db, s.project, s.user, 7)
        row = await add_provisional_sum_item(db, s.assessment, master, s.user, s.cli.id)
    await db.commit()
    return row


_ROW_MODEL = {
    "line-item": AssessmentLineItem,
    "variation": AssessmentVariation,
    "provisional-sum": AssessmentProvisionalSum,
}


@pytest.mark.parametrize(
    ("source_type", "target_type"),
    [
        ("line-item", "provisional-sum"),
        ("variation", "line-item"),
        ("variation", "variation"),
        ("variation", "provisional-sum"),
        ("provisional-sum", "line-item"),
        ("provisional-sum", "variation"),
        ("provisional-sum", "provisional-sum"),
    ],
)
async def test_reclassify_today_moves_row_and_carries_values(db_session, source_type, target_type):
    s = await seed_scenario(db_session)
    source_id = (await _source(db_session, s, source_type)).id
    cli_id, wbs_b_id = s.cli.id, s.wbs_b.id
    req = ReclassifyRequest(
        source_item_id=source_id,
        source_type=source_type,
        target_type=target_type,
        target_wbs_code_id=wbs_b_id,
        new_record=ReclassifyNewRecord(description="Moved"),
    )

    await assessment_service.reclassify_item(db_session, s.project.id, s.assessment.id, req, s.user)

    remaining = await rows_of(db_session, _ROW_MODEL[source_type], s.assessment.id)
    assert source_id not in {r.id for r in remaining}
    [target] = await rows_of(db_session, _ROW_MODEL[target_type], s.assessment.id)
    assert target.id != source_id
    assert target.claim_line_item_id == cli_id
    assert target.contractor_claim_to_date == CLAIMED_TO_DATE
    assert target.total_recommended == RECOMMENDED
    assert target.recommended_this_period == RECOMMENDED
    assert target.variance_to_claim == RECOMMENDED - CLAIMED_TO_DATE
    assert target.previously_paid == Decimal("0")
    assert target.percentage == Decimal("0")
    assert target.status == LineItemStatus.unapproved
    if target_type == "line-item":
        assert target.wbs_code_id == wbs_b_id
        assert target.description == "Concrete Works"
    elif target_type == "variation":
        master = await db_session.get(Variation, target.variation_id)
        assert (master.description, master.contractor_submission) == ("Moved", Decimal("50000.00"))
    else:
        master = await db_session.get(ProvisionalSum, target.provisional_sum_id)
        assert (master.description, master.contract_sum) == ("Moved", Decimal("50000.00"))


# --- close-out / interim adjustment ---


async def test_close_out_line_item_today(db_session):
    s = await seed_scenario(db_session)
    history = await add_line_item(
        db_session, s.assessment, s.wbs_a, s.user, None, comments="Interim - pending", sort_order=1
    )
    bare = await add_line_item(db_session, s.assessment, s.wbs_a, s.user, None, comments=None, sort_order=2)
    plain = await add_line_item(db_session, s.assessment, s.wbs_a, s.user, None, comments="note", sort_order=3)
    done = await add_line_item(db_session, s.assessment, s.wbs_a, s.user, None, comments="Closed Out", sort_order=4)
    other = await add_line_item(db_session, s.assessment, s.wbs_b, s.user, None, comments="untouched", sort_order=5)
    await db_session.commit()

    await assessment_service.close_out_item(
        db_session, s.project.id, s.assessment.id, CloseOutRequest(item_type="line-item", parent_id=s.wbs_a.id), s.user
    )

    rows = {r.id: r for r in await rows_of(db_session, AssessmentLineItem, s.assessment.id)}
    for row_id in (s.line_item.id, history.id, bare.id, plain.id, done.id):
        assert rows[row_id].status == LineItemStatus.approved
        assert rows[row_id].is_closed_out is True
    assert rows[s.line_item.id].comments is None  # claim-linked rows keep their comment
    assert rows[history.id].comments == "Closed Out - pending"
    assert rows[bare.id].comments == "Closed Out"
    assert rows[plain.id].comments == "Closed Out - note"
    assert rows[done.id].comments == "Closed Out"
    assert rows[other.id].comments == "untouched"
    assert rows[other.id].is_closed_out is False


@pytest.mark.parametrize("kind", ["variation", "provisional-sum"])
async def test_close_out_master_kinds_today(db_session, kind):
    s = await seed_scenario(db_session)
    if kind == "variation":
        master = await seed_variation(db_session, s.project, s.user)
        row = await add_variation_item(db_session, s.assessment, master, s.user, None, comments="Interim")
    else:
        master = await seed_provisional_sum(db_session, s.project, s.user)
        row = await add_provisional_sum_item(db_session, s.assessment, master, s.user, None, comments="Interim")
    await db_session.commit()

    await assessment_service.close_out_item(
        db_session, s.project.id, s.assessment.id, CloseOutRequest(item_type=kind, parent_id=master.id), s.user
    )

    [after] = await rows_of(db_session, _ROW_MODEL[kind], s.assessment.id)
    assert after.id == row.id
    assert (after.status, after.is_closed_out, after.comments) == (LineItemStatus.approved, True, "Closed Out")


async def test_close_out_on_finalised_today_is_bad_request(db_session):
    s = await seed_scenario(db_session)
    await assessment_service.finalise_assessment(db_session, s.project.id, s.assessment.id, s.user)
    with pytest.raises(BadRequestError, match="must be in draft to close out"):
        await assessment_service.close_out_item(
            db_session,
            s.project.id,
            s.assessment.id,
            CloseOutRequest(item_type="line-item", parent_id=s.wbs_a.id),
            s.user,
        )


async def test_interim_adjustment_line_item_today_nets_off_history(db_session):
    s = await seed_scenario(db_session)
    await add_line_item(
        db_session, s.assessment, s.wbs_a, s.user, None, previously_paid=Decimal("5000"), description="History"
    )
    await db_session.commit()

    await assessment_service.create_interim_adjustment(
        db_session,
        s.project.id,
        s.assessment.id,
        InterimAdjustRequest(item_type="line-item", parent_id=s.wbs_a.id, agreed_total=Decimal("7000"), comments="ok"),
        s.user,
    )

    [adj] = [r for r in await rows_of(db_session, AssessmentLineItem, s.assessment.id) if r.adjustment_type]
    assert adj.adjustment_type == AdjustmentType.interim_adjustment
    assert adj.wbs_code_id == s.wbs_a.id
    assert adj.description == "History"
    assert adj.total_recommended == Decimal("2000")
    assert adj.recommended_this_period == Decimal("2000")
    assert adj.variance_to_claim == Decimal("2000")
    assert adj.status == LineItemStatus.interim
    assert adj.comments == "Interim - ok"
    assert adj.sort_order == 1
    assert adj.source_assessment_id is None


@pytest.mark.parametrize("kind", ["variation", "provisional-sum"])
async def test_interim_adjustment_master_kinds_today_without_history(db_session, kind):
    s = await seed_scenario(db_session)
    if kind == "variation":
        master = await seed_variation(db_session, s.project, s.user)
    else:
        master = await seed_provisional_sum(db_session, s.project, s.user)
    await db_session.commit()

    await assessment_service.create_interim_adjustment(
        db_session,
        s.project.id,
        s.assessment.id,
        InterimAdjustRequest(item_type=kind, parent_id=master.id, agreed_total=Decimal("3000")),
        s.user,
    )

    [adj] = await rows_of(db_session, _ROW_MODEL[kind], s.assessment.id)
    assert adj.adjustment_type == AdjustmentType.interim_adjustment
    assert adj.total_recommended == Decimal("3000")
    assert adj.status == LineItemStatus.interim
    assert adj.comments == "Interim"


async def test_interim_adjustment_sources_previous_finalised_assessment_today(db_session):
    s = await seed_scenario(db_session)
    await assessment_service.finalise_assessment(db_session, s.project.id, s.assessment.id, s.user)
    claim2, _ = await seed_claim(db_session, s.project, s.user, claim_number=2)
    draft = await seed_assessment(db_session, s.project, claim2, s.user)
    await db_session.commit()

    await assessment_service.create_interim_adjustment(
        db_session,
        s.project.id,
        draft.id,
        InterimAdjustRequest(item_type="line-item", parent_id=s.wbs_a.id, agreed_total=Decimal("100")),
        s.user,
    )

    [adj] = await rows_of(db_session, AssessmentLineItem, draft.id)
    assert adj.source_assessment_id == s.assessment.id
    assert adj.description == "Interim adjustment"


# --- list_claims ---


async def test_list_claims_today_reports_latest_assessment_per_claim(db_session):
    s = await seed_scenario(db_session)
    v2 = await seed_assessment(db_session, s.project, s.claim, s.user, version=2, status=AssessmentStatus.finalised)
    claim2, _ = await seed_claim(db_session, s.project, s.user, claim_number=2)
    claim3, _ = await seed_claim(db_session, s.project, s.user, claim_number=3)
    draft2 = await seed_assessment(db_session, s.project, claim2, s.user)
    await db_session.commit()

    claims = await claim_service.list_claims(db_session, s.project.id)

    assert [(c.id, c.assessment_id, c.assessment_status) for c in claims] == [
        (s.claim.id, v2.id, "finalised"),
        (claim2.id, draft2.id, "draft"),
        (claim3.id, None, None),
    ]


# --- delete_claim orphan cleanup ---


async def test_delete_claim_today_cleans_orphan_masters(db_session):
    s = await seed_scenario(db_session)
    orphan_var = await seed_variation(db_session, s.project, s.user, 1)
    kept_var = await seed_variation(db_session, s.project, s.user, 2)
    never_assessed_var = await seed_variation(db_session, s.project, s.user, 3)
    orphan_ps = await seed_provisional_sum(db_session, s.project, s.user, 1)
    kept_ps = await seed_provisional_sum(db_session, s.project, s.user, 2)
    await add_variation_item(db_session, s.assessment, orphan_var, s.user, s.cli.id)
    await add_provisional_sum_item(db_session, s.assessment, orphan_ps, s.user, s.cli.id)
    claim2, _ = await seed_claim(db_session, s.project, s.user, claim_number=2)
    other = await seed_assessment(db_session, s.project, claim2, s.user)
    await add_variation_item(db_session, other, kept_var, s.user, None)
    await add_provisional_sum_item(db_session, other, kept_ps, s.user, None)
    await db_session.commit()

    await claim_service.delete_claim(db_session, s.project.id, s.claim.id)

    var_ids = set(
        (await db_session.execute(select(Variation.id).where(Variation.project_id == s.project.id))).scalars()
    )
    ps_ids = set(
        (await db_session.execute(select(ProvisionalSum.id).where(ProvisionalSum.project_id == s.project.id))).scalars()
    )
    assert var_ids == {kept_var.id}  # a never-assessed project variation is deleted too
    assert never_assessed_var.id not in var_ids
    assert ps_ids == {kept_ps.id}
