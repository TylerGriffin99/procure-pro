# backend/tests/integration/legacy/test_create_records_history.py
"""Tests for create_records.py variation/PS history bug fixes."""

import json
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.constants.enums import FlagSeverity, FlagType
from app.harness.executors.create_records import execute_create_records
from app.models.assessment import Assessment
from app.models.claim_line_item import ClaimLineItem
from app.models.variation import Variation, VariationStatus
from app.repos import harness_repo
from tests.integration.legacy.conftest import list_flags_by_session


def _parsed_claim(items: list[dict], claim_number: str = "2") -> str:
    return json.dumps(
        {
            "metadata": {"claim_number": claim_number},
            "line_items": items,
            "summary": {"original_contract_total": "100000.00", "revised_contract_total": "100000.00"},
        }
    )


def _variation_item(idx: int, ref: str = "CI-01", desc: str = "Var", value: str = "5000.00") -> dict:
    return {
        "item_index": idx,
        "ref_code": ref,
        "description": desc,
        "item_type": "variation",
        "contract_value": value,
        "percentage": "0.00",
        "ptd": "0.00",
        "previous": "0.00",
        "current": "0.00",
        "balance": value,
    }


@pytest.mark.asyncio
async def test_zero_activity_variation_gets_history_row(
    db_session: AsyncSession, test_user, test_project, test_document
):
    """A variation with zero prior activity should still get an assessment row."""
    # Create an existing variation with zero activity (no prior assessment)
    var = Variation(
        project_id=test_project.id,
        ci_number=1,
        contractor_ref="CI-01",
        description="Zero activity var",
        contractor_submission=Decimal("5000.00"),
        status=VariationStatus.unapproved,
        created_by=test_user.id,
    )
    db_session.add(var)
    await db_session.flush()

    # Set up harness session with a claim that includes this variation
    session = await harness_repo.create_session(
        document_id=test_document.id,
        db=db_session,
        user_id=test_user.id,
        project_id=test_project.id,
        harness_type="claim_parse",
    )
    items = [_variation_item(0, ref="CI-01", desc="Zero activity var")]
    await harness_repo.write_workspace_file(db_session, session.id, "parsed_claim.json", _parsed_claim(items))
    await harness_repo.write_workspace_file(db_session, session.id, "wbs_matches.json", json.dumps([]))
    await harness_repo.write_workspace_file(
        db_session,
        session.id,
        "vps_matches.json",
        json.dumps([{"item_index": 0, "item_type": "variation", "matched_id": str(var.id), "confidence": 0.9}]),
    )
    await db_session.flush()

    await execute_create_records(
        db=db_session, session_id=session.id, user_id=test_user.id, project_id=test_project.id, config={}, llm=None
    )

    # The assessment should have variation items — a Phase 1 history row + a Phase 2 current row
    # Eager-load: the identity map holds the executor's Assessment only weakly, so once GC collects it
    # a lazy collection load here would raise MissingGreenlet.
    stmt = (
        select(Assessment)
        .where(Assessment.project_id == test_project.id)
        .options(selectinload(Assessment.variation_items))
    )
    assessment = (await db_session.execute(stmt)).scalars().first()
    assert assessment is not None
    var_items = [vi for vi in assessment.variation_items if vi.variation_id == var.id]
    # Should have at least a history row (Phase 1) — previously this was skipped
    assert len(var_items) >= 1, f"Expected history row for zero-activity variation, got {len(var_items)}"


