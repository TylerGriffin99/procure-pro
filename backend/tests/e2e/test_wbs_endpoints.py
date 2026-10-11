"""E2E tests for WBS code create and update operations."""
import uuid
from decimal import Decimal

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_user
from app.exceptions import UnprocessableError
from app.main import app
from app.models.user import User
from app.models.wbs_code import WBSLevel
from app.repos import wbs_code_repo
from app.schemas.project import ProjectCreate, WBSCodeCreate, WBSCodeUpdate
from app.services import project_service


@pytest_asyncio.fixture
async def user(db_session: AsyncSession) -> User:
    user_id = uuid.uuid4()
    user = User(id=user_id, email="test@test.com", hashed_password="x", first_name="Test", last_name="User", created_by=user_id)
    db_session.add(user)
    await db_session.flush()
    return user


@pytest_asyncio.fixture
async def authed_client(client, user):
    """Client with get_current_user overridden to return the test user."""
    app.dependency_overrides[get_current_user] = lambda: user
    yield client
    app.dependency_overrides.pop(get_current_user, None)


@pytest_asyncio.fixture
async def project_with_wbs(db_session: AsyncSession, user: User):
    data = ProjectCreate(
        name="Test Project",
        client_name="Client",
        contractor_name="Contractor",
        contract_sum=Decimal("1000000"),
        wbs_codes=[
            WBSCodeCreate(code="DM", description="Demolition", level="category", sort_order=0),
            WBSCodeCreate(code="DM-01", description="Demo works", level="subcategory", parent_code="DM", sort_order=1, contract_sum=Decimal("50000")),
            WBSCodeCreate(code="FR", description="Frame", level="category", sort_order=10),
        ],
    )
    project = await project_service.create_project(db_session, data, user)
    return project


@pytest.mark.asyncio
async def test_create_wbs_code_category(db_session: AsyncSession, project_with_wbs, user):
    project = project_with_wbs
    data = WBSCodeCreate(
        code="EW",
        description="External Walls",
        level="category",
        sort_order=20,
        contract_sum=Decimal("75000"),
    )
    wbs = await project_service.create_wbs_code(db_session, project.id, data, user)
    assert wbs.code == "EW"
    assert wbs.level == WBSLevel.category
    assert wbs.contract_sum == Decimal("75000")
    assert wbs.project_id == project.id


@pytest.mark.asyncio
async def test_create_wbs_code_subcategory(db_session: AsyncSession, project_with_wbs, user):
    project = project_with_wbs
    dm_cat = next(w for w in project.wbs_codes if w.code == "DM")
    data = WBSCodeCreate(
        code="DM-02",
        description="Removal works",
        level="subcategory",
        parent_id=dm_cat.id,
        sort_order=2,
        contract_sum=Decimal("30000"),
    )
    wbs = await project_service.create_wbs_code(db_session, project.id, data, user)
    assert wbs.code == "DM-02"
    assert wbs.parent_id == dm_cat.id


@pytest.mark.asyncio
async def test_create_wbs_code_duplicate_code_fails(db_session: AsyncSession, project_with_wbs, user):
    project = project_with_wbs
    data = WBSCodeCreate(code="DM", description="Duplicate", level="category", sort_order=99)
    with pytest.raises(UnprocessableError) as exc_info:
        await project_service.create_wbs_code(db_session, project.id, data, user)
    assert exc_info.value.status_code == 422


@pytest.mark.asyncio
async def test_update_wbs_code_not_in_use(db_session: AsyncSession, project_with_wbs, user):
    project = project_with_wbs
    dm_sub = next(w for w in project.wbs_codes if w.code == "DM-01")
    data = WBSCodeUpdate(code="DM-99", description="Updated desc", contract_sum=Decimal("60000"))
    updated = await project_service.update_wbs_code(db_session, project.id, dm_sub.id, data, user)
    assert updated.code == "DM-99"
    assert updated.description == "Updated desc"
    assert updated.contract_sum == Decimal("60000")


@pytest.mark.asyncio
async def test_update_wbs_code_in_use_restricts_code_change(db_session: AsyncSession, project_with_wbs, user):
    """When a WBS code is in use, updating the code field should fail."""
    project = project_with_wbs
    dm_sub = next(w for w in project.wbs_codes if w.code == "DM-01")

    from app.models.claim import Claim
    from app.models.assessment import Assessment
    from app.models.assessment_line_item import AssessmentLineItem

    claim = Claim(
        id=uuid.uuid4(), project_id=project.id, claim_number=1,
        created_by=user.id,
    )
    db_session.add(claim)
    await db_session.flush()

    assessment = Assessment(
        id=uuid.uuid4(), project_id=project.id, claim_id=claim.id,
        created_by=user.id,
    )
    db_session.add(assessment)
    await db_session.flush()

    ali = AssessmentLineItem(
        id=uuid.uuid4(),
        assessment_id=assessment.id,
        wbs_code_id=dm_sub.id,
        description="Test line",
        contract_sum=Decimal("50000"),
        contractor_claim_to_date=Decimal("25000"),
        total_recommended=Decimal("25000"),
        percentage=Decimal("0.5"),
        variance_to_claim=Decimal("0"),
        previously_paid=Decimal("0"),
        recommended_this_period=Decimal("25000"),
        sort_order=0,
        created_by=user.id,
    )
    db_session.add(ali)
    await db_session.flush()

    data = WBSCodeUpdate(code="DM-CHANGED")
    with pytest.raises(UnprocessableError) as exc_info:
        await project_service.update_wbs_code(db_session, project.id, dm_sub.id, data, user)
    assert exc_info.value.status_code == 422


