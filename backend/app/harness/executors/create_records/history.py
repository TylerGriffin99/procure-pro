import logging
import uuid
from collections.abc import Callable, Iterable
from decimal import Decimal
from operator import attrgetter
from typing import Any, Final

from sqlalchemy.ext.asyncio import AsyncSession

from app.constants.enums import ClaimItemType, LineItemStatus, WBSLevel
from app.harness.schemas import HistorySource, KindHistory, MasterRef
from app.models.assessment import Assessment
from app.models.claim import Claim
from app.repos import assessment_repo, provisional_sum_repo, variation_repo, wbs_code_repo
from app.schemas.assessment_aggregate import AssessmentRows, AssessmentRowValues
from app.services.assessment_aggregate import aggregate_assessment

logger = logging.getLogger(__name__)

ZERO = Decimal("0")
HUNDRED = Decimal("100")
Key = Callable[[Any], uuid.UUID | None]


def prior_totals(groups: Iterable[Any], key: Key) -> tuple[dict[uuid.UUID, Decimal], dict[uuid.UUID, Decimal]]:
    keyed = [(master_id, g) for g in groups if (master_id := key(g)) is not None]
    return (
        {master_id: g.total_recommended for master_id, g in keyed},
        {master_id: g.contractor_claim_to_date for master_id, g in keyed},
    )


def carried_comments(rows: Iterable[Any], key: Key) -> dict[uuid.UUID, str]:
    return {
        master_id: row.comments
        for row in rows
        if (master_id := key(row)) and row.comments and row.claim_line_item_id is None
    }


def contractor_previous(claim_lines: Iterable[Any], kind: ClaimItemType, key: Key) -> dict[uuid.UUID, Decimal]:
    # The contractor's `previous` per group; below our stored claim-to-date it means they accepted the QS valuation.
    totals: dict[uuid.UUID, Decimal] = {}
    for line in claim_lines:
        master_id = key(line)
        if line.item_type == kind and master_id:
            totals[master_id] = totals.get(master_id, ZERO) + (line.previous if line.previous is not None else ZERO)
    return totals


def kind_history(source: HistorySource, kind: ClaimItemType, *, groups: str, rows: str, key: str) -> KindHistory:
    get_key = attrgetter(key)
    recommended, claimed = prior_totals(getattr(source.previous, groups) if source.previous else [], get_key)
    line_key = attrgetter("suggested_wbs_code_id") if kind == ClaimItemType.contract_work else get_key
    return KindHistory(
        recommended=recommended,
        claimed=claimed,
        comments=carried_comments(getattr(source.latest, rows) if source.latest else [], get_key),
        accepted=contractor_previous(source.claim_lines, kind, line_key),
    )


def history_row(master: MasterRef, history: KindHistory, *, user_id: uuid.UUID, label: str) -> AssessmentRowValues:
    previously_paid = history.recommended.get(master.id, ZERO)
    claimed = history.claimed.get(master.id, ZERO)
    accepted = history.accepted.get(master.id)
    if accepted is not None and accepted < claimed:
        logger.debug("Contractor acceptance: %s %s: %s -> %s", label, master.id, claimed, accepted)
        claimed = accepted
    return AssessmentRowValues(
        master_id=master.id,
        claim_line_item_id=None,
        contractor_claim_to_date=claimed,
        total_recommended=previously_paid,
        percentage=(previously_paid / master.denominator * HUNDRED) if master.denominator else ZERO,
        variance_to_claim=previously_paid - claimed,
        previously_paid=previously_paid,
        recommended_this_period=ZERO,
        status=LineItemStatus.approved,
        comments=history.comments.get(master.id),
        description=master.description,
        sort_order=master.sort_order,
        created_by=user_id,
    )


def current_row(
    line: Any,
    master_id: uuid.UUID | None,
    *,
    user_id: uuid.UUID,
    description: str | None = None,
    sort_order: int | None = None,
) -> AssessmentRowValues:
    current = line.current or ZERO
    return AssessmentRowValues(
        master_id=master_id,
        claim_line_item_id=line.id,
        contractor_claim_to_date=current,
        total_recommended=current,
        percentage=ZERO,
        variance_to_claim=ZERO,
        previously_paid=ZERO,
        recommended_this_period=current,
        status=LineItemStatus.approved if current == ZERO else LineItemStatus.unapproved,
        description=description,
        sort_order=sort_order,
        created_by=user_id,
    )


