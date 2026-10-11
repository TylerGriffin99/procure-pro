import logging
import re
import uuid
from collections.abc import Sequence
from typing import Final, assert_never

from sqlalchemy.ext.asyncio import AsyncSession

from app.constants.enums import ClaimItemType, VariationStatus
from app.harness.schemas import ParsedClaimItem, VpsLinks, VpsMatch
from app.models.provisional_sum import ProvisionalSum
from app.models.variation import Variation
from app.repos import provisional_sum_repo, variation_repo
from app.utils.money import parse_money

logger = logging.getLogger(__name__)

UNAPPROVED_PREFIX: Final = re.compile(r"^\(U\)\s*")
MASTER_COLLECTION: Final = {ClaimItemType.variation: "variations", ClaimItemType.provisional_sum: "provisional sums"}
MASTER_LABEL: Final = {ClaimItemType.variation: "variation", ClaimItemType.provisional_sum: "PS"}

Master = Variation | ProvisionalSum


def description_key(description: str, kind: ClaimItemType) -> str:
    text = UNAPPROVED_PREFIX.sub("", description) if kind == ClaimItemType.variation else description
    return text.lower().strip()


def existing_master(match: VpsMatch, masters: dict[uuid.UUID, Master]) -> Master | None:
    # LLMs can corrupt UUIDs, so a matched id must name a record that exists.
    if not match.matched_id:
        return None
    matched_id = uuid.UUID(match.matched_id)
    master = masters.get(matched_id)
    if master is None:
        logger.warning(
            "VPS match item_index=%s: matched_id %s not found in existing %s, treating as unmatched",
            match.item_index,
            matched_id,
            MASTER_COLLECTION[ClaimItemType(match.item_type)],
        )
    return master


async def refresh_claimed_value(db: AsyncSession, master: Master, item: ParsedClaimItem) -> None:
    # The contractor may revise a submission between claims; the latest claim's value wins.
    claimed = parse_money(item.contract_value).value
    match master:
        case Variation():
            if claimed and claimed != master.contractor_submission:
                logger.info(
                    "Updating variation %s contractor_submission: %s -> %s",
                    master.id,
                    master.contractor_submission,
                    claimed,
                )
                await variation_repo.update(db, master, contractor_submission=claimed)
        case ProvisionalSum():
            if claimed and claimed != master.contract_sum:
                logger.info("Updating PS %s contract_sum: %s -> %s", master.id, master.contract_sum, claimed)
                await provisional_sum_repo.update(db, master, contract_sum=claimed)
        case _:
            assert_never(master)


async def create_master(
    db: AsyncSession, kind: ClaimItemType, item: ParsedClaimItem, *, project_id: uuid.UUID, user_id: uuid.UUID
) -> uuid.UUID:
    value = parse_money(item.contract_value).value
    match kind:
        case ClaimItemType.variation:
            ci_number = await variation_repo.get_max_ci_number(db, project_id) + 1
            variation = await variation_repo.create(
                db,
                project_id=project_id,
                ci_number=ci_number,
                contractor_ref=item.ref_code,
                description=UNAPPROVED_PREFIX.sub("", item.description),
                contractor_submission=value,
                status=VariationStatus.unapproved,
                created_by=user_id,
            )
            return variation.id
        case ClaimItemType.provisional_sum:
            ps_number = await provisional_sum_repo.get_max_ps_number(db, project_id) + 1
            ps = await provisional_sum_repo.create(
                db,
                project_id=project_id,
                ps_number=ps_number,
                description=item.description,
                contract_sum=value,
                status=VariationStatus.unapproved,
                created_by=user_id,
            )
            return ps.id
        case ClaimItemType.contract_work:
            raise ValueError(f"No variation/PS master for contract_work item {item.item_index}")
        case _:
            assert_never(kind)


async def link_matches(
    db: AsyncSession,
    *,
    items: Sequence[ParsedClaimItem],
    matches: Sequence[VpsMatch],
    masters: dict[ClaimItemType, dict[uuid.UUID, Master]],
    project_id: uuid.UUID,
    user_id: uuid.UUID,
) -> dict[ClaimItemType, dict[int, uuid.UUID]]:
    links: dict[ClaimItemType, dict[int, uuid.UUID]] = {kind: {} for kind in masters}
    for match in matches:
        kind = ClaimItemType(match.item_type)
        item = items[match.item_index]
        master = existing_master(match, masters[kind])
        if master is None:
            links[kind][match.item_index] = await create_master(db, kind, item, project_id=project_id, user_id=user_id)
            continue
        await refresh_claimed_value(db, master, item)
        links[kind][match.item_index] = master.id
    return links


def find_by_description(candidates: Sequence[Master], item: ParsedClaimItem, kind: ClaimItemType) -> Master | None:
    key = description_key(item.description, kind)
    return next((m for m in candidates if m.description.lower().strip() == key), None)


async def link_unmatched(
    db: AsyncSession,
    *,
    items: Sequence[ParsedClaimItem],
    linked: dict[ClaimItemType, dict[int, uuid.UUID]],
    masters: dict[ClaimItemType, dict[uuid.UUID, Master]],
    project_id: uuid.UUID,
    user_id: uuid.UUID,
) -> dict[ClaimItemType, dict[int, uuid.UUID]]:
    # Items the VPS matcher omitted, or that were reclassified after it ran, link to an unclaimed existing
    # record with the same description before a new record is created.
    claimed = {master_id for links in linked.values() for master_id in links.values()}
    links: dict[ClaimItemType, dict[int, uuid.UUID]] = {kind: {} for kind in masters}
    for index, item in enumerate(items):
        kind = item.item_type
        if kind not in masters or index in linked[kind]:
            continue
        unclaimed = [m for m in masters[kind].values() if m.id not in claimed]
        found = find_by_description(unclaimed, item, kind)
        if found is not None:
            claimed.add(found.id)
            links[kind][index] = found.id
            logger.info(
                "Fallback matched %s item_index=%s to existing record %s by description",
                MASTER_LABEL[kind],
                index,
                found.id,
            )
            continue
        links[kind][index] = await create_master(db, kind, item, project_id=project_id, user_id=user_id)
        if kind == ClaimItemType.variation:
            logger.info("Created fallback variation for unmatched item_index %s: %s", index, item.description)
        else:
            logger.info("Created fallback provisional sum for unmatched item_index %s", index)
    return links


async def resolve_vps(
    db: AsyncSession,
    *,
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    items: Sequence[ParsedClaimItem],
    matches: Sequence[VpsMatch],
) -> VpsLinks:
    variations = await variation_repo.get_by_project(db, project_id)
    provisional_sums = await provisional_sum_repo.get_by_project(db, project_id)
    masters: dict[ClaimItemType, dict[uuid.UUID, Master]] = {
        ClaimItemType.variation: {v.id: v for v in variations},
        ClaimItemType.provisional_sum: {p.id: p for p in provisional_sums},
    }
    linked = await link_matches(
        db, items=items, matches=matches, masters=masters, project_id=project_id, user_id=user_id
    )
    fallback = await link_unmatched(
        db, items=items, linked=linked, masters=masters, project_id=project_id, user_id=user_id
    )
    return VpsLinks(
        variations=linked[ClaimItemType.variation] | fallback[ClaimItemType.variation],
        provisional_sums=linked[ClaimItemType.provisional_sum] | fallback[ClaimItemType.provisional_sum],
    )
