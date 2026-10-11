import logging
import uuid
from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.constants.enums import WBSLevel
from app.harness.schemas import WbsMatch
from app.repos import wbs_code_repo

logger = logging.getLogger(__name__)


async def create_subcategory(
    db: AsyncSession, match: WbsMatch, *, parent_id: uuid.UUID | None, project_id: uuid.UUID, user_id: uuid.UUID
) -> uuid.UUID | None:
    if not parent_id:
        logger.warning(
            "create_records: skipping WBS match for item %s — new code %r has "
            "unresolvable parent_code %r; line left uncategorised",
            match.item_index,
            match.wbs_code,
            match.parent_code,
        )
        return None
    wbs = await wbs_code_repo.create(
        db,
        project_id=project_id,
        parent_id=parent_id,
        code=match.wbs_code,
        description=match.wbs_description,
        level=WBSLevel.subcategory,
        created_by=user_id,
    )
    return wbs.id


async def resolve_wbs(
    db: AsyncSession, *, project_id: uuid.UUID, user_id: uuid.UUID, matches: Sequence[WbsMatch]
) -> dict[int, uuid.UUID]:
    all_wbs = await wbs_code_repo.get_by_project(db, project_id)
    code_to_id = {w.code: w.id for w in all_wbs if w.level == WBSLevel.subcategory}
    parent_code_to_id = {w.code: w.id for w in all_wbs if w.level == WBSLevel.category}
    resolved: dict[int, uuid.UUID] = {}
    for match in matches:
        # An existing code is always reused, whatever the matcher's is_new says.
        wbs_id = code_to_id.get(match.wbs_code)
        if wbs_id is None and match.is_new:
            wbs_id = await create_subcategory(
                db, match, parent_id=parent_code_to_id.get(match.parent_code), project_id=project_id, user_id=user_id
            )
            if wbs_id is not None:
                code_to_id[match.wbs_code] = wbs_id
        if wbs_id is not None:
            resolved[match.item_index] = wbs_id
    return resolved
