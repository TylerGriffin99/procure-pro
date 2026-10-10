"""
Pure aggregation utility for assessment rows.

Groups assessment rows (line items, variations, provisional sums) by their
parent record and computes totals. Sources contract_sum from master records,
not from individual rows.

No DB access — takes data in, returns computed results.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Protocol

ZERO = Decimal("0.00")


# ── Protocols for duck-typing ORM models and test fakes ──────────────────
# Members are read-only (properties) so the protocols are covariant: ORM models
# whose columns are narrower types (e.g. str-enums for `status`/`adjustment_type`)
# structurally satisfy them, and so do plain-attribute test fakes. The aggregators
# only ever read these fields.


class LineItemLike(Protocol):
    @property
    def id(self) -> uuid.UUID: ...
    @property
    def wbs_code_id(self) -> uuid.UUID | None: ...
    @property
    def claim_line_item_id(self) -> uuid.UUID | None: ...
    @property
    def description(self) -> str: ...
    @property
    def contract_sum(self) -> Decimal | None: ...
    @property
    def contractor_claim_to_date(self) -> Decimal: ...
    @property
    def total_recommended(self) -> Decimal: ...
    @property
    def previously_paid(self) -> Decimal: ...
    @property
    def recommended_this_period(self) -> Decimal: ...
    @property
    def variance_to_claim(self) -> Decimal: ...
    @property
    def percentage(self) -> Decimal: ...
    @property
    def status(self) -> str: ...
    @property
    def sort_order(self) -> int: ...
    @property
    def comments(self) -> str | None: ...
    @property
    def adjustment_type(self) -> str | None: ...


class WBSLike(Protocol):
    @property
    def id(self) -> uuid.UUID: ...
    @property
    def description(self) -> str: ...
    @property
    def contract_sum(self) -> Decimal | None: ...


class VariationItemLike(Protocol):
    @property
    def id(self) -> uuid.UUID: ...
    @property
    def variation_id(self) -> uuid.UUID: ...
    @property
    def claim_line_item_id(self) -> uuid.UUID | None: ...
    @property
    def contractor_claim_to_date(self) -> Decimal: ...
    @property
    def total_recommended(self) -> Decimal: ...
    @property
    def previously_paid(self) -> Decimal: ...
    @property
    def recommended_this_period(self) -> Decimal: ...
    @property
    def status(self) -> str: ...
    @property
    def adjustment_type(self) -> str | None: ...


class VariationLike(Protocol):
    @property
    def id(self) -> uuid.UUID: ...
    @property
    def ci_number(self) -> int: ...
    @property
    def contractor_ref(self) -> str | None: ...
    @property
    def description(self) -> str: ...
    @property
    def contractor_submission(self) -> Decimal: ...


class PSItemLike(Protocol):
    @property
    def id(self) -> uuid.UUID: ...
    @property
    def provisional_sum_id(self) -> uuid.UUID: ...
    @property
    def claim_line_item_id(self) -> uuid.UUID | None: ...
    @property
    def contractor_claim_to_date(self) -> Decimal: ...
    @property
    def total_recommended(self) -> Decimal: ...
    @property
    def previously_paid(self) -> Decimal: ...
    @property
    def recommended_this_period(self) -> Decimal: ...
    @property
    def status(self) -> str: ...
    @property
    def adjustment_type(self) -> str | None: ...


class PSLike(Protocol):
    @property
    def id(self) -> uuid.UUID: ...
    @property
    def ps_number(self) -> int: ...
    @property
    def description(self) -> str: ...
    @property
    def contract_sum(self) -> Decimal: ...


# ── Output dataclasses ───────────────────────────────────────────────────


@dataclass
class AggregatedWBSGroup:
    wbs_code_id: uuid.UUID | None
    description: str
    contract_sum: Decimal
    previously_paid: Decimal
    recommended_this_period: Decimal
    total_recommended: Decimal
    contractor_claim_to_date: Decimal
    variance_to_claim: Decimal
    percentage: Decimal
    history_row: Any | None
    child_rows: list[Any] = field(default_factory=list)


@dataclass
class AggregatedVariationGroup:
    variation_id: uuid.UUID
    ci_number: int
    contractor_ref: str
    description: str
    contractor_submission: Decimal
    previously_paid: Decimal
    recommended_this_period: Decimal
    total_recommended: Decimal
    contractor_claim_to_date: Decimal
    variance_to_claim: Decimal
    percentage: Decimal
    history_row: Any | None
    child_rows: list[Any] = field(default_factory=list)


@dataclass
class AggregatedPSGroup:
    provisional_sum_id: uuid.UUID
    ps_number: int
    description: str
    contract_sum: Decimal
    previously_paid: Decimal
    recommended_this_period: Decimal
    total_recommended: Decimal
    contractor_claim_to_date: Decimal
    variance_to_claim: Decimal
    percentage: Decimal
    history_row: Any | None
    child_rows: list[Any] = field(default_factory=list)


@dataclass
class AssessmentTotals:
    sub_contract_works: Decimal
    approved_variation_orders: Decimal
    adjustment_to_provisional_sums: Decimal
    total_recommended: Decimal
    value_claimed_to_date: Decimal
    adjustments: Decimal


# ── Aggregation functions ────────────────────────────────────────────────


def aggregate_line_items(
    rows: Sequence[LineItemLike],
    wbs_codes: Sequence[WBSLike],
) -> list[AggregatedWBSGroup]:
    """Group line items by wbs_code_id, compute totals, source contract_sum from WBS master."""
    wbs_map: dict[uuid.UUID, WBSLike] = {w.id: w for w in wbs_codes}

    # Group rows by wbs_code_id, preserving insertion order
    # Use a sentinel for uncategorized items (wbs_code_id=None)
    _UNCATEGORIZED = uuid.UUID(int=0)
    groups: dict[uuid.UUID, dict] = {}
    group_order: list[uuid.UUID] = []
    for row in rows:
        wbs_id = row.wbs_code_id or _UNCATEGORIZED
        if wbs_id not in groups:
            groups[wbs_id] = {"history": None, "children": []}
            group_order.append(wbs_id)
        if row.claim_line_item_id is None and not row.adjustment_type:
            groups[wbs_id]["history"] = row
        else:
            groups[wbs_id]["children"].append(row)

    result: list[AggregatedWBSGroup] = []
    for wbs_id in group_order:
        g = groups[wbs_id]
        history = g["history"]
        children = g["children"]
        master = wbs_map.get(wbs_id)

        master_contract_sum = (master.contract_sum or ZERO) if master else ZERO
        previously_paid = history.previously_paid if history else ZERO
        history_claim = history.contractor_claim_to_date if history else ZERO

        history_rtp = history.recommended_this_period if history else ZERO
        child_rtp = sum((c.recommended_this_period for c in children), ZERO)
        child_claim = sum((c.contractor_claim_to_date for c in children), ZERO)

        rec_this_period = history_rtp + child_rtp
        total_recommended = previously_paid + rec_this_period
        contractor_claim_to_date = history_claim + child_claim
        variance = total_recommended - contractor_claim_to_date
        pct = (total_recommended / master_contract_sum * 100) if master_contract_sum else ZERO

        # Description: prefer history row, fall back to master record, fall back to first child
        if history:
            description = history.description
        elif master:
            description = master.description
        else:
            description = children[0].description if children else ""

        result.append(
            AggregatedWBSGroup(
                wbs_code_id=wbs_id if wbs_id != _UNCATEGORIZED else None,
                description=description,
                contract_sum=master_contract_sum,
                previously_paid=previously_paid,
                recommended_this_period=rec_this_period,
                total_recommended=total_recommended,
                contractor_claim_to_date=contractor_claim_to_date,
                variance_to_claim=variance,
                percentage=pct,
                history_row=history,
                child_rows=children,
            )
        )

    return result


def aggregate_variations(
    rows: Sequence[VariationItemLike],
    variations: Sequence[VariationLike],
) -> list[AggregatedVariationGroup]:
    """Group variation items by variation_id, compute totals.

    Source contractor_submission from master.
    """
    var_map: dict[uuid.UUID, VariationLike] = {v.id: v for v in variations}

    groups: dict[uuid.UUID, dict] = {}
    group_order: list[uuid.UUID] = []
    for row in rows:
        vid = row.variation_id
        if vid not in groups:
            groups[vid] = {"history": None, "children": []}
            group_order.append(vid)
        if row.claim_line_item_id is None and not row.adjustment_type:
            groups[vid]["history"] = row
        else:
            groups[vid]["children"].append(row)

    result: list[AggregatedVariationGroup] = []
    for vid in group_order:
        g = groups[vid]
        history = g["history"]
        children = g["children"]
        master = var_map.get(vid)

        submission = master.contractor_submission if master else ZERO
        previously_paid = history.previously_paid if history else ZERO
        history_claim = history.contractor_claim_to_date if history else ZERO

        history_rtp = history.recommended_this_period if history else ZERO
        child_rtp = sum((c.recommended_this_period for c in children), ZERO)
        child_claim = sum((c.contractor_claim_to_date for c in children), ZERO)

        rec_this_period = history_rtp + child_rtp
        total_recommended = previously_paid + rec_this_period
        contractor_claim_to_date = history_claim + child_claim
        variance = total_recommended - contractor_claim_to_date
        pct = (total_recommended / submission * 100) if submission else ZERO

        result.append(
            AggregatedVariationGroup(
                variation_id=vid,
                ci_number=master.ci_number if master else 0,
                contractor_ref=(master.contractor_ref or "") if master else "",
                description=master.description if master else "",
                contractor_submission=submission,
                previously_paid=previously_paid,
                recommended_this_period=rec_this_period,
                total_recommended=total_recommended,
                contractor_claim_to_date=contractor_claim_to_date,
                variance_to_claim=variance,
                percentage=pct,
                history_row=history,
                child_rows=children,
            )
        )

    result.sort(key=lambda g: g.ci_number)
    return result


def aggregate_provisional_sums(
    rows: Sequence[PSItemLike],
    provisional_sums: Sequence[PSLike],
) -> list[AggregatedPSGroup]:
    """Group PS items by provisional_sum_id, compute totals, source contract_sum from master."""
    ps_map: dict[uuid.UUID, PSLike] = {p.id: p for p in provisional_sums}

    groups: dict[uuid.UUID, dict] = {}
    group_order: list[uuid.UUID] = []
    for row in rows:
        psid = row.provisional_sum_id
        if psid not in groups:
            groups[psid] = {"history": None, "children": []}
            group_order.append(psid)
        if row.claim_line_item_id is None and not row.adjustment_type:
            groups[psid]["history"] = row
        else:
            groups[psid]["children"].append(row)

    result: list[AggregatedPSGroup] = []
    for psid in group_order:
        g = groups[psid]
        history = g["history"]
        children = g["children"]
        master = ps_map.get(psid)

        master_contract_sum = master.contract_sum if master else ZERO
        previously_paid = history.previously_paid if history else ZERO
        history_claim = history.contractor_claim_to_date if history else ZERO

        history_rtp = history.recommended_this_period if history else ZERO
        child_rtp = sum((c.recommended_this_period for c in children), ZERO)
        child_claim = sum((c.contractor_claim_to_date for c in children), ZERO)

        rec_this_period = history_rtp + child_rtp
        total_recommended = previously_paid + rec_this_period
        contractor_claim_to_date = history_claim + child_claim
        variance = total_recommended - contractor_claim_to_date
        pct = (total_recommended / master_contract_sum * 100) if master_contract_sum else ZERO

        result.append(
            AggregatedPSGroup(
                provisional_sum_id=psid,
                ps_number=master.ps_number if master else 0,
                description=master.description if master else "",
                contract_sum=master_contract_sum,
                previously_paid=previously_paid,
                recommended_this_period=rec_this_period,
                total_recommended=total_recommended,
                contractor_claim_to_date=contractor_claim_to_date,
                variance_to_claim=variance,
                percentage=pct,
                history_row=history,
                child_rows=children,
            )
        )

    result.sort(key=lambda g: g.ps_number)
    return result


def compute_assessment_totals(
    wbs_groups: list[AggregatedWBSGroup],
    var_groups: list[AggregatedVariationGroup],
    ps_groups: list[AggregatedPSGroup],
) -> AssessmentTotals:
    """Sum across all groups to produce assessment-level totals."""
    sub_cw = sum((g.total_recommended for g in wbs_groups), ZERO)
    sub_var = sum((g.total_recommended for g in var_groups), ZERO)
    sub_ps = sum((g.total_recommended for g in ps_groups), ZERO)

    total_recommended = sub_cw + sub_var + sub_ps

    value_claimed = (
        sum((g.contractor_claim_to_date for g in wbs_groups), ZERO)
        + sum((g.contractor_claim_to_date for g in var_groups), ZERO)
        + sum((g.contractor_claim_to_date for g in ps_groups), ZERO)
    )

    return AssessmentTotals(
        sub_contract_works=sub_cw,
        approved_variation_orders=sub_var,
        adjustment_to_provisional_sums=sub_ps,
        total_recommended=total_recommended,
        value_claimed_to_date=value_claimed,
        adjustments=total_recommended - value_claimed,
    )
