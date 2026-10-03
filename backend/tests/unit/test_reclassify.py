"""Tests for the reclassify_item service function."""
import uuid
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.assessment import Assessment, AssessmentStatus, LineItemStatus
from app.models.assessment_line_item import AssessmentLineItem
from app.models.assessment_variation import AssessmentVariation
from app.models.claim import Claim, ClaimItemType
from app.models.claim_line_item import ClaimLineItem
from app.models.project import Project
from app.models.user import User
from app.models.variation import Variation, VariationStatus
from app.models.wbs_code import WBSCode, WBSLevel
from app.schemas.assessment import ReclassifyRequest, ReclassifyNewRecord
from app.services import assessment_service


async def _seed(db: AsyncSession):
    """Create a minimal project, claim, assessment, and line items for testing."""
    # Pre-generate user ID so we can set created_by on itself
    user_id = uuid.uuid4()
    user = User(
        id=user_id,
        email=f"test-{uuid.uuid4().hex[:8]}@example.com",
        hashed_password="hashed",
        first_name="Test",
        last_name="User",
        created_by=user_id,
    )
    db.add(user)
    await db.flush()

    project = Project(
        name="Test Project",
        client_name="Client",
        contractor_name="Contractor",
        contract_sum=Decimal("1000000"),
        created_by=user.id,
    )
    db.add(project)
    await db.flush()

    wbs_a = WBSCode(
        project_id=project.id, code="A", description="Category A",
        level=WBSLevel.subcategory, sort_order=0, created_by=user.id,
    )
    wbs_b = WBSCode(
        project_id=project.id, code="B", description="Category B",
        level=WBSLevel.subcategory, sort_order=1, created_by=user.id,
    )
    db.add_all([wbs_a, wbs_b])
    await db.flush()

    claim = Claim(
        project_id=project.id, claim_number=1, created_by=user.id,
    )
    db.add(claim)
    await db.flush()

    cli = ClaimLineItem(
        claim_id=claim.id,
        item_type=ClaimItemType.contract_work,
        description="Concrete Works",
        contract_value=Decimal("50000"),
        ptd=Decimal("10000"),
        previous=Decimal("0"),
        current=Decimal("10000"),
        balance=Decimal("40000"),
        percentage=Decimal("20"),
        sort_order=0,
        created_by=user.id,
    )
    db.add(cli)
    await db.flush()

    assessment = Assessment(
        claim_id=claim.id,
        project_id=project.id,
        version=1,
        status=AssessmentStatus.draft,
        created_by=user.id,
    )
    db.add(assessment)
    await db.flush()

    ali = AssessmentLineItem(
        assessment_id=assessment.id,
        claim_line_item_id=cli.id,
        wbs_code_id=wbs_a.id,
        description="Concrete Works",
        contract_sum=Decimal("50000"),
        contractor_claim_to_date=Decimal("10000"),
        total_recommended=Decimal("8000"),
        percentage=Decimal("16"),
        variance_to_claim=Decimal("-2000"),
        previously_paid=Decimal("0"),
        recommended_this_period=Decimal("8000"),
        status=LineItemStatus.unapproved,
        sort_order=0,
        created_by=user.id,
    )
    db.add(ali)
    await db.flush()

    return user, project, claim, cli, assessment, ali, wbs_a, wbs_b


@pytest.mark.asyncio
async def test_reclassify_line_item_to_new_variation(db_session: AsyncSession):
    user, project, claim, cli, assessment, ali, wbs_a, wbs_b = await _seed(db_session)

    req = ReclassifyRequest(
        source_item_id=ali.id,
        source_type="line-item",
        target_type="variation",
        new_record=ReclassifyNewRecord(description="Concrete Works Variation"),
    )

    result = await assessment_service.reclassify_item(
        db_session, project.id, assessment.id, req, user,
    )

    # Source line item should be deleted
    assert len(result.line_items) == 0

    # New variation item should be created
    assert len(result.variation_items) == 1
    av = result.variation_items[0]
    assert av.claim_line_item_id == cli.id
    assert av.contractor_claim_to_date == Decimal("10000")
    assert av.recommended_this_period == Decimal("8000")
    assert av.total_recommended == Decimal("8000")
    assert av.status == LineItemStatus.unapproved
    assert av.previously_paid == Decimal("0")

    # Variation master record should exist
    assert av.variation is not None
    assert av.variation.description == "Concrete Works Variation"
    assert av.variation.ci_number == 1
    assert av.variation.project_id == project.id