@pytest.mark.asyncio
async def test_update_wbs_code_in_use_allows_contract_sum_and_description(db_session: AsyncSession, project_with_wbs, user):
    """When in use, contract_sum and description should still be editable."""
    project = project_with_wbs
    dm_sub = next(w for w in project.wbs_codes if w.code == "DM-01")

    from app.models.claim import Claim
    from app.models.assessment import Assessment
    from app.models.assessment_line_item import AssessmentLineItem

    claim = Claim(
        id=uuid.uuid4(), project_id=project.id, claim_number=2,
        created_by=user.id,
    )
    db_session.add(claim)
    await db_session.flush()

    assessment = Assessment(
        id=uuid.uuid4(), project_id=project.id, claim_id=claim.id,
        created_by=user.id,
    )
    db_session.add(assessment)
    await db_session.flush()

    ali = AssessmentLineItem(
        id=uuid.uuid4(),
        assessment_id=assessment.id,
        wbs_code_id=dm_sub.id,
        description="Line",
        contract_sum=Decimal("50000"),
        contractor_claim_to_date=Decimal("25000"),
        total_recommended=Decimal("25000"),
        percentage=Decimal("0.5"),
        variance_to_claim=Decimal("0"),
        previously_paid=Decimal("0"),
        recommended_this_period=Decimal("25000"),
        sort_order=0,
        created_by=user.id,
    )
    db_session.add(ali)
    await db_session.flush()

    data = WBSCodeUpdate(contract_sum=Decimal("99999"), description="Updated while in use")
    updated = await project_service.update_wbs_code(db_session, project.id, dm_sub.id, data, user)
    assert updated.contract_sum == Decimal("99999")
    assert updated.description == "Updated while in use"


# ── HTTP-level tests ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_post_wbs_endpoint(authed_client, db_session, user):
    """Test POST /api/v1/projects/:id/wbs via HTTP."""
    data = ProjectCreate(
        name="Route Test",
        client_name="Client",
        contractor_name="Contractor",
        contract_sum=Decimal("500000"),
    )
    project = await project_service.create_project(db_session, data, user)

    resp = await authed_client.post(
        f"/api/v1/projects/{project.id}/wbs",
        json={"code": "NW", "description": "New Work", "level": "category", "sort_order": 0, "contract_sum": "10000.00"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["code"] == "NW"
    assert body["in_use"] is False


@pytest.mark.asyncio
async def test_patch_wbs_endpoint(authed_client, db_session, user):
    """Test PATCH /api/v1/projects/:id/wbs/:wbs_id via HTTP."""
    data = ProjectCreate(
        name="Patch Route Test",
        client_name="Client",
        contractor_name="Contractor",
        contract_sum=Decimal("500000"),
        wbs_codes=[
            WBSCodeCreate(code="AB", description="Alpha Bravo", level="category", sort_order=0, contract_sum=Decimal("20000")),
        ],
    )
    project = await project_service.create_project(db_session, data, user)
    wbs = next(w for w in project.wbs_codes if w.code == "AB")

    resp = await authed_client.patch(
        f"/api/v1/projects/{project.id}/wbs/{wbs.id}",
        json={"contract_sum": "30000.00", "description": "Updated Alpha Bravo"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["contract_sum"] == "30000.00"
    assert body["description"] == "Updated Alpha Bravo"


@pytest.mark.asyncio
async def test_get_project_includes_in_use(authed_client, db_session, user):
    """GET /api/v1/projects/:id should include in_use flag on WBS codes."""
    data = ProjectCreate(
        name="InUse Test",
        client_name="Client",
        contractor_name="Contractor",
        contract_sum=Decimal("500000"),
        wbs_codes=[
            WBSCodeCreate(code="TT", description="Test", level="category", sort_order=0),
        ],
    )
    project = await project_service.create_project(db_session, data, user)

    resp = await authed_client.get(f"/api/v1/projects/{project.id}")
    assert resp.status_code == 200
    body = resp.json()
    wbs = body["wbs_codes"][0]
    assert "in_use" in wbs
    assert wbs["in_use"] is False
