from __future__ import annotations

import asyncio
import json
import logging
import random

import httpx
from pydantic import TypeAdapter

from app.config import settings
from app.harness.matchers.base import MatchOutcome
from app.harness.matchers.data import Subcat, vps_records, wbs_subcategories
from app.harness.matchers.jev_client import call_decisions
from app.harness.matchers.llm import run_llm_matches
from app.harness.schemas import VpsMatch, WbsMatch
from app.repos import harness_repo

logger = logging.getLogger(__name__)

_RETRYABLE = {429, 529}
_FATAL = {400, 401, 402, 403, 404, 422}  # config/auth/credit errors: raise, never fall back
_MAX_CONTEXT_TOKENS = 32_000
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


def _item_state(item: dict) -> dict:
    return {"description": item.get("description", ""),
            "contract_value": item.get("contract_value"),
            "item_type": item.get("item_type")}


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


class JevMatcher:
    name = "jev"

    def __init__(self, decide_fn=None):
        self._decide = decide_fn or call_decisions

    async def _read_items(self, db, session_id) -> list[dict]:
        raw = await harness_repo.read_workspace_file(db, session_id, "parsed_claim.json")
        if not raw:
            raise ValueError(f"parsed_claim.json missing or empty for session {session_id}")
        parsed = json.loads(raw)
        if not isinstance(parsed, dict) or "line_items" not in parsed:
            raise ValueError(f"parsed_claim.json has no 'line_items' for session {session_id}")
        return parsed["line_items"]

    async def _decide_with_retry(self, qid, state, criteria, instructions, max_attempts=4):
        """Call Jev, retrying 429/529 with exponential backoff + jitter.

        Config/auth/credit errors (_FATAL) are raised immediately (never fall back).
        Any other terminal failure is logged and re-raised.
        """
        delay = 0.5
        for attempt in range(1, max_attempts + 1):
            try:
                return await self._decide(
                    state=state,
                    questions={qid: {"type": "choice", "instructions": instructions, "criteria": criteria}},
                    model=settings.jev_model, url=settings.jev_decisions_url,
                    api_key=settings.open_router_api_key,
                )
            except httpx.HTTPStatusError as e:
                code = e.response.status_code
                if code in _FATAL:
                    raise
                if code in _RETRYABLE and attempt < max_attempts:
                    await asyncio.sleep(delay + random.uniform(0, delay))
                    delay *= 2
                    continue
                logger.warning("Jev decision %s failed after %d attempt(s): HTTP %s", qid, attempt, code)
                raise

    @staticmethod
    def _check_context(phase_def, states, criteria, instructions) -> None:
        """Reject requests whose serialized size exceeds ~32k tokens (chars/4 proxy)."""
        worst = max(states, key=lambda s: len(json.dumps(s, default=str)), default={})
        payload = json.dumps(
            {"state": worst, "questions": {"item_0": {"instructions": instructions, "criteria": criteria}}},
            default=str,
        )
        if len(payload) / 4 > _MAX_CONTEXT_TOKENS:
            raise ValueError(f"Jev request for '{phase_def.name}' exceeds 32k context")

    @staticmethod
    def _is_fatal(e: Exception) -> bool:
        return isinstance(e, httpx.HTTPStatusError) and e.response.status_code in _FATAL

    async def _resolve_residue(
        self, residue, phase_def, db, project_id, session_id
    ) -> tuple[dict[int, WbsMatch], MatchOutcome]:
        outcome = await run_llm_matches(
            phase_def=phase_def, db=db, project_id=project_id, session_id=session_id,
        )
        return {m.item_index: m for m in outcome.output if m.item_index in residue}, outcome

    async def match(self, *, phase_def, db, project_id, session_id) -> MatchOutcome:
        if phase_def.output_schema == list[VpsMatch]:
            return await self._match_vps(phase_def, db, project_id, session_id)
        return await self._match_wbs(phase_def, db, project_id, session_id)

    async def _match_vps(self, phase_def, db, project_id, session_id) -> MatchOutcome:
        kinds = {"variation", "provisional_sum"}
        items = [i for i in await self._read_items(db, session_id) if i.get("item_type") in kinds]
        records = await vps_records(db=db, project_id=project_id)
        criteria = {
            r.id: f"{r.description} — ${r.value:,.2f}" if r.value is not None else r.description
            for r in records
        }
        criteria[NONE_OPTION] = "No existing record matches; create a new one"
        valid_ids = {r.id for r in records}
        self._check_context(phase_def, [_item_state(i) for i in items], criteria, _VPS_INSTRUCTIONS)
        sem = asyncio.Semaphore(settings.jev_max_concurrency)
        results: dict[int, VpsMatch] = {}
        failed: set[int] = set()
        in_tok = 0

        async def run(item):
            nonlocal in_tok
            idx = item["item_index"]
            qid = f"item_{idx}"
            state = _item_state(item)
            try:
                async with sem:
                    data = await self._decide_with_retry(qid, state, criteria, _VPS_INSTRUCTIONS)
                ans = data["answers"][qid]
                choice = ans.get("choice")
                conf = float(ans.get("confidence", 0.0))
                in_valid = choice in valid_ids
                tok = int(data.get("usage", {}).get("input_tokens", 0))
            except Exception as e:
                if self._is_fatal(e):
                    raise
                logger.warning("JevMatcher VPS item %s failed, treating as new record: %s: %r",
                               idx, type(e).__name__, e, exc_info=True)
                failed.add(idx)
                results[idx] = VpsMatch(item_index=idx, item_type=item["item_type"],
                                        matched_id=None, confidence=0.0)
                return
            in_tok += tok
            if choice != NONE_OPTION and not in_valid:
                logger.warning("JevMatcher: out-of-criteria VPS choice %r for item %s; treating as new record",
                               choice, idx)
            matched_id = choice if in_valid else None
            floor = settings.jev_confidence_floor
            if matched_id is not None and conf < floor:
                logger.warning(
                    "JevMatcher: VPS item %s confidence %.2f below floor %.2f; treating as new record",
                    idx, conf, floor)
                matched_id = None
            results[idx] = VpsMatch(
                item_index=idx, item_type=item["item_type"],
                matched_id=matched_id, confidence=conf,
            )

        await asyncio.gather(*(run(i) for i in items))
        if results and len(failed) == len(results):
            logger.warning("JevMatcher: all %d VPS items failed Jev; created as new records", len(results))
        output = [results[k] for k in sorted(results)]
        return MatchOutcome(
            output=output,
            output_json=TypeAdapter(list[VpsMatch]).dump_json(output).decode(),
            input_tokens=in_tok, output_tokens=0,
            fell_back=len(failed),
        )

    async def _match_wbs(self, phase_def, db, project_id, session_id) -> MatchOutcome:
        items = [i for i in await self._read_items(db, session_id) if i.get("item_type") == "contract_work"]
        subcats = await wbs_subcategories(db=db, project_id=project_id)
        criteria, key_to_id = build_wbs_criteria(subcats)
        by_id = {s.id: s for s in subcats}

        self._check_context(phase_def, [_item_state(i) for i in items], criteria, _WBS_INSTRUCTIONS)
        sem = asyncio.Semaphore(settings.jev_max_concurrency)
        results: dict[int, WbsMatch] = {}
        failed: set[int] = set()
        in_tok = 0
        out_tok = 0
        cost = 0.0
        have_cost = False

        async def run(item):
            nonlocal in_tok
            idx = item["item_index"]
            qid = f"item_{idx}"
            state = _item_state(item)
            try:
                async with sem:
                    data = await self._decide_with_retry(qid, state, criteria, _WBS_INSTRUCTIONS)
                ans = data["answers"][qid]
                choice = ans.get("choice")
                conf = float(ans.get("confidence", 0.0))
                known = choice in key_to_id
                tok = int(data.get("usage", {}).get("input_tokens", 0))
            except Exception as e:
                if self._is_fatal(e):
                    raise
                logger.warning("JevMatcher item %s fell back to LLM: %s: %r",
                               idx, type(e).__name__, e, exc_info=True)
                failed.add(idx)
                results[idx] = WbsMatch(item_index=idx, wbs_code="", is_new=True, confidence=0.0)
                return
            in_tok += tok
            if choice != NONE_OPTION and not known:
                logger.warning("JevMatcher: out-of-criteria choice %r for item %s; treating as none/new", choice, idx)
            if choice == NONE_OPTION or not known:
                # No existing code chosen. Placeholder; Task 8 mints the real residue code.
                results[idx] = WbsMatch(item_index=idx, wbs_code="", is_new=True, confidence=conf)
            else:
                sub = by_id[key_to_id[choice]]
                results[idx] = WbsMatch(
                    item_index=idx, wbs_code=sub.code, wbs_code_id=sub.id,
                    wbs_description=sub.description, parent_code=sub.parent_code,
                    is_new=False, confidence=conf,
                )

        await asyncio.gather(*(run(i) for i in items))

        # Residue = Jev picked none/unknown OR confidence below the floor.
        floor = settings.jev_confidence_floor
        residue: set[int] = {idx for idx, m in results.items()
                   if m.is_new or m.wbs_code_id is None or m.confidence < floor}
        if results and len(failed) == len(results):
            logger.warning("JevMatcher: all %d items fell back to LLM (Jev unavailable)", len(results))
        if residue:
            logger.info("JevMatcher routing %d/%d WBS item(s) to LLM (none/low-confidence): %s",
                        len(residue), len(results), sorted(residue))
            resolved, llm_outcome = await self._resolve_residue(residue, phase_def, db, project_id, session_id)
            in_tok += llm_outcome.input_tokens
            out_tok += llm_outcome.output_tokens
            if llm_outcome.cost_usd is not None:
                cost += llm_outcome.cost_usd
                have_cost = True
            missing = residue - set(resolved)
            if missing:
                logger.warning("JevMatcher: residue items not resolved by LLM, keeping placeholder: %s",
                               sorted(missing))
            results.update(resolved)
        output = [results[k] for k in sorted(results)]
        return MatchOutcome(
            output=output,
            output_json=TypeAdapter(list[WbsMatch]).dump_json(output).decode(),
            input_tokens=in_tok, output_tokens=out_tok,
            cost_usd=cost if have_cost else None,
            fell_back=len(failed), residue=len(residue),
        )
