"""Jev decision-model matcher: WBS categorisation and variation / provisional-sum matching.

One Jev ``choice`` question per line item under bounded concurrency; answers are mapped
onto typed matches; WBS items Jev could not place (none / low confidence) are routed to the
LLM matcher. Transport, retry and error classification live in :class:`JevClient`.
"""

from __future__ import annotations

import functools
import logging
from collections.abc import Awaitable, Callable, Sequence
from typing import Final, cast

from pydantic import TypeAdapter

from app.clients.jev_client import JevClient
from app.clients.llm_client import LlmClient
from app.constants.enums import ClaimItemType, MatcherName, VpsKind
from app.exceptions import ExternalServiceError
from app.harness.matchers.data import read_parsed_items, vps_records, wbs_subcategories
from app.harness.matchers.llm import match_with_llm
from app.harness.models import PhaseRun
from app.harness.prompts import load_prompt
from app.harness.schemas import (
    ItemDecision,
    JevTuning,
    MatchOutcome,
    ParsedClaimItem,
    Subcat,
    VpsMatch,
    VpsRecord,
    WbsMatch,
)
from app.utils.concurrency import bounded_gather

logger = logging.getLogger(__name__)

NONE_OPTION = "__none__"
WBS_INSTRUCTIONS = load_prompt("jev_wbs_instructions").strip().format(none_option=NONE_OPTION)
VPS_INSTRUCTIONS = load_prompt("jev_vps_instructions").strip().format(none_option=NONE_OPTION)
VPS_KINDS: Final = frozenset({ClaimItemType.variation, ClaimItemType.provisional_sum})
WBS_MATCHES: Final = TypeAdapter(list[WbsMatch])
VPS_MATCHES: Final = TypeAdapter(list[VpsMatch])


def build_wbs_criteria(subcats: list[Subcat]) -> tuple[dict[str, str], dict[str, str]]:
    """Return (criteria, option_key -> subcat_id).

    Options are keyed by code, or by ``code#id`` when a code is shared by several
    subcategories, so resolving a choice never maps to the wrong subcategory.
    """
    counts: dict[str, int] = {}
    for s in subcats:
        counts[s.code] = counts.get(s.code, 0) + 1
    criteria: dict[str, str] = {}
    key_to_id: dict[str, str] = {}
    for s in subcats:
        key = s.code if counts[s.code] == 1 else f"{s.code}#{s.id}"
        sum_txt = f" — contract sum ${s.contract_sum:,.2f}" if s.contract_sum is not None else ""
        criteria[key] = f"{s.description}{sum_txt}".strip(" —")
        key_to_id[key] = s.id
    criteria[NONE_OPTION] = "None of the above subcategories fit this line item"
    return criteria, key_to_id


def build_vps_criteria(records: list[VpsRecord]) -> tuple[dict[str, str], set[str]]:
    """Return (criteria keyed by record id, the set of valid record ids)."""
    criteria = {r.id: f"{r.description} — ${r.value:,.2f}" if r.value is not None else r.description for r in records}
    criteria[NONE_OPTION] = "No existing record matches; create a new one"
    return criteria, {r.id for r in records}


def to_vps_match(
    decision: ItemDecision, vps_type: VpsKind, valid_ids: set[str], *, floor: float
) -> tuple[VpsMatch, bool]:
    """Build a ``VpsMatch`` from a Jev choice; return ``(match, out_of_criteria)``.

    A choice outside the supplied records (and not ``NONE_OPTION``) is a grounding
    violation; a valid choice below the confidence floor is treated as a new record.
    """
    idx, choice, conf = decision.item_index, decision.choice, decision.confidence
    in_valid = choice in valid_ids
    out_of_criteria = choice != NONE_OPTION and not in_valid
    if out_of_criteria:
        logger.warning("JevMatcher: out-of-criteria VPS choice %r for item %s; treating as new record", choice, idx)
    matched_id = choice if in_valid else None
    if matched_id is not None and conf < floor:
        logger.warning(
            "JevMatcher: VPS item %s confidence %.2f below floor %.2f; treating as new record", idx, conf, floor
        )
        matched_id = None
    return VpsMatch(item_index=idx, item_type=vps_type, matched_id=matched_id, confidence=conf), out_of_criteria