@pytest.mark.asyncio
async def test_prior_variation_carried_forward_when_not_in_current_claim(
    db_session: AsyncSession, test_user, test_project, test_document
):
    """Variations from prior claims that aren't in the current claim still appear in the assessment."""
    # Create two existing variations
    var_in_claim = Variation(
        project_id=test_project.id,
        ci_number=1,
        contractor_ref="CI-01",
        description="In current claim",
        contractor_submission=Decimal("5000.00"),
        status=VariationStatus.unapproved,
        created_by=test_user.id,
    )
    var_not_in_claim = Variation(
        project_id=test_project.id,
        ci_number=2,
        contractor_ref="CI-02",
        description="Not in current claim",
        contractor_submission=Decimal("3000.00"),
        status=VariationStatus.unapproved,
        created_by=test_user.id,
    )
    db_session.add_all([var_in_claim, var_not_in_claim])
    await db_session.flush()

    # Claim only includes var_in_claim
    session = await harness_repo.create_session(
        document_id=test_document.id,
        db=db_session,
        user_id=test_user.id,
        project_id=test_project.id,
        harness_type="claim_parse",
    )
    items = [_variation_item(0, ref="CI-01", desc="In current claim")]
    await harness_repo.write_workspace_file(db_session, session.id, "parsed_claim.json", _parsed_claim(items))
    await harness_repo.write_workspace_file(db_session, session.id, "wbs_matches.json", json.dumps([]))
    await harness_repo.write_workspace_file(
        db_session,
        session.id,
        "vps_matches.json",
        json.dumps([{"item_index": 0, "item_type": "variation", "matched_id": str(var_in_claim.id), "confidence": 0.9}]),
    )
    await db_session.flush()

    await execute_create_records(
        db=db_session, session_id=session.id, user_id=test_user.id, project_id=test_project.id, config={}, llm=None
    )

    stmt = (
        select(Assessment)
        .where(Assessment.project_id == test_project.id)
        .options(selectinload(Assessment.variation_items))
    )
    assessment = (await db_session.execute(stmt)).scalars().first()
    assert assessment is not None

    # Both variations should have assessment rows
    var_ids_in_assessment = {vi.variation_id for vi in assessment.variation_items}
    assert var_in_claim.id in var_ids_in_assessment, "var_in_claim should be in assessment"
    assert var_not_in_claim.id in var_ids_in_assessment, "var_not_in_claim should be carried forward"


@pytest.mark.asyncio
async def test_malformed_amount_persists_zero_and_records_a_format_warning_flag(
    db_session: AsyncSession, test_user, test_project, test_document
):
    session = await harness_repo.create_session(
        document_id=test_document.id,
        db=db_session,
        user_id=test_user.id,
        project_id=test_project.id,
        harness_type="claim_parse",
    )
    items = [_variation_item(0, ref="CI-09", desc="Malformed var", value="1,2OO.00")]
    await harness_repo.write_workspace_file(db_session, session.id, "parsed_claim.json", _parsed_claim(items))
    await harness_repo.write_workspace_file(db_session, session.id, "wbs_matches.json", json.dumps([]))
    await db_session.flush()

    result = await execute_create_records(
        db=db_session, session_id=session.id, user_id=test_user.id, project_id=test_project.id, config={}, llm=None
    )

    flags = sorted(await list_flags_by_session(db_session, session.id), key=lambda f: f.description)
    assert [(f.flag_type, f.severity, f.line_item_ref) for f in flags] == [
        (FlagType.format_warning, FlagSeverity.warning, "CI-09"),
        (FlagType.format_warning, FlagSeverity.warning, "CI-09"),
    ]
    assert all(f.claim_id == result.claim_id for f in flags)
    assert flags[0].description.startswith("balance:")
    assert flags[1].description.startswith("contract_value:")

    stmt = select(ClaimLineItem).where(ClaimLineItem.claim_id == result.claim_id)
    line = (await db_session.execute(stmt)).scalars().one()
    assert line.contract_value == Decimal("0")


@pytest.mark.asyncio
async def test_draft_totals_come_from_the_aggregator(db_session: AsyncSession, test_user, test_project, test_document):
    session = await harness_repo.create_session(
        document_id=test_document.id,
        db=db_session,
        user_id=test_user.id,
        project_id=test_project.id,
        harness_type="claim_parse",
    )
    items = [{**_variation_item(0, ref="CI-01", desc="New var"), "ptd": "400.00", "current": "400.00"}]
    await harness_repo.write_workspace_file(db_session, session.id, "parsed_claim.json", _parsed_claim(items))
    await db_session.flush()

    result = await execute_create_records(
        db=db_session, session_id=session.id, user_id=test_user.id, project_id=test_project.id, config={}, llm=None
    )

    assessment = await db_session.get(Assessment, result.assessment_id)
    assert assessment is not None
    assert assessment.version == 1
    assert (assessment.total_recommended, assessment.value_claimed_to_date) == (Decimal("400.00"), Decimal("400.00"))
    assert (assessment.approved_variation_orders, assessment.adjustment_to_provisional_sums) == (
        Decimal("400.00"),
        Decimal("0.00"),
    )
    assert assessment.adjusted_contract_sum == Decimal("1000400.00")
    assert assessment.adjustments == Decimal("0.00")
    assert (assessment.gst_amount, assessment.total_including_gst) == (Decimal("60.00"), Decimal("460.00"))
