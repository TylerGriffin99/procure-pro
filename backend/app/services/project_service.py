import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.constants.enums import WBSLevel
from app.exceptions import UnprocessableError, require
from app.models.project import Project
from app.models.user import User
from app.models.wbs_code import WBSCode
from app.repos import (
    assessment_repo,
    claim_repo,
    harness_repo,
    project_repo,
    provisional_sum_repo,
    retention_tier_repo,
    variation_repo,
    wbs_code_repo,
)
from app.schemas.project import ProjectCreate, ProjectUpdate, WBSCodeCreate, WBSCodeUpdate


async def create_project(db: AsyncSession, data: ProjectCreate, user: User, project_id: uuid.UUID | None = None):
    # project_id lets seeds pin a deterministic id; otherwise the model default
    # (uuid4) assigns a random one.
    id_kwargs = {"id": project_id} if project_id is not None else {}
    project = await project_repo.create(
        db,
        **id_kwargs,
        name=data.name,
        project_number=data.project_number,
        client_name=data.client_name,
        client_contact=data.client_contact,
        contractor_name=data.contractor_name,
        contract_sum=data.contract_sum,
        gst_rate=data.gst_rate,
        end_client_name=data.end_client_name,
        end_client_representative=data.end_client_representative,
        end_client_address=data.end_client_address,
        landlord_split_pct=data.landlord_split_pct,
        operator_split_pct=data.operator_split_pct,
        provisional_sum_total=data.provisional_sum_total,
        created_by=user.id,
    )

    for tier in data.retention_tiers:
        await retention_tier_repo.create(db, project_id=project.id, **tier.model_dump(), created_by=user.id)

    # Two-pass WBS code creation
    code_to_wbs: dict[str, WBSCode] = {}

    # Pass 1: categories
    for wbs in data.wbs_codes:
        if wbs.level == WBSLevel.category:
            wbs_obj = await wbs_code_repo.create(
                db,
                project_id=project.id,
                code=wbs.code,
                description=wbs.description,
                level=WBSLevel.category,
                sort_order=wbs.sort_order,
                contract_sum=wbs.contract_sum,
                created_by=user.id,
            )
            code_to_wbs[wbs.code] = wbs_obj

    # Pass 2: subcategories
    for wbs in data.wbs_codes:
        if wbs.level == WBSLevel.subcategory:
            parent = code_to_wbs.get(wbs.parent_code) if wbs.parent_code else None
            await wbs_code_repo.create(
                db,
                project_id=project.id,
                code=wbs.code,
                description=wbs.description,
                level=WBSLevel.subcategory,
                sort_order=wbs.sort_order,
                parent_id=parent.id if parent else None,
                contract_sum=wbs.contract_sum,
                created_by=user.id,
            )

    await db.commit()

    # Reload with eager loading
    return await project_repo.get_by_id(db, project.id)


async def list_projects(db: AsyncSession):
    return await project_repo.get_all(db)


async def get_project(db: AsyncSession, project_id: uuid.UUID):
    project = require(await project_repo.get_by_id(db, project_id), "Project")

    # Populate in_use flag for each WBS code (single batch query)
    all_wbs = await wbs_code_repo.get_by_project(db, project_id)
    in_use_ids = await wbs_code_repo.get_in_use_ids(db, [wbs.id for wbs in all_wbs])
    for wbs in all_wbs:
        wbs.in_use = wbs.id in in_use_ids

    return project


async def update_project(db: AsyncSession, project_id: uuid.UUID, data: ProjectUpdate, user: User) -> Project:
    project = require(await project_repo.get_by_id(db, project_id), "Project")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(project, field, value)

    project.updated_by = user.id
    await db.commit()
    await db.refresh(project)
    return project


async def delete_project(db: AsyncSession, project_id: uuid.UUID) -> None:
    project = require(await project_repo.get_by_id(db, project_id), "Project")

    await harness_repo.delete_sessions_by_project(db, project_id)
    await assessment_repo.delete_by_project(db, project_id)
    await claim_repo.delete_by_project(db, project_id)
    await variation_repo.delete_by_project(db, project_id)
    await provisional_sum_repo.delete_by_project(db, project_id)

    await db.delete(project)
    await db.commit()


async def create_wbs_code(db: AsyncSession, project_id: uuid.UUID, data: WBSCodeCreate, user: User) -> WBSCode:
    require(await project_repo.get_by_id(db, project_id), "Project")

    existing = await wbs_code_repo.get_by_project(db, project_id)
    if any(w.code == data.code for w in existing):
        raise UnprocessableError(f"WBS code '{data.code}' already exists in this project")

    if data.level == WBSLevel.subcategory:
        parent_id = data.parent_id
        if not parent_id:
            raise UnprocessableError("Subcategory requires a parent_id")
        parent = await wbs_code_repo.get_by_id(db, parent_id)
        if not parent or parent.project_id != project_id:
            raise UnprocessableError("Invalid parent_id")
    else:
        parent_id = None

    wbs = await wbs_code_repo.create(
        db,
        project_id=project_id,
        code=data.code,
        description=data.description,
        level=data.level,
        sort_order=data.sort_order,
        parent_id=parent_id,
        contract_sum=data.contract_sum,
        created_by=user.id,
    )
    await db.commit()

    return require(await wbs_code_repo.get_by_id_with_children(db, wbs.id), "WBS code")


def require_in_project(wbs: WBSCode | None, project_id: uuid.UUID) -> WBSCode:
    # A WBS code of another project is reported as missing, the same as an unknown id.
    return require(wbs if wbs is not None and wbs.project_id == project_id else None, "WBS code")


async def update_wbs_code(
    db: AsyncSession, project_id: uuid.UUID, wbs_code_id: uuid.UUID, data: WBSCodeUpdate, user: User
) -> WBSCode:
    wbs = require_in_project(await wbs_code_repo.get_by_id(db, wbs_code_id), project_id)

    update_data = data.model_dump(exclude_unset=True)
    if not update_data:
        return wbs

    in_use = await wbs_code_repo.is_in_use(db, wbs_code_id)
    if in_use:
        restricted_fields = {"code", "level", "parent_id"}
        attempted = data.model_fields_set & restricted_fields
        if attempted:
            raise UnprocessableError(
                f"Cannot update {', '.join(attempted)} on a WBS code that is in use by claim/assessment data"
            )

    if data.code is not None and data.code != wbs.code:
        existing = await wbs_code_repo.get_by_project(db, project_id)
        if any(w.code == data.code and w.id != wbs_code_id for w in existing):
            raise UnprocessableError(f"WBS code '{data.code}' already exists in this project")

    update_data["updated_by"] = user.id
    wbs = await wbs_code_repo.update(db, wbs, **update_data)
    await db.commit()

    return require(await wbs_code_repo.get_by_id_with_children(db, wbs.id), "WBS code")
