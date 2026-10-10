"""Jev decision-model matcher: WBS categorisation and variation / provisional-sum matching.

One Jev ``choice`` question per line item under bounded concurrency; answers are mapped
onto typed matches; WBS items Jev could not place (none / low confidence) are routed to the
LLM matcher. Transport, retry and error classification live in :class:`JevClient`.
"""

from __future__ import annotations

import functools
import logging
import uuid
from typing import TYPE_CHECKING, Literal, cast

from pydantic import TypeAdapter

from app.clients.jev_client import JevClient
from app.config import settings
from app.harness.matchers.data import read_parsed_items, vps_records, wbs_subcategories
from app.harness.matchers.llm import run_llm_matches
from app.harness.prompts import load_prompt
from app.harness.schemas import ItemDecision, MatchOutcome, ParsedClaimItem, Subcat, VpsMatch, VpsRecord, WbsMatch
from app.utils.concurrency import bounded_gather

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.harness.models import PhaseDefinition

logger = logging.getLogger(__name__)

NONE_OPTION = "__none__"
WBS_INSTRUCTIONS = load_prompt("jev_wbs_instructions").strip().format(none_option=NONE_OPTION)
VPS_INSTRUCTIONS = load_prompt("jev_vps_instructions").strip().format(none_option=NONE_OPTION)
VpsType = Literal["variation", "provisional_sum"]


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


def to_vps_match(decision: ItemDecision, vps_type: VpsType, valid_ids: set[str]) -> tuple[VpsMatch, bool]:
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
    floor = settings.jev_confidence_floor
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


class JevMatcher:
    name = "jev"

    def __init__(self, client: JevClient | None = None) -> None:
        self.client = client or JevClient.from_settings(settings)

    async def match(
        self, *, phase_def: PhaseDefinition, db: AsyncSession, project_id: uuid.UUID, session_id: uuid.UUID
    ) -> MatchOutcome:
        if phase_def.output_schema == list[VpsMatch]:
            return await self.match_vps(phase_def=phase_def, db=db, project_id=project_id, session_id=session_id)
        return await self.match_wbs(phase_def=phase_def, db=db, project_id=project_id, session_id=session_id)

    async def decide_item(self, item: ParsedClaimItem, *, criteria: dict[str, str], instructions: str) -> ItemDecision:
        """One Jev choice for one item. Non-fatal failures (network, 5xx after retries,
        malformed answers) become ``failed=True``; fatal HTTP errors propagate."""
        qid = f"item_{item.item_index}"
        try:
            data = await self.client.choose(
                qid=qid, state=self.client.item_state(item), criteria=criteria, instructions=instructions
            )
            answer = data.answers[qid]
        except Exception as exc:
            if self.client.is_fatal(exc):
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
        self, items: list[ParsedClaimItem], *, phase_name: str, criteria: dict[str, str], instructions: str
    ) -> list[ItemDecision]:
        """Budget-check, then fan out ``decide_item`` under ``settings.jev_max_concurrency``."""
        self.client.check_context_budget(
            phase_name=phase_name,
            states=[self.client.item_state(i) for i in items],
            criteria=criteria,
            instructions=instructions,
        )
        decide = functools.partial(self.decide_item, criteria=criteria, instructions=instructions)
        return await bounded_gather(items, decide, limit=settings.jev_max_concurrency)

    async def resolve_residue(
        self,
        residue: set[int],
        results: dict[int, WbsMatch],
        *,
        phase_def: PhaseDefinition,
        db: AsyncSession,
        project_id: uuid.UUID,
        session_id: uuid.UUID,
    ) -> MatchOutcome:
        """Resolve none / low-confidence WBS items via the LLM and merge them into ``results``.

        Returns the LLM ``MatchOutcome`` so the caller can fold in its token/cost usage.
        """
        logger.info(
            "JevMatcher routing %d/%d WBS item(s) to LLM (none/low-confidence): %s",
            len(residue),
            len(results),
            sorted(residue),
        )
        outcome = await run_llm_matches(phase_def=phase_def, db=db, project_id=project_id, session_id=session_id)
        resolved = {m.item_index: m for m in outcome.output if m.item_index in residue}
        missing = residue - set(resolved)
        if missing:
            logger.warning("JevMatcher: residue items not resolved by LLM, keeping placeholder: %s", sorted(missing))
        results.update(resolved)
        return outcome

    async def match_vps(
        self, *, phase_def: PhaseDefinition, db: AsyncSession, project_id: uuid.UUID, session_id: uuid.UUID
    ) -> MatchOutcome:
        kinds = {"variation", "provisional_sum"}
        items = [i for i in await read_parsed_items(db, session_id) if i.item_type in kinds]
        records = await vps_records(db=db, project_id=project_id)
        criteria, valid_ids = build_vps_criteria(records)
        decisions = await self.decide_items(
            items, phase_name=phase_def.name, criteria=criteria, instructions=VPS_INSTRUCTIONS
        )
        by_index = {i.item_index: i for i in items}
        results: dict[int, VpsMatch] = {}
        failed = ooc = 0
        for d in decisions:
            # Safe: items were pre-filtered to these two types above.
            vps_type = cast(VpsType, by_index[d.item_index].item_type)
            if d.failed:
                logger.warning("JevMatcher VPS item %s failed, treating as new record", d.item_index)
                failed += 1
                results[d.item_index] = VpsMatch(
                    item_index=d.item_index, item_type=vps_type, matched_id=None, confidence=0.0
                )
                continue
            match, is_ooc = to_vps_match(d, vps_type, valid_ids)
            ooc += is_ooc
            results[d.item_index] = match
        if results and failed == len(results):
            logger.warning("JevMatcher: all %d VPS items failed Jev; created as new records", len(results))
        output = [results[k] for k in sorted(results)]
        return MatchOutcome(
            output=output,
            output_json=TypeAdapter(list[VpsMatch]).dump_json(output).decode(),
            input_tokens=sum(d.input_tokens for d in decisions),
            output_tokens=0,
            fell_back=failed,
            out_of_criteria=ooc,
        )

    async def match_wbs(
        self, *, phase_def: PhaseDefinition, db: AsyncSession, project_id: uuid.UUID, session_id: uuid.UUID
    ) -> MatchOutcome:
        items = [i for i in await read_parsed_items(db, session_id) if i.item_type == "contract_work"]
        subcats = await wbs_subcategories(db=db, project_id=project_id)
        criteria, key_to_id = build_wbs_criteria(subcats)
        by_id = {s.id: s for s in subcats}
        decisions = await self.decide_items(
            items, phase_name=phase_def.name, criteria=criteria, instructions=WBS_INSTRUCTIONS
        )
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

        # Residue = Jev picked none/unknown OR confidence below the floor.
        floor = settings.jev_confidence_floor
        residue = {idx for idx, m in results.items() if m.is_new or m.wbs_code_id is None or m.confidence < floor}
        in_tok = sum(d.input_tokens for d in decisions)
        out_tok = 0
        cost: float | None = None
        if residue:
            llm = await self.resolve_residue(
                residue, results, phase_def=phase_def, db=db, project_id=project_id, session_id=session_id
            )
            in_tok += llm.input_tokens
            out_tok += llm.output_tokens
            cost = llm.cost_usd
        output = [results[k] for k in sorted(results)]
        return MatchOutcome(
            output=output,
            output_json=TypeAdapter(list[WbsMatch]).dump_json(output).decode(),
            input_tokens=in_tok,
            output_tokens=out_tok,
            cost_usd=cost,
            fell_back=failed,
            residue=len(residue),
            out_of_criteria=ooc,
        )
