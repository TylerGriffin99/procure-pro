import logging
import uuid
from collections.abc import Sequence
from typing import Final

from pydantic import TypeAdapter
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants.enums import ClaimItemType, WorkspaceFile
from app.harness.schemas import CreateRecordsInputs, ParsedClaim, ParsedClaimItem, VpsMatch, WbsMatch
from app.repos import harness_repo

logger = logging.getLogger(__name__)

WBS_MATCHES: Final = TypeAdapter(list[WbsMatch])
VPS_MATCHES: Final = TypeAdapter(list[VpsMatch])
VPS_KINDS: Final = frozenset({ClaimItemType.variation, ClaimItemType.provisional_sum})
PROVISIONAL_SUM_PREFIX: Final = "provisional sum"


async def load_inputs(db: AsyncSession, session_id: uuid.UUID) -> CreateRecordsInputs:
    parsed_raw = await harness_repo.read_workspace_file(db, session_id, WorkspaceFile.parsed_claim)
    wbs_raw = await harness_repo.read_workspace_file(db, session_id, WorkspaceFile.wbs_matches)
    vps_raw = await harness_repo.read_workspace_file(db, session_id, WorkspaceFile.vps_matches)
    if not parsed_raw:
        raise ValueError("parsed_claim.json not found")
    return CreateRecordsInputs(
        parsed=ParsedClaim.model_validate_json(parsed_raw),
        wbs_matches=WBS_MATCHES.validate_json(wbs_raw) if wbs_raw else [],
        vps_matches=VPS_MATCHES.validate_json(vps_raw) if vps_raw else None,
    )


def check_index_range(matches: Sequence[WbsMatch | VpsMatch], kind: str, max_index: int) -> None:
    for match in matches:
        if match.item_index > max_index:
            raise ValueError(
                f"{kind} match has out-of-range item_index {match.item_index} (valid range: 0-{max_index})"
            )


def wbs_in_scope(matches: list[WbsMatch], contract_work: set[int]) -> list[WbsMatch]:
    # The LLM sometimes categorises every item although the prompt says contract_work only.
    if not matches:
        return matches
    in_scope = [m for m in matches if m.item_index in contract_work]
    if len(in_scope) != len(contract_work):
        raise ValueError(
            f"WBS categorisation returned {len(in_scope)} contract_work matches "
            f"but extraction has {len(contract_work)} contract_work items"
        )
    return in_scope


def vps_in_scope(matches: list[VpsMatch] | None, vps_items: set[int]) -> list[VpsMatch] | None:
    if matches is None:
        return None
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
    check_index_range(inputs.vps_matches or [], "VPS", max_index)
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