def wbs_rows(source: HistorySource) -> list[AssessmentRowValues]:
    subcategories = sorted(
        (w for w in source.wbs_codes if w.level == WBSLevel.subcategory and w.contract_sum is not None),
        key=attrgetter("sort_order"),
    )
    masters = [
        MasterRef(id=w.id, denominator=w.contract_sum, description=w.description, sort_order=i)
        for i, w in enumerate(subcategories)
    ]
    history = kind_history(
        source, ClaimItemType.contract_work, groups="wbs_groups", rows="line_items", key="wbs_code_id"
    )
    lines = [line for line in source.claim_lines if line.item_type == ClaimItemType.contract_work]
    return [history_row(m, history, user_id=source.user_id, label="WBS") for m in masters] + [
        current_row(
            line,
            line.suggested_wbs_code_id,
            user_id=source.user_id,
            description=line.description,
            sort_order=len(masters) + i,
        )
        for i, line in enumerate(lines)
    ]


def variation_rows(source: HistorySource) -> list[AssessmentRowValues]:
    masters = [MasterRef(id=v.id, denominator=v.contractor_submission) for v in source.variations]
    history = kind_history(
        source, ClaimItemType.variation, groups="variation_groups", rows="variation_items", key="variation_id"
    )
    return [history_row(m, history, user_id=source.user_id, label="Variation") for m in masters] + [
        current_row(line, line.variation_id, user_id=source.user_id)
        for line in source.claim_lines
        if line.item_type == ClaimItemType.variation and line.variation_id
    ]


def provisional_sum_rows(source: HistorySource) -> list[AssessmentRowValues]:
    masters = [MasterRef(id=p.id, denominator=p.contract_sum) for p in source.provisional_sums]
    history = kind_history(
        source,
        ClaimItemType.provisional_sum,
        groups="ps_groups",
        rows="provisional_sum_items",
        key="provisional_sum_id",
    )
    return [history_row(m, history, user_id=source.user_id, label="PS") for m in masters] + [
        current_row(line, line.provisional_sum_id, user_id=source.user_id)
        for line in source.claim_lines
        if line.item_type == ClaimItemType.provisional_sum and line.provisional_sum_id
    ]


HISTORY_BUILDERS: Final[dict[ClaimItemType, Callable[[HistorySource], list[AssessmentRowValues]]]] = {
    ClaimItemType.contract_work: wbs_rows,
    ClaimItemType.variation: variation_rows,
    ClaimItemType.provisional_sum: provisional_sum_rows,
}


def build_history(source: HistorySource) -> AssessmentRows:
    rows = {kind: build(source) for kind, build in HISTORY_BUILDERS.items()}
    return AssessmentRows(
        line_items=rows[ClaimItemType.contract_work],
        variation_items=rows[ClaimItemType.variation],
        provisional_sum_items=rows[ClaimItemType.provisional_sum],
    )


async def load_history_source(
    db: AsyncSession, *, project_id: uuid.UUID, user_id: uuid.UUID, claim: Claim
) -> HistorySource:
    latest = await assessment_repo.get_latest_finalised(db, project_id)
    previous = (await aggregate_assessment(db, project_id, latest)).aggregate if latest else None
    return HistorySource(
        claim_lines=sorted(claim.line_items, key=attrgetter("sort_order")),
        previous=previous,
        latest=latest,
        wbs_codes=await wbs_code_repo.get_by_project(db, project_id),
        variations=await variation_repo.get_by_project(db, project_id),
        provisional_sums=await provisional_sum_repo.get_by_project(db, project_id),
        user_id=user_id,
    )


async def build_assessment(db: AsyncSession, *, project_id: uuid.UUID, user_id: uuid.UUID, claim: Claim) -> Assessment:
    source = await load_history_source(db, project_id=project_id, user_id=user_id, claim=claim)
    previously_certified = source.latest.total_payment_to_date if source.latest else ZERO
    return await assessment_repo.create(
        db,
        rows=build_history(source),
        claim_id=claim.id,
        project_id=project_id,
        version=await assessment_repo.next_version_number(db, claim.id),
        previously_certified=previously_certified or ZERO,
        created_by=user_id,
    )