@pytest.mark.asyncio
async def test_reclassify_line_item_to_existing_variation(db_session: AsyncSession):
    user, project, claim, cli, assessment, ali, wbs_a, wbs_b = await _seed(db_session)

    # Create an existing variation
    existing_var = Variation(
        project_id=project.id,
        ci_number=5,
        contractor_ref="CI-005",
        description="Existing Variation",
        contractor_submission=Decimal("20000"),
        status=VariationStatus.unapproved,
        created_by=user.id,
    )
    db_session.add(existing_var)
    await db_session.flush()

    # Create an existing assessment variation so the variation is findable
    existing_av = AssessmentVariation(
        assessment_id=assessment.id,
        variation_id=existing_var.id,
        claim_line_item_id=None,  # history row
        contractor_claim_to_date=Decimal("5000"),
        total_recommended=Decimal("4000"),
        percentage=Decimal("20"),
        variance_to_claim=Decimal("-1000"),
        previously_paid=Decimal("4000"),
        recommended_this_period=Decimal("0"),
        status=LineItemStatus.approved,
        created_by=user.id,
    )
    db_session.add(existing_av)
    await db_session.flush()

    req = ReclassifyRequest(
        source_item_id=ali.id,
        source_type="line-item",
        target_type="variation",
        target_id=existing_var.id,
    )

    result = await assessment_service.reclassify_item(
        db_session, project.id, assessment.id, req, user,
    )

    assert len(result.line_items) == 0
    # Should have original history row + new reclassified row
    assert len(result.variation_items) == 2
    new_av = next(av for av in result.variation_items if av.claim_line_item_id == cli.id)
    assert new_av.variation_id == existing_var.id
    assert new_av.contractor_claim_to_date == Decimal("10000")


@pytest.mark.asyncio
async def test_reclassify_rejects_history_row(db_session: AsyncSession):
    user, project, claim, cli, assessment, ali, wbs_a, wbs_b = await _seed(db_session)

    # Create a history row (no claim_line_item_id)
    history_li = AssessmentLineItem(
        assessment_id=assessment.id,
        claim_line_item_id=None,
        wbs_code_id=wbs_a.id,
        description="History Row",
        contract_sum=Decimal("30000"),
        contractor_claim_to_date=Decimal("0"),
        total_recommended=Decimal("0"),
        percentage=Decimal("0"),
        variance_to_claim=Decimal("0"),
        previously_paid=Decimal("5000"),
        recommended_this_period=Decimal("-5000"),
        status=LineItemStatus.approved,
        sort_order=1,
        created_by=user.id,
    )
    db_session.add(history_li)
    await db_session.flush()

    req = ReclassifyRequest(
        source_item_id=history_li.id,
        source_type="line-item",
        target_type="variation",
        new_record=ReclassifyNewRecord(description="Should fail"),
    )

    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc_info:
        await assessment_service.reclassify_item(
            db_session, project.id, assessment.id, req, user,
        )
    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_reclassify_wbs_to_wbs(db_session: AsyncSession):
    user, project, claim, cli, assessment, ali, wbs_a, wbs_b = await _seed(db_session)

    req = ReclassifyRequest(
        source_item_id=ali.id,
        source_type="line-item",
        target_type="line-item",
        target_wbs_code_id=wbs_b.id,
    )

    result = await assessment_service.reclassify_item(
        db_session, project.id, assessment.id, req, user,
    )

    # Line item should still exist, not deleted
    assert len(result.line_items) == 1
    li = result.line_items[0]
    assert li.id == ali.id
    assert li.wbs_code_id == wbs_b.id
    # Values should be unchanged
    assert li.contractor_claim_to_date == Decimal("10000")
    assert li.total_recommended == Decimal("8000")


@pytest.mark.asyncio
async def test_reclassify_roundtrip_line_item_to_ps_and_back(db_session: AsyncSession):
    """Reclassify line-item → new provisional sum, then back → line-item.

    The financial values must transfer correctly in both directions and
    the source row must be deleted each time.
    """
    user, project, claim, cli, assessment, ali, wbs_a, wbs_b = await _seed(db_session)

    # Step 1: line-item → provisional sum
    req1 = ReclassifyRequest(
        source_item_id=ali.id,
        source_type="line-item",
        target_type="provisional-sum",
        target_wbs_code_id=wbs_a.id,
        new_record=ReclassifyNewRecord(description="Provisional sum - Concrete Works"),
    )
    result1 = await assessment_service.reclassify_item(
        db_session, project.id, assessment.id, req1, user,
    )

    # Source line item deleted, PS row created with correct values
    assert len(result1.line_items) == 0
    assert len(result1.provisional_sum_items) == 1
    ps_row = result1.provisional_sum_items[0]
    assert ps_row.claim_line_item_id == cli.id
    assert ps_row.recommended_this_period == Decimal("8000")
    assert ps_row.total_recommended == Decimal("8000")
    assert ps_row.contractor_claim_to_date == Decimal("10000")

    # Step 2: provisional sum → line-item
    req2 = ReclassifyRequest(
        source_item_id=ps_row.id,
        source_type="provisional-sum",
        target_type="line-item",
        target_wbs_code_id=wbs_a.id,
    )
    result2 = await assessment_service.reclassify_item(
        db_session, project.id, assessment.id, req2, user,
    )

    # PS row should be deleted
    assert len(result2.provisional_sum_items) == 0

    # Line item should be recreated with the original financial values
    assert len(result2.line_items) == 1
    li = result2.line_items[0]
    assert li.claim_line_item_id == cli.id
    assert li.recommended_this_period == Decimal("8000")
    assert li.total_recommended == Decimal("8000")
    assert li.contractor_claim_to_date == Decimal("10000")
