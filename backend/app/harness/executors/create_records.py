"""Phase 5: Create domain records from workspace data."""
import json
import logging
import uuid
from datetime import datetime, timezone, date as dt_date
from decimal import Decimal
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.assessment import Assessment, LineItemStatus
from app.models.assessment_line_item import AssessmentLineItem
from app.models.assessment_variation import AssessmentVariation
from app.models.assessment_provisional_sum import AssessmentProvisionalSum
from app.models.claim import Claim, ClaimItemType
from app.models.claim_line_item import ClaimLineItem
from app.models.provisional_sum import ProvisionalSum
from app.models.variation import Variation, VariationStatus
from app.models.wbs_code import WBSCode, WBSLevel
from app.repos import (
    project_repo, assessment_repo,
    variation_repo, provisional_sum_repo, harness_repo,
    wbs_code_repo,
)
from app.utils.assessment_engine import calculate_assessment_totals
from app.utils.assessment_aggregator import (
    aggregate_line_items,
    aggregate_variations,
    aggregate_provisional_sums,
)
import re

logger = logging.getLogger(__name__)

ZERO = Decimal("0")
_U_PREFIX = re.compile(r"^\(U\)\s*")


def _dec(value: str | None) -> Decimal:
    if not value:
        return ZERO
    try:
        return Decimal(str(value).replace(",", ""))
    except Exception:
        return ZERO


def _parse_date(date_str: str | None) -> dt_date | None:
    if not date_str:
        return None
    try:
        parts = date_str.split("/")
        if len(parts) == 3:
            day, month, year = int(parts[0]), int(parts[1]), int(parts[2])
            if year < 100:
                year += 2000
            return dt_date(year, month, day)
    except (ValueError, IndexError):
        pass
    return None