def to_wbs_match(decision: ItemDecision, key_to_id: dict[str, str], by_id: dict[str, Subcat]) -> tuple[WbsMatch, bool]:
    """Build a ``WbsMatch`` from a Jev choice; return ``(match, out_of_criteria)``.

    ``NONE_OPTION`` or an unknown choice yields a placeholder (``is_new=True``) that the
    residue phase later resolves; an unknown choice also flags a grounding violation.
    """
    idx, choice, conf = decision.item_index, decision.choice, decision.confidence
    known = choice in key_to_id
    out_of_criteria = choice != NONE_OPTION and not known
    if out_of_criteria:
        logger.warning("JevMatcher: out-of-criteria choice %r for item %s; treating as none/new", choice, idx)
    if choice is None or choice == NONE_OPTION or not known:
        return WbsMatch(item_index=idx, wbs_code="", is_new=True, confidence=conf), out_of_criteria
    sub = by_id[key_to_id[choice]]
    match = WbsMatch(
        item_index=idx,
        wbs_code=sub.code,
        wbs_code_id=sub.id,
        wbs_description=sub.description,
        parent_code=sub.parent_code,
        is_new=False,
        confidence=conf,
    )
    return match, out_of_criteria


async def decide_item(
    item: ParsedClaimItem, *, client: JevClient, criteria: dict[str, str], instructions: str
) -> ItemDecision:
    """One Jev choice for one item. Non-fatal failures (network, 5xx after retries,
    malformed answers) become ``failed=True``; fatal HTTP errors propagate."""
    qid = f"item_{item.item_index}"
    try:
        data = await client.choose(qid=qid, state=client.item_state(item), criteria=criteria, instructions=instructions)
        answer = data.answers[qid]
    except Exception as exc:
        if client.is_fatal(exc):
            raise
        logger.warning(
            "JevMatcher: Jev call for item %s failed (%s)", item.item_index, type(exc).__name__, exc_info=True
        )
        return ItemDecision(item_index=item.item_index, failed=True)
    return ItemDecision(
        item_index=item.item_index,
        choice=answer.choice,
        confidence=answer.confidence,
        input_tokens=data.usage.input_tokens,
    )


async def decide_items(
    items: list[ParsedClaimItem],
    *,
    client: JevClient,
    phase_name: str,
    criteria: dict[str, str],
    instructions: str,
    limit: int,
) -> list[ItemDecision]:
    """Budget-check, then fan out ``decide_item`` under ``limit`` concurrent calls."""
    client.check_context_budget(
        phase_name=phase_name,
        states=[client.item_state(i) for i in items],
        criteria=criteria,
        instructions=instructions,
    )
    decide = functools.partial(decide_item, client=client, criteria=criteria, instructions=instructions)
    return await bounded_gather(items, decide, limit=limit)


def residue_of(results: dict[int, WbsMatch], floor: float) -> set[int]:
    # Residue = Jev picked none/unknown OR confidence below the floor.
    return {idx for idx, m in results.items() if m.is_new or m.wbs_code_id is None or m.confidence < floor}


async def resolve_residue(
    residue: set[int], results: dict[int, WbsMatch], *, fallback: Callable[[], Awaitable[MatchOutcome]]
) -> tuple[dict[int, WbsMatch], MatchOutcome]:
    """Resolve none / low-confidence WBS items via the LLM fallback; return the merged results and the
    LLM ``MatchOutcome`` so the caller can fold in its token usage."""
    logger.info(
        "JevMatcher routing %d/%d WBS item(s) to LLM (none/low-confidence): %s",
        len(residue),
        len(results),
        sorted(residue),
    )
    outcome = await fallback()
    resolved = {m.item_index: m for m in outcome.output if m.item_index in residue}
    missing = residue - set(resolved)
    if missing:
        logger.warning("JevMatcher: residue items not resolved by LLM, keeping placeholder: %s", sorted(missing))
    return results | resolved, outcome


def vps_results(
    decisions: Sequence[ItemDecision], items: Sequence[ParsedClaimItem], valid_ids: set[str], *, floor: float
) -> tuple[dict[int, VpsMatch], int, int]:
    by_index = {i.item_index: i for i in items}
    results: dict[int, VpsMatch] = {}
    failed = ooc = 0
    for d in decisions:
        # Safe: items were pre-filtered to these two types.
        vps_type = cast(VpsKind, by_index[d.item_index].item_type)
        if d.failed:
            logger.warning("JevMatcher VPS item %s failed, treating as new record", d.item_index)
            failed += 1
            results[d.item_index] = VpsMatch(
                item_index=d.item_index, item_type=vps_type, matched_id=None, confidence=0.0
            )
            continue
        match, is_ooc = to_vps_match(d, vps_type, valid_ids, floor=floor)
        ooc += is_ooc
        results[d.item_index] = match
    return results, failed, ooc


