from __future__ import annotations

import asyncio
import logging
import uuid
from typing import TYPE_CHECKING, Literal, cast

from pydantic import TypeAdapter

from app.config import settings
from app.harness.matchers.base import MatchOutcome
from app.harness.matchers.data import Subcat, read_parsed_items, vps_records, wbs_subcategories
from app.harness.matchers.jev_client import (
    DecideFn,
    call_decisions,
    check_context_budget,
    decide_with_retry,
    is_fatal,
    item_state,
)
from app.harness.matchers.llm import run_llm_matches
from app.harness.schemas import ParsedClaimItem, VpsMatch, WbsMatch

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.harness.models import PhaseDefinition

logger = logging.getLogger(__name__)

NONE_OPTION = "__none__"
_WBS_INSTRUCTIONS = (
    "Which WBS subcategory does this line item belong to? Prefer an exact or near "
    "(within ~1%) contract-sum match over description similarity. Choose "
    f"'{NONE_OPTION}' only if no subcategory fits."
)
_VPS_INSTRUCTIONS = (
    "Which existing record does this item match? Match on description, then value "
    f"within ~20%. Choose '{NONE_OPTION}' to create a new record."
)


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


def _vps_match(
    idx: int,
    vps_type: Literal["variation", "provisional_sum"],
    choice: str | None,
    conf: float,
    valid_ids: set[str],
) -> tuple[VpsMatch, bool]:
    """Build a ``VpsMatch`` from a Jev choice; return ``(match, out_of_criteria)``.

    A choice outside the supplied records (and not the explicit ``NONE_OPTION``) is a
    grounding violation; a valid choice below the confidence floor is treated as new.
    """
    in_valid = choice in valid_ids
    out_of_criteria = choice != NONE_OPTION and not in_valid
    if out_of_criteria:
        logger.warning(
            "JevMatcher: out-of-criteria VPS choice %r for item %s; treating as new record",
            choice,
            idx,
        )
    matched_id = choice if in_valid else None
    floor = settings.jev_confidence_floor
    if matched_id is not None and conf < floor:
        logger.warning(
            "JevMatcher: VPS item %s confidence %.2f below floor %.2f; treating as new record",
            idx,
            conf,
            floor,
        )
        matched_id = None
    return VpsMatch(
        item_index=idx, item_type=vps_type, matched_id=matched_id, confidence=conf
    ), out_of_criteria


def _wbs_match(
    idx: int,
    choice: str | None,
    conf: float,
    key_to_id: dict[str, str],
    by_id: dict[str, Subcat],
) -> tuple[WbsMatch, bool]:
    """Build a ``WbsMatch`` from a Jev choice; return ``(match, out_of_criteria)``.

    ``NONE_OPTION`` or an unknown choice yields a placeholder (``is_new=True``) that the
    residue phase later mints into a real code; an unknown choice also flags a grounding
    violation.
    """
    known = choice in key_to_id
    out_of_criteria = choice != NONE_OPTION and not known
    if out_of_criteria:
        logger.warning(
            "JevMatcher: out-of-criteria choice %r for item %s; treating as none/new", choice, idx
        )
    if choice == NONE_OPTION or not known:
        return WbsMatch(item_index=idx, wbs_code="", is_new=True, confidence=conf), out_of_criteria
    sub = by_id[key_to_id[choice]]
    return WbsMatch(
        item_index=idx,
        wbs_code=sub.code,
        wbs_code_id=sub.id,
        wbs_description=sub.description,
        parent_code=sub.parent_code,
        is_new=False,
        confidence=conf,
    ), out_of_criteria


