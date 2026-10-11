import uuid
from decimal import Decimal
from typing import NamedTuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.assessment import Assessment, AssessmentStatus, LineItemStatus
from app.models.assessment_line_item import AssessmentLineItem
from app.models.assessment_provisional_sum import AssessmentProvisionalSum
from app.models.assessment_variation import AssessmentVariation
from app.models.claim import Claim, ClaimItemType
from app.models.claim_line_item import ClaimLineItem
from app.models.project import Project
from app.models.provisional_sum import ProvisionalSum
from app.models.retention_tier import RetentionTier
from app.models.user import User
from app.models.variation import Variation, VariationStatus
from app.models.wbs_code import WBSCode, WBSLevel

CLAIMED_TO_DATE = Decimal("10000")
RECOMMENDED = Decimal("8000")


class Scenario(NamedTuple):
    user: User
    project: Project
    wbs_a: WBSCode
    wbs_b: WBSCode
    claim: Claim
    cli: ClaimLineItem
    assessment: Assessment
    line_item: AssessmentLineItem


async def seed_user(db: AsyncSession) -> User:
    user_id = uuid.uuid4()
    user = User(
        id=user_id,
        email=f"char-{user_id.hex[:8]}@example.com",
        hashed_password="hashed",
        first_name="Char",
        last_name="User",
        created_by=user_id,
    )
    db.add(user)
    await db.flush()
    return user


async def seed_project(db: AsyncSession, user: User) -> Project:
    project = Project(
        name="Characterisation Project",
        client_name="Client",
        contractor_name="Contractor",
        contract_sum=Decimal("1000000"),
        created_by=user.id,
    )
    db.add(project)
    await db.flush()
    db.add(
        RetentionTier(
            project_id=project.id, tier_order=0, percentage=Decimal("0.10"), up_to_amount=None, created_by=user.id
        )
    )
    await db.flush()
    return project


async def seed_wbs(db: AsyncSession, project: Project, user: User, code: str, sort_order: int = 0) -> WBSCode:
    wbs = WBSCode(
        project_id=project.id,
        code=code,
        description=f"Category {code}",
        level=WBSLevel.subcategory,
        sort_order=sort_order,
        created_by=user.id,
    )
    db.add(wbs)
    await db.flush()
    return wbs


async def seed_claim(
    db: AsyncSession, project: Project, user: User, claim_number: int = 1
) -> tuple[Claim, ClaimLineItem]:
    claim = Claim(project_id=project.id, claim_number=claim_number, created_by=user.id)
    db.add(claim)
    await db.flush()
    cli = ClaimLineItem(
        claim_id=claim.id,
        item_type=ClaimItemType.contract_work,
        description="Concrete Works",
        contract_value=Decimal("50000"),
        ptd=CLAIMED_TO_DATE,
        previous=Decimal("0"),
        current=CLAIMED_TO_DATE,
        balance=Decimal("40000"),
        percentage=Decimal("20"),
        sort_order=0,
        created_by=user.id,
    )
    db.add(cli)
    await db.flush()
    return claim, cli


async def seed_assessment(
    db: AsyncSession,
    project: Project,
    claim: Claim,
    user: User,
    version: int = 1,
    status: AssessmentStatus = AssessmentStatus.draft,
) -> Assessment:
    assessment = Assessment(
        claim_id=claim.id, project_id=project.id, version=version, status=status, created_by=user.id
    )
    db.add(assessment)
    await db.flush()
    return assessment


def _row_values(user: User, claim_line_item_id: uuid.UUID | None) -> dict:
    return {
        "claim_line_item_id": claim_line_item_id,
        "contractor_claim_to_date": CLAIMED_TO_DATE,
        "total_recommended": RECOMMENDED,
        "percentage": Decimal("16"),
        "variance_to_claim": RECOMMENDED - CLAIMED_TO_DATE,
        "previously_paid": Decimal("0"),
        "recommended_this_period": RECOMMENDED,
        "status": LineItemStatus.unapproved,
        "created_by": user.id,
    }


async def add_line_item(
    db: AsyncSession,
    assessment: Assessment,
    wbs: WBSCode,
    user: User,
    claim_line_item_id: uuid.UUID | None,
    **overrides,
) -> AssessmentLineItem:
    values = _row_values(user, claim_line_item_id) | {"description": "Concrete Works", "sort_order": 0} | overrides
    row = AssessmentLineItem(assessment_id=assessment.id, wbs_code_id=wbs.id, **values)
    db.add(row)
    await db.flush()
    return row


async def seed_variation(db: AsyncSession, project: Project, user: User, ci_number: int = 1) -> Variation:
    variation = Variation(
        project_id=project.id,
        ci_number=ci_number,
        contractor_ref=f"CI-{ci_number:03d}",
        description=f"Variation {ci_number}",
        contractor_submission=Decimal("20000"),
        status=VariationStatus.unapproved,
        created_by=user.id,
    )
    db.add(variation)
    await db.flush()
    return variation


async def add_variation_item(
    db: AsyncSession,
    assessment: Assessment,
    variation: Variation,
    user: User,
    claim_line_item_id: uuid.UUID | None,
    **overrides,
) -> AssessmentVariation:
    values = _row_values(user, claim_line_item_id) | overrides
    row = AssessmentVariation(assessment_id=assessment.id, variation_id=variation.id, **values)
    db.add(row)
    await db.flush()
    return row


async def seed_provisional_sum(db: AsyncSession, project: Project, user: User, ps_number: int = 1) -> ProvisionalSum:
    ps = ProvisionalSum(
        project_id=project.id,
        ps_number=ps_number,
        description=f"Provisional sum {ps_number}",
        contract_sum=Decimal("30000"),
        status=VariationStatus.unapproved,
        created_by=user.id,
    )
    db.add(ps)
    await db.flush()
    return ps


async def add_provisional_sum_item(
    db: AsyncSession,
    assessment: Assessment,
    ps: ProvisionalSum,
    user: User,
    claim_line_item_id: uuid.UUID | None,
    **overrides,
) -> AssessmentProvisionalSum:
    values = _row_values(user, claim_line_item_id) | overrides
    row = AssessmentProvisionalSum(assessment_id=assessment.id, provisional_sum_id=ps.id, **values)
    db.add(row)
    await db.flush()
    return row


async def seed_scenario(db: AsyncSession) -> Scenario:
    user = await seed_user(db)
    project = await seed_project(db, user)
    wbs_a = await seed_wbs(db, project, user, "A", 0)
    wbs_b = await seed_wbs(db, project, user, "B", 1)
    claim, cli = await seed_claim(db, project, user)
    assessment = await seed_assessment(db, project, claim, user)
    line_item = await add_line_item(db, assessment, wbs_a, user, cli.id)
    await db.commit()
    return Scenario(user, project, wbs_a, wbs_b, claim, cli, assessment, line_item)


async def rows_of[T](db: AsyncSession, model: type[T], assessment_id: uuid.UUID) -> list[T]:
    """Fresh rows from the DB, bypassing the identity map's cached collections."""
    result = await db.execute(
        select(model).where(model.assessment_id == assessment_id).execution_options(populate_existing=True)  # type: ignore[attr-defined]
    )
    return list(result.scalars().all())