async def execute_create_records(
    db: AsyncSession,
    session_id: uuid.UUID,
    user_id: uuid.UUID,
    project_id: uuid.UUID,
    config: dict[str, Any],
) -> dict:
    """Create Claim, Assessment, and all line item records from workspace data."""
    # Load workspace files
    parsed_raw = await harness_repo.read_workspace_file(db, session_id, "parsed_claim.json")
    wbs_raw = await harness_repo.read_workspace_file(db, session_id, "wbs_matches.json")
    vps_raw = await harness_repo.read_workspace_file(db, session_id, "vps_matches.json")

    if not parsed_raw:
        raise ValueError("parsed_claim.json not found")

    parsed = json.loads(parsed_raw)
    wbs_matches = json.loads(wbs_raw) if wbs_raw else []
    vps_matches = json.loads(vps_raw) if vps_raw else []

    metadata = parsed.get("metadata", {})
    line_items = parsed.get("line_items", [])
    summary = parsed.get("summary", {})

    # -- Item count validation --
    max_index = len(line_items) - 1
    cw_indices = {
        i for i, it in enumerate(line_items)
        if it.get("item_type") == "contract_work"
    }
    vps_indices = {
        i for i, it in enumerate(line_items)
        if it.get("item_type") in ("variation", "provisional_sum")
    }

    # Index range check (before filtering)
    for match in (wbs_matches or []):
        idx = match.get("item_index")
        if idx is None or idx < 0 or idx > max_index:
            raise ValueError(
                f"WBS match has out-of-range item_index {idx} "
                f"(valid range: 0-{max_index})"
            )
    for match in (vps_matches or []):
        idx = match.get("item_index")
        if idx is None or idx < 0 or idx > max_index:
            raise ValueError(
                f"VPS match has out-of-range item_index {idx} "
                f"(valid range: 0-{max_index})"
            )

    # LLM sometimes categorises all items despite the prompt saying
    # "contract_work only" — filter to the correct item types.
    if wbs_matches:
        wbs_matches = [m for m in wbs_matches if m.get("item_index") in cw_indices]
        if len(wbs_matches) != len(cw_indices):
            raise ValueError(
                f"WBS categorisation returned {len(wbs_matches)} contract_work matches "
                f"but extraction has {len(cw_indices)} contract_work items"
            )

    if vps_raw:
        vps_matches = [m for m in vps_matches if m.get("item_index") in vps_indices]
        if len(vps_matches) != len(vps_indices):
            # raise ValueError(
            #     f"VPS matching returned {len(vps_matches)} variation/PS matches "
            #     f"but extraction has {len(vps_indices)} variation/provisional_sum items"
            # )
            logger.warning(
                "VPS matching returned %d matches but extraction has %d variation/PS items; "
                "unmatched items will be handled by fallback matching",
                len(vps_matches), len(vps_indices),
            )

    # Verify project exists
    project = await project_repo.get_by_id(db, project_id)
    if not project:
        raise ValueError(f"Project {project_id} not found")

    # -- Build WBS lookups and create new codes --
    all_wbs = await wbs_code_repo.get_by_project(db, project_id)
    wbs_code_to_id = {w.code: w.id for w in all_wbs if w.level == WBSLevel.subcategory}
    parent_code_to_id = {w.code: w.id for w in all_wbs if w.level == WBSLevel.category}
    index_to_wbs_id: dict[int, uuid.UUID] = {}

    for match in wbs_matches:
        item_idx = match["item_index"]
        code = match.get("wbs_code", "")
        existing_id = wbs_code_to_id.get(code)

        if existing_id:
            # Code already exists — always reuse it, regardless of is_new flag
            index_to_wbs_id[item_idx] = existing_id
        elif match.get("is_new"):
            # Truly new code (doesn't exist in project) — create it
            parent_id = parent_code_to_id.get(match["parent_code"])
            if not parent_id:
                logger.warning(
                    "create_records: skipping WBS match for item %s — new code %r has "
                    "unresolvable parent_code %r; line left uncategorised",
                    item_idx, match.get("wbs_code"), match.get("parent_code"))
                continue
            new_wbs = WBSCode(
                project_id=project_id, parent_id=parent_id,
                code=match["wbs_code"], description=match.get("wbs_description", ""),
                level=WBSLevel.subcategory, created_by=user_id,
            )
            db.add(new_wbs)
            await db.flush()
            wbs_code_to_id[code] = new_wbs.id
            index_to_wbs_id[item_idx] = new_wbs.id

    # -- Build variation/PS lookups and create new records --
    existing_vars = await variation_repo.get_by_project(db, project_id)
    existing_ps = await provisional_sum_repo.get_by_project(db, project_id)
    next_ci = max((v.ci_number for v in existing_vars), default=0) + 1
    next_ps = max((ps.ps_number for ps in existing_ps), default=0) + 1

    # ── Reclassify mistyped provisional sums ──
    # The extraction LLM sometimes classifies provisional sums as contract_work.
    # Catch this deterministically using the description prefix.
    reclassified = 0
    for item in line_items:
        if item.get("item_type") != "contract_work":
            continue
        desc = (item.get("description") or "").lower()
        if desc.startswith("provisional sum"):
            item["item_type"] = "provisional_sum"
            reclassified += 1
            logger.info("Reclassified ref=%s as provisional_sum (was contract_work): %s", item.get("ref_code"), item.get("description"))
    if reclassified:
        logger.info("Reclassified %d items from contract_work to provisional_sum", reclassified)

    var_id_by_index: dict[int, uuid.UUID] = {}
    ps_id_by_index: dict[int, uuid.UUID] = {}

    # Build sets of valid IDs to guard against LLM-hallucinated UUIDs
    valid_var_ids = {v.id for v in existing_vars}
    valid_ps_ids = {ps.id for ps in existing_ps}

    for match in vps_matches:
        item_idx = match["item_index"]
        item = line_items[item_idx]
        ref = item.get("ref_code", "")

        if match.get("matched_id"):
            mid = uuid.UUID(match["matched_id"])
            # Validate the ID actually exists — LLMs can corrupt UUIDs
            if match["item_type"] == "variation":
                if mid in valid_var_ids:
                    var_id_by_index[item_idx] = mid
                    # Update contractor_submission from latest claim (contractor
                    # may revise their submission value between claims)
                    new_submission = _dec(item.get("contract_value"))
                    existing_var = next(v for v in existing_vars if v.id == mid)
                    if new_submission and new_submission != existing_var.contractor_submission:
                        logger.info(
                            "Updating variation %s contractor_submission: %s -> %s",
                            mid, existing_var.contractor_submission, new_submission,
                        )
                        existing_var.contractor_submission = new_submission
                else:
                    logger.warning(
                        "VPS match item_index=%s: matched_id %s not found in existing variations, treating as unmatched",
                        item_idx, mid,
                    )
                    match["matched_id"] = None  # fall through to create new
            else:
                if mid in valid_ps_ids:
                    ps_id_by_index[item_idx] = mid
                    # Update contract_sum from latest claim
                    new_sum = _dec(item.get("contract_value"))
                    existing_ps_rec = next(ps for ps in existing_ps if ps.id == mid)
                    if new_sum and new_sum != existing_ps_rec.contract_sum:
                        logger.info(
                            "Updating PS %s contract_sum: %s -> %s",
                            mid, existing_ps_rec.contract_sum, new_sum,
                        )
                        existing_ps_rec.contract_sum = new_sum
                else:
                    logger.warning(
                        "VPS match item_index=%s: matched_id %s not found in existing provisional sums, treating as unmatched",
                        item_idx, mid,
                    )
                    match["matched_id"] = None  # fall through to create new

        if not match.get("matched_id"):
            # Create new master record
            if match["item_type"] == "variation":
                desc = _U_PREFIX.sub("", item.get("description", ""))
                new_var = Variation(
                    project_id=project_id, ci_number=next_ci,
                    contractor_ref=ref, description=desc,
                    contractor_submission=_dec(item.get("contract_value")),
                    status=VariationStatus.unapproved, created_by=user_id,
                )
                db.add(new_var)
                await db.flush()
                var_id_by_index[item_idx] = new_var.id
                next_ci += 1
            else:
                new_ps = ProvisionalSum(
                    project_id=project_id, ps_number=next_ps,
                    description=item.get("description", ""),
                    contract_sum=_dec(item.get("contract_value")),
                    status=VariationStatus.unapproved, created_by=user_id,
                )
                db.add(new_ps)
                await db.flush()
                ps_id_by_index[item_idx] = new_ps.id
                next_ps += 1

    # -- Fallback: link or create records for unmatched variations/PS --
    # Items may be unmatched because the VPS matcher omitted them, or because
    # they were reclassified after the VPS phase ran. Try to match to existing
    # records by description before creating new ones.
    matched_var_indices = set(var_id_by_index.keys())
    matched_ps_indices = set(ps_id_by_index.keys())

    # Build description-based lookups for existing records not already claimed
    claimed_var_ids = set(var_id_by_index.values())
    claimed_ps_ids = set(ps_id_by_index.values())
    unclaimed_vars = [v for v in existing_vars if v.id not in claimed_var_ids]
    unclaimed_ps = [ps for ps in existing_ps if ps.id not in claimed_ps_ids]

    for item_idx, item in enumerate(line_items):
        ref = item.get("ref_code", "")
        item_type = item.get("item_type", "")
        desc = item.get("description", "")

        if item_type == "variation" and item_idx not in matched_var_indices:
            clean_desc = _U_PREFIX.sub("", desc).lower().strip()
            # Try to match an existing unclaimed variation by description
            matched_existing = next(
                (v for v in unclaimed_vars if v.description.lower().strip() == clean_desc),
                None,
            )
            if matched_existing:
                var_id_by_index[item_idx] = matched_existing.id
                unclaimed_vars.remove(matched_existing)
                logger.info("Fallback matched variation item_index=%s to existing record %s by description", item_idx, matched_existing.id)
            else:
                new_var = Variation(
                    project_id=project_id, ci_number=next_ci,
                    contractor_ref=ref, description=_U_PREFIX.sub("", desc),
                    contractor_submission=_dec(item.get("contract_value")),
                    status=VariationStatus.unapproved, created_by=user_id,
                )
                db.add(new_var)
                await db.flush()
                var_id_by_index[item_idx] = new_var.id
                next_ci += 1
                logger.info("Created fallback variation for unmatched item_index %s: %s", item_idx, desc)

        elif item_type == "provisional_sum" and item_idx not in matched_ps_indices:
            desc_lower = desc.lower().strip()
            # Try to match an existing unclaimed PS by description
            matched_existing = next(
                (ps for ps in unclaimed_ps if ps.description.lower().strip() == desc_lower),
                None,
            )
            if matched_existing:
                ps_id_by_index[item_idx] = matched_existing.id
                unclaimed_ps.remove(matched_existing)
                logger.info("Fallback matched PS item_index=%s to existing record %s by description", item_idx, matched_existing.id)
            else:
                new_ps = ProvisionalSum(
                    project_id=project_id, ps_number=next_ps,
                    description=desc,
                    contract_sum=_dec(item.get("contract_value")),
                    status=VariationStatus.unapproved, created_by=user_id,
                )
                db.add(new_ps)
                await db.flush()
                ps_id_by_index[item_idx] = new_ps.id
                next_ps += 1
                logger.info("Created fallback provisional sum for unmatched item_index %s", item_idx)

    # -- Create Claim --
    claim = Claim(
        project_id=project_id,
        claim_number=int(metadata.get("claim_number", 0) or 0),
        period_from=_parse_date(metadata.get("period_from")),
        period_to=_parse_date(metadata.get("period_to")),
        payment_due=_parse_date(metadata.get("payment_due")),
        parsed_at=datetime.now(timezone.utc),
        original_contract_total=_dec(summary.get("original_contract_total")),
        variations_total=_dec(summary.get("variations_total")),
        revised_contract_total=_dec(summary.get("revised_contract_total")),
        retention_amount=_dec(summary.get("retention_amount")),
        claimed_amount=_dec(summary.get("claimed_amount")),
        raw_pdf_path=config.get("file_path"),
        created_by=user_id,
    )

    for i, item in enumerate(line_items):
        claim.line_items.append(ClaimLineItem(
            item_type=ClaimItemType(item.get("item_type", "contract_work")),
            ref_code=item.get("ref_code", ""),
            description=item.get("description", ""),
            contract_value=_dec(item.get("contract_value")),
            percentage=_dec(item.get("percentage")),
            ptd=_dec(item.get("ptd")),
            previous=_dec(item.get("previous")),
            current=_dec(item.get("current")),
            balance=_dec(item.get("balance")),
            sort_order=i,
            suggested_wbs_code_id=index_to_wbs_id.get(i),
            variation_id=var_id_by_index.get(i),
            provisional_sum_id=ps_id_by_index.get(i),
            categorisation_confidence=Decimal(str(item.get("confidence", 0))),
            created_by=user_id,
        ))

    db.add(claim)
    await db.flush()

    # -- Build contractor acceptance lookups from new claim --
    # Sum the contractor's `previous` values per WBS/variation/PS.
    # If contractor's previous < our stored contractor_claim_to_date,
    # the contractor has accepted the QS valuation.
    claim_prev_by_wbs: dict[uuid.UUID, Decimal] = {}
    claim_prev_by_variation: dict[uuid.UUID, Decimal] = {}
    claim_prev_by_ps: dict[uuid.UUID, Decimal] = {}
    for cli in claim.line_items:
        prev = cli.previous if cli.previous is not None else ZERO
        if cli.item_type == ClaimItemType.contract_work and cli.suggested_wbs_code_id:
            claim_prev_by_wbs[cli.suggested_wbs_code_id] = (
                claim_prev_by_wbs.get(cli.suggested_wbs_code_id, ZERO) + prev
            )
        elif cli.item_type == ClaimItemType.variation and cli.variation_id:
            claim_prev_by_variation[cli.variation_id] = (
                claim_prev_by_variation.get(cli.variation_id, ZERO) + prev
            )
        elif cli.item_type == ClaimItemType.provisional_sum and cli.provisional_sum_id:
            claim_prev_by_ps[cli.provisional_sum_id] = (
                claim_prev_by_ps.get(cli.provisional_sum_id, ZERO) + prev
            )

    # -- Create Assessment (WBS-first approach) --
    latest_assessment = await assessment_repo.get_latest_finalised(db, project_id)
    previously_certified = latest_assessment.total_payment_to_date if latest_assessment else ZERO

    # Build previous assessment history lookups — sum across multiple rows per WBS/var/PS
    prev_recommended_by_wbs: dict[uuid.UUID, Decimal] = {}
    prev_contractor_claim_by_wbs: dict[uuid.UUID, Decimal] = {}
    prev_variation_recommended: dict[uuid.UUID, Decimal] = {}
    prev_variation_contractor_claim: dict[uuid.UUID, Decimal] = {}
    prev_ps_recommended: dict[uuid.UUID, Decimal] = {}
    prev_ps_contractor_claim: dict[uuid.UUID, Decimal] = {}
    if latest_assessment:
        prev_wbs_groups = aggregate_line_items(latest_assessment.line_items, all_wbs)
        for g in prev_wbs_groups:
            prev_recommended_by_wbs[g.wbs_code_id] = g.total_recommended
            prev_contractor_claim_by_wbs[g.wbs_code_id] = g.contractor_claim_to_date

        prev_var_groups = aggregate_variations(latest_assessment.variation_items, existing_vars)
        for g in prev_var_groups:
            prev_variation_recommended[g.variation_id] = g.total_recommended
            prev_variation_contractor_claim[g.variation_id] = g.contractor_claim_to_date

        prev_ps_groups = aggregate_provisional_sums(latest_assessment.provisional_sum_items, existing_ps)
        for g in prev_ps_groups:
            prev_ps_recommended[g.provisional_sum_id] = g.total_recommended
            prev_ps_contractor_claim[g.provisional_sum_id] = g.contractor_claim_to_date

    # Build comment lookups from previous assessment for carry-forward
    prev_comments_by_wbs: dict[uuid.UUID, str] = {}
    prev_comments_by_variation: dict[uuid.UUID, str] = {}
    prev_comments_by_ps: dict[uuid.UUID, str] = {}
    if latest_assessment:
        for li in latest_assessment.line_items:
            if li.wbs_code_id and li.comments and li.claim_line_item_id is None:
                prev_comments_by_wbs[li.wbs_code_id] = li.comments
        for av in latest_assessment.variation_items:
            if av.comments and av.claim_line_item_id is None:
                prev_comments_by_variation[av.variation_id] = av.comments
        for ps in latest_assessment.provisional_sum_items:
            if ps.comments and ps.claim_line_item_id is None:
                prev_comments_by_ps[ps.provisional_sum_id] = ps.comments

    assessment = Assessment(
        claim_id=claim.id, project_id=project_id,
        version=1,
        previously_certified=previously_certified or ZERO,
        created_by=user_id,
    )

    # -- Phase 1: WBS-level history rows (one per WBS subcategory) --
    all_wbs = await wbs_code_repo.get_by_project(db, project_id)
    wbs_subcategories = sorted(
        (w for w in all_wbs if w.level == WBSLevel.subcategory and w.contract_sum is not None),
        key=lambda w: w.sort_order,
    )
    for i, wbs in enumerate(wbs_subcategories):
        previously_paid = prev_recommended_by_wbs.get(wbs.id, ZERO)
        prev_contractor_claim = prev_contractor_claim_by_wbs.get(wbs.id, ZERO)
        # Contractor acceptance: if their `previous` is lower, they accepted QS valuation
        claim_prev = claim_prev_by_wbs.get(wbs.id)
        if claim_prev is not None and claim_prev < prev_contractor_claim:
            logger.debug("Contractor acceptance: WBS %s: %s -> %s", wbs.id, prev_contractor_claim, claim_prev)
            prev_contractor_claim = claim_prev
        assessment.line_items.append(AssessmentLineItem(
            claim_line_item_id=None,
            description=wbs.description,
            contractor_claim_to_date=prev_contractor_claim,
            total_recommended=previously_paid,
            percentage=(previously_paid / wbs.contract_sum * 100) if wbs.contract_sum else ZERO,
            variance_to_claim=previously_paid - prev_contractor_claim,
            previously_paid=previously_paid,
            recommended_this_period=ZERO,
            status=LineItemStatus.approved,
            wbs_code_id=wbs.id,
            sort_order=i,
            comments=prev_comments_by_wbs.get(wbs.id),
            created_by=user_id,
        ))

    # -- Phase 2: Per-claim-line-item rows for contract works --
    next_sort = len(wbs_subcategories)
    for cli in sorted(claim.line_items, key=lambda x: x.sort_order):
        if cli.item_type != ClaimItemType.contract_work:
            continue
        current = cli.current or ZERO
        assessment.line_items.append(AssessmentLineItem(
            claim_line_item_id=cli.id,
            wbs_code_id=cli.suggested_wbs_code_id,
            description=cli.description,
            contractor_claim_to_date=current,
            total_recommended=current,
            percentage=ZERO,
            variance_to_claim=ZERO,
            previously_paid=ZERO,
            recommended_this_period=current,
            status=LineItemStatus.approved if current == ZERO else LineItemStatus.unapproved,
            sort_order=next_sort,
            created_by=user_id,
        ))
        next_sort += 1

    # -- Phase 1: Variation history rows --
    existing_vars = await variation_repo.get_by_project(db, project_id)
    for var in existing_vars:
        prev_rec = prev_variation_recommended.get(var.id, ZERO)
        prev_claim = prev_variation_contractor_claim.get(var.id, ZERO)
        # Contractor acceptance
        claim_prev = claim_prev_by_variation.get(var.id)
        if claim_prev is not None and claim_prev < prev_claim:
            logger.debug("Contractor acceptance: Variation %s: %s -> %s", var.id, prev_claim, claim_prev)
            prev_claim = claim_prev
        assessment.variation_items.append(AssessmentVariation(
            variation_id=var.id,
            claim_line_item_id=None,
            contractor_claim_to_date=prev_claim,
            total_recommended=prev_rec,
            percentage=(prev_rec / var.contractor_submission * 100) if var.contractor_submission else ZERO,
            variance_to_claim=prev_rec - prev_claim,
            previously_paid=prev_rec,
            recommended_this_period=ZERO,
            status=LineItemStatus.approved,
            comments=prev_comments_by_variation.get(var.id),
            created_by=user_id,
        ))

    # -- Phase 2: Per-claim-line-item variation rows --
    for cli in sorted(claim.line_items, key=lambda x: x.sort_order):
        if cli.item_type == ClaimItemType.variation and cli.variation_id:
            current = cli.current or ZERO
            assessment.variation_items.append(AssessmentVariation(
                variation_id=cli.variation_id,
                claim_line_item_id=cli.id,
                contractor_claim_to_date=current,
                total_recommended=current,
                percentage=ZERO,
                variance_to_claim=ZERO,
                previously_paid=ZERO,
                recommended_this_period=current,
                status=LineItemStatus.approved if current == ZERO else LineItemStatus.unapproved,
                created_by=user_id,
            ))

    # -- Phase 1: Provisional sum history rows --
    existing_ps_records = await provisional_sum_repo.get_by_project(db, project_id)
    for ps in existing_ps_records:
        prev_rec = prev_ps_recommended.get(ps.id, ZERO)
        prev_claim = prev_ps_contractor_claim.get(ps.id, ZERO)
        # Contractor acceptance
        claim_prev = claim_prev_by_ps.get(ps.id)
        if claim_prev is not None and claim_prev < prev_claim:
            logger.debug("Contractor acceptance: PS %s: %s -> %s", ps.id, prev_claim, claim_prev)
            prev_claim = claim_prev
        assessment.provisional_sum_items.append(AssessmentProvisionalSum(
            provisional_sum_id=ps.id,
            claim_line_item_id=None,
            contractor_claim_to_date=prev_claim,
            total_recommended=prev_rec,
            percentage=(prev_rec / ps.contract_sum * 100) if ps.contract_sum else ZERO,
            variance_to_claim=prev_rec - prev_claim,
            previously_paid=prev_rec,
            recommended_this_period=ZERO,
            status=LineItemStatus.approved,
            comments=prev_comments_by_ps.get(ps.id),
            created_by=user_id,
        ))

    # -- Phase 2: Per-claim-line-item PS rows --
    for cli in sorted(claim.line_items, key=lambda x: x.sort_order):
        if cli.item_type == ClaimItemType.provisional_sum and cli.provisional_sum_id:
            current = cli.current or ZERO
            assessment.provisional_sum_items.append(AssessmentProvisionalSum(
                provisional_sum_id=cli.provisional_sum_id,
                claim_line_item_id=cli.id,
                contractor_claim_to_date=current,
                total_recommended=current,
                percentage=ZERO,
                variance_to_claim=ZERO,
                previously_paid=ZERO,
                recommended_this_period=current,
                status=LineItemStatus.approved if current == ZERO else LineItemStatus.unapproved,
                created_by=user_id,
            ))

    # -- Calculate retention and assessment summary totals --
    sub_total_contract_works = sum(
        (ali.total_recommended or ZERO) for ali in assessment.line_items
    )
    sub_total_provisional_sums = sum(
        (aps.total_recommended or ZERO) for aps in assessment.provisional_sum_items
    )
    sub_total_variations_recommended = sum(
        (av.total_recommended or ZERO) for av in assessment.variation_items
    )
    variations_claimed = sum(
        (av.contractor_claim_to_date or ZERO) for av in assessment.variation_items
    )

    retention_tiers = [
        {"percentage": t.percentage, "up_to_amount": t.up_to_amount}
        for t in project.retention_tiers
    ]

    totals = calculate_assessment_totals(
        contract_sum=project.contract_sum or ZERO,
        sub_total_contract_works=sub_total_contract_works,
        sub_total_provisional_sums=sub_total_provisional_sums,
        sub_total_variations_recommended=sub_total_variations_recommended,
        variations_claimed=variations_claimed,
        retention_tiers=retention_tiers,
        previously_certified=previously_certified or ZERO,
        gst_rate=project.gst_rate or Decimal("0.15"),
    )

    assessment.contract_sum = totals["contract_sum"]
    assessment.approved_variation_orders = totals["approved_variation_orders"]
    assessment.adjusted_contract_sum = totals["adjusted_contract_sum"]
    assessment.value_claimed_to_date = totals["value_claimed_to_date"]
    assessment.adjustments = totals["adjustments"]
    assessment.total_recommended = totals["total_recommended"]
    assessment.total_retention = totals["total_retention"]
    assessment.total_payment_to_date = totals["total_payment_to_date"]
    assessment.recommended_this_period = totals["recommended_this_period"]
    assessment.gst_amount = totals["gst_amount"]
    assessment.total_including_gst = totals["total_including_gst"]

    db.add(assessment)
    await db.flush()

    # Link flags to claim
    await harness_repo.link_flags_to_claim(db, session_id, claim.id)

    # Set claim_id on harness session
    await harness_repo.set_claim_id(db, session_id, claim.id)

    logger.info(
        "Created claim %s with %d items, assessment %s (retention: %s)",
        claim.id, len(claim.line_items), assessment.id, assessment.total_retention,
    )

    return {
        "claim_id": str(claim.id),
        "assessment_id": str(assessment.id),
        "line_items_created": len(claim.line_items),
    }