class JevMatcher:
    name = "jev"

    def __init__(self, decide_fn: DecideFn | None = None) -> None:
        self._decide: DecideFn = decide_fn or call_decisions

    async def _resolve_residue(
        self,
        residue: set[int],
        phase_def: PhaseDefinition,
        db: AsyncSession,
        project_id: uuid.UUID,
        session_id: uuid.UUID,
    ) -> tuple[dict[int, WbsMatch], MatchOutcome]:
        outcome = await run_llm_matches(
            phase_def=phase_def,
            db=db,
            project_id=project_id,
            session_id=session_id,
        )
        return {m.item_index: m for m in outcome.output if m.item_index in residue}, outcome

    async def _merge_residue(
        self,
        residue: set[int],
        results: dict[int, WbsMatch],
        phase_def: PhaseDefinition,
        db: AsyncSession,
        project_id: uuid.UUID,
        session_id: uuid.UUID,
    ) -> MatchOutcome:
        """Resolve none/low-confidence WBS items via the LLM and merge them into ``results``.

        Returns the LLM ``MatchOutcome`` so the caller can fold in its token/cost usage.
        """
        logger.info(
            "JevMatcher routing %d/%d WBS item(s) to LLM (none/low-confidence): %s",
            len(residue),
            len(results),
            sorted(residue),
        )
        resolved, outcome = await self._resolve_residue(
            residue, phase_def, db, project_id, session_id
        )
        missing = residue - set(resolved)
        if missing:
            logger.warning(
                "JevMatcher: residue items not resolved by LLM, keeping placeholder: %s",
                sorted(missing),
            )
        results.update(resolved)
        return outcome

    async def match(
        self,
        *,
        phase_def: PhaseDefinition,
        db: AsyncSession,
        project_id: uuid.UUID,
        session_id: uuid.UUID,
    ) -> MatchOutcome:
        if phase_def.output_schema == list[VpsMatch]:
            return await self._match_vps(phase_def, db, project_id, session_id)
        return await self._match_wbs(phase_def, db, project_id, session_id)

    async def _match_vps(
        self,
        phase_def: PhaseDefinition,
        db: AsyncSession,
        project_id: uuid.UUID,
        session_id: uuid.UUID,
    ) -> MatchOutcome:
        kinds = {"variation", "provisional_sum"}
        items = [i for i in await read_parsed_items(db, session_id) if i.item_type in kinds]
        records = await vps_records(db=db, project_id=project_id)
        criteria = {
            r.id: f"{r.description} — ${r.value:,.2f}" if r.value is not None else r.description
            for r in records
        }
        criteria[NONE_OPTION] = "No existing record matches; create a new one"
        valid_ids = {r.id for r in records}
        check_context_budget(
            phase_name=phase_def.name,
            states=[item_state(i) for i in items],
            criteria=criteria,
            instructions=_VPS_INSTRUCTIONS,
        )
        sem = asyncio.Semaphore(settings.jev_max_concurrency)
        results: dict[int, VpsMatch] = {}
        failed: set[int] = set()
        ooc: set[int] = set()  # out-of-criteria (grounding) violations
        in_tok = 0

        async def run(item: ParsedClaimItem) -> None:
            nonlocal in_tok
            idx = item.item_index
            # Safe: items were pre-filtered to these two types above.
            vps_type = cast(Literal["variation", "provisional_sum"], item.item_type)
            qid = f"item_{idx}"
            state = item_state(item)
            try:
                async with sem:
                    data = await decide_with_retry(
                        self._decide,
                        qid=qid,
                        state=state,
                        criteria=criteria,
                        instructions=_VPS_INSTRUCTIONS,
                        model=settings.jev_model,
                        url=settings.jev_decisions_url,
                        api_key=settings.open_router_api_key,
                    )
                ans = data.answers[qid]
                tok = data.usage.input_tokens
            except Exception as e:
                if is_fatal(e):
                    raise
                logger.warning(
                    "JevMatcher VPS item %s failed, treating as new record: %s: %r",
                    idx,
                    type(e).__name__,
                    e,
                    exc_info=True,
                )
                failed.add(idx)
                results[idx] = VpsMatch(
                    item_index=idx, item_type=vps_type, matched_id=None, confidence=0.0
                )
                return
            in_tok += tok
            match, is_ooc = _vps_match(idx, vps_type, ans.choice, ans.confidence, valid_ids)
            if is_ooc:
                ooc.add(idx)
            results[idx] = match

        await asyncio.gather(*(run(i) for i in items))
        if results and len(failed) == len(results):
            logger.warning(
                "JevMatcher: all %d VPS items failed Jev; created as new records", len(results)
            )
        output = [results[k] for k in sorted(results)]
        return MatchOutcome(
            output=output,
            output_json=TypeAdapter(list[VpsMatch]).dump_json(output).decode(),
            input_tokens=in_tok,
            output_tokens=0,
            fell_back=len(failed),
            out_of_criteria=len(ooc),
        )

    async def _match_wbs(
        self,
        phase_def: PhaseDefinition,
        db: AsyncSession,
        project_id: uuid.UUID,
        session_id: uuid.UUID,
    ) -> MatchOutcome:
        items = [
            i for i in await read_parsed_items(db, session_id) if i.item_type == "contract_work"
        ]
        subcats = await wbs_subcategories(db=db, project_id=project_id)
        criteria, key_to_id = build_wbs_criteria(subcats)
        by_id = {s.id: s for s in subcats}

        check_context_budget(
            phase_name=phase_def.name,
            states=[item_state(i) for i in items],
            criteria=criteria,
            instructions=_WBS_INSTRUCTIONS,
        )
        sem = asyncio.Semaphore(settings.jev_max_concurrency)
        results: dict[int, WbsMatch] = {}
        failed: set[int] = set()
        ooc: set[int] = set()  # out-of-criteria (grounding) violations
        in_tok = 0
        out_tok = 0
        cost = 0.0
        have_cost = False

        async def run(item: ParsedClaimItem) -> None:
            nonlocal in_tok
            idx = item.item_index
            qid = f"item_{idx}"
            state = item_state(item)
            try:
                async with sem:
                    data = await decide_with_retry(
                        self._decide,
                        qid=qid,
                        state=state,
                        criteria=criteria,
                        instructions=_WBS_INSTRUCTIONS,
                        model=settings.jev_model,
                        url=settings.jev_decisions_url,
                        api_key=settings.open_router_api_key,
                    )
                ans = data.answers[qid]
                tok = data.usage.input_tokens
            except Exception as e:
                if is_fatal(e):
                    raise
                logger.warning(
                    "JevMatcher item %s fell back to LLM: %s: %r",
                    idx,
                    type(e).__name__,
                    e,
                    exc_info=True,
                )
                failed.add(idx)
                results[idx] = WbsMatch(item_index=idx, wbs_code="", is_new=True, confidence=0.0)
                return
            in_tok += tok
            match, is_ooc = _wbs_match(idx, ans.choice, ans.confidence, key_to_id, by_id)
            if is_ooc:
                ooc.add(idx)
            results[idx] = match

        await asyncio.gather(*(run(i) for i in items))

        # Residue = Jev picked none/unknown OR confidence below the floor.
        floor = settings.jev_confidence_floor
        residue: set[int] = {
            idx
            for idx, m in results.items()
            if m.is_new or m.wbs_code_id is None or m.confidence < floor
        }
        if results and len(failed) == len(results):
            logger.warning(
                "JevMatcher: all %d items fell back to LLM (Jev unavailable)", len(results)
            )
        if residue:
            llm_outcome = await self._merge_residue(
                residue, results, phase_def, db, project_id, session_id
            )
            in_tok += llm_outcome.input_tokens
            out_tok += llm_outcome.output_tokens
            if llm_outcome.cost_usd is not None:
                cost += llm_outcome.cost_usd
                have_cost = True
        output = [results[k] for k in sorted(results)]
        return MatchOutcome(
            output=output,
            output_json=TypeAdapter(list[WbsMatch]).dump_json(output).decode(),
            input_tokens=in_tok,
            output_tokens=out_tok,
            cost_usd=cost if have_cost else None,
            fell_back=len(failed),
            residue=len(residue),
            out_of_criteria=len(ooc),
        )