async def match_vps(
    items: list[ParsedClaimItem], records: list[VpsRecord], *, phase_name: str, client: JevClient, tuning: JevTuning
) -> MatchOutcome:
    criteria, valid_ids = build_vps_criteria(records)
    decisions = await decide_items(
        items,
        client=client,
        phase_name=phase_name,
        criteria=criteria,
        instructions=VPS_INSTRUCTIONS,
        limit=tuning.max_concurrency,
    )
    results, failed, ooc = vps_results(decisions, items, valid_ids, floor=tuning.confidence_floor)
    if results and failed == len(results):
        logger.warning("JevMatcher: all %d VPS items failed Jev; failing the phase", len(results))
        raise ExternalServiceError("Jev matcher failed for every item")
    output = [results[k] for k in sorted(results)]
    return MatchOutcome(
        matcher=MatcherName.jev,
        output=output,
        output_json=VPS_MATCHES.dump_json(output).decode(),
        input_tokens=sum(d.input_tokens for d in decisions),
        output_tokens=0,
        fell_back=failed,
        out_of_criteria=ooc,
    )


def wbs_results(
    decisions: Sequence[ItemDecision], key_to_id: dict[str, str], by_id: dict[str, Subcat]
) -> tuple[dict[int, WbsMatch], int, int]:
    results: dict[int, WbsMatch] = {}
    failed = ooc = 0
    for d in decisions:
        if d.failed:
            logger.warning("JevMatcher item %s fell back to LLM", d.item_index)
            failed += 1
            results[d.item_index] = WbsMatch(item_index=d.item_index, wbs_code="", is_new=True, confidence=0.0)
            continue
        match, is_ooc = to_wbs_match(d, key_to_id, by_id)
        ooc += is_ooc
        results[d.item_index] = match
    if results and failed == len(results):
        logger.warning("JevMatcher: all %d items fell back to LLM (Jev unavailable)", len(results))
    return results, failed, ooc


async def match_wbs(
    items: list[ParsedClaimItem],
    subcats: list[Subcat],
    *,
    phase_name: str,
    client: JevClient,
    tuning: JevTuning,
    fallback: Callable[[], Awaitable[MatchOutcome]],
) -> MatchOutcome:
    criteria, key_to_id = build_wbs_criteria(subcats)
    decisions = await decide_items(
        items,
        client=client,
        phase_name=phase_name,
        criteria=criteria,
        instructions=WBS_INSTRUCTIONS,
        limit=tuning.max_concurrency,
    )
    results, failed, ooc = wbs_results(decisions, key_to_id, {s.id: s for s in subcats})
    residue = residue_of(results, tuning.confidence_floor)
    in_tok, out_tok = sum(d.input_tokens for d in decisions), 0
    if residue:
        results, llm_outcome = await resolve_residue(residue, results, fallback=fallback)
        in_tok += llm_outcome.input_tokens
        out_tok += llm_outcome.output_tokens
    output = [results[k] for k in sorted(results)]
    return MatchOutcome(
        matcher=MatcherName.jev,
        output=output,
        output_json=WBS_MATCHES.dump_json(output).decode(),
        input_tokens=in_tok,
        output_tokens=out_tok,
        fell_back=failed,
        residue=len(residue),
        out_of_criteria=ooc,
    )


async def match_with_jev(phase: PhaseRun, *, client: JevClient, llm: LlmClient, tuning: JevTuning) -> MatchOutcome:
    items = await read_parsed_items(phase.db, phase.session_id)
    if phase.phase_def.output_schema == list[VpsMatch]:
        in_scope = [i for i in items if i.item_type in VPS_KINDS]
        records = await vps_records(db=phase.db, project_id=phase.project_id)
        return await match_vps(in_scope, records, phase_name=phase.phase_def.name, client=client, tuning=tuning)
    in_scope = [i for i in items if i.item_type == ClaimItemType.contract_work]
    subcats = await wbs_subcategories(db=phase.db, project_id=phase.project_id)
    return await match_wbs(
        in_scope,
        subcats,
        phase_name=phase.phase_def.name,
        client=client,
        tuning=tuning,
        fallback=functools.partial(match_with_llm, phase, llm=llm),
    )
