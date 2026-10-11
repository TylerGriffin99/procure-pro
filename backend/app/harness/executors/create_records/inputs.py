import logging
import uuid
from collections.abc import Sequence
from typing import Final

from sqlalchemy.ext.asyncio import AsyncSession

from app.constants.enums import ClaimItemType, WorkspaceFile
from app.exceptions import ExternalServiceError
from app.harness.phase_context import load_workspace
from app.harness.schemas import (
    VPS_KINDS,
    VPS_MATCHES,
    WBS_MATCHES,
    CreateRecordsInputs,
    ParsedClaim,
    ParsedClaimItem,
    VpsMatch,
    WbsMatch,
)

logger = logging.getLogger(__name__)

PROVISIONAL_SUM_PREFIX: Final = "provisional sum"


async def load_inputs(db: AsyncSession, session_id: uuid.UUID) -> CreateRecordsInputs:
    return CreateRecordsInputs(
        parsed=await load_workspace(db, session_id, WorkspaceFile.parsed_claim, ParsedClaim.model_validate_json),
        wbs_matches=await load_workspace(db, session_id, WorkspaceFile.wbs_matches, WBS_MATCHES.validate_json),
        vps_matches=await load_workspace(db, session_id, WorkspaceFile.vps_matches, VPS_MATCHES.validate_json),
    )


def check_index_range(matches: Sequence[WbsMatch | VpsMatch], kind: str, max_index: int) -> None:
    for match in matches:
        if match.item_index > max_index:
            raise ExternalServiceError(
                f"{kind} match has out-of-range item_index {match.item_index} (valid range: 0-{max_index})"
            )


def wbs_in_scope(matches: list[WbsMatch], contract_work: set[int]) -> list[WbsMatch]:
    # The LLM sometimes categorises every item although the prompt says contract_work only.
    if not matches:
        return matches
    in_scope = [m for m in matches if m.item_index in contract_work]
    if len(in_scope) != len(contract_work):
        raise ExternalServiceError(
            f"WBS categorisation returned {len(in_scope)} contract_work matches "
            f"but extraction has {len(contract_work)} contract_work items"
        )
    return in_scope


def vps_in_scope(matches: list[VpsMatch], vps_items: set[int]) -> list[VpsMatch]:
    in_scope = [m for m in matches if m.item_index in vps_items]
    if len(in_scope) != len(vps_items):
        logger.warning(
            "VPS matching returned %d matches but extraction has %d variation/PS items; "
            "unmatched items will be handled by fallback matching",
            len(in_scope),
            len(vps_items),
        )
    return in_scope


def validate_counts(inputs: CreateRecordsInputs) -> CreateRecordsInputs:
    items = inputs.parsed.line_items
    max_index = len(items) - 1
    check_index_range(inputs.wbs_matches, "WBS", max_index)
    check_index_range(inputs.vps_matches, "VPS", max_index)
    contract_work = {i for i, item in enumerate(items) if item.item_type == ClaimItemType.contract_work}
    vps_items = {i for i, item in enumerate(items) if item.item_type in VPS_KINDS}
    return inputs.model_copy(
        update={
            "wbs_matches": wbs_in_scope(inputs.wbs_matches, contract_work),
            "vps_matches": vps_in_scope(inputs.vps_matches, vps_items),
        }
    )


def reclassify_item(item: ParsedClaimItem) -> ParsedClaimItem:
    # The extraction LLM sometimes types a provisional sum as contract_work; the description prefix catches it.
    if item.item_type != ClaimItemType.contract_work or not item.description.lower().startswith(PROVISIONAL_SUM_PREFIX):
        return item
    logger.info("Reclassified ref=%s as provisional_sum (was contract_work): %s", item.ref_code, item.description)
    return item.model_copy(update={"item_type": ClaimItemType.provisional_sum})


def reclassify_provisional_sums(parsed: ParsedClaim) -> ParsedClaim:
    items = [reclassify_item(item) for item in parsed.line_items]
    reclassified = sum(1 for old, new in zip(parsed.line_items, items, strict=True) if old is not new)
    if reclassified:
        logger.info("Reclassified %d items from contract_work to provisional_sum", reclassified)
    return parsed.model_copy(update={"line_items": items})
