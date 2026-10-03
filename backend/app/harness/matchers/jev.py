from __future__ import annotations

import asyncio
import json
import logging

from pydantic import TypeAdapter

from app.config import settings
from app.harness.matchers.base import MatchOutcome
from app.harness.matchers.data import Subcat, vps_records, wbs_subcategories
from app.harness.matchers.jev_client import call_decisions
from app.harness.matchers.llm import run_llm_matches
from app.harness.schemas import VpsMatch, WbsMatch
from app.repos import harness_repo

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


class JevMatcher:
    name = "jev"

    def __init__(self, decide_fn=None):
        self._decide = decide_fn or call_decisions

    async def _read_items(self, db, session_id) -> list[dict]:
        raw = await harness_repo.read_workspace_file(db, session_id, "parsed_claim.json")
        return json.loads(raw or "{}").get("line_items", [])

    async def _choose(self, qid, state, criteria):
        data = await self._decide(
            state=state,
            questions={qid: {"type": "choice", "instructions": _WBS_INSTRUCTIONS, "criteria": criteria}},
            model=settings.jev_model, url=settings.jev_decisions_url, api_key=settings.open_router_api_key,
        )
        return data["answers"][qid], data.get("usage", {})

    async def _resolve_residue(self, residue, phase_def, db, project_id, session_id) -> dict[int, WbsMatch]:
        outcome = await run_llm_matches(
            phase_def=phase_def, db=db, project_id=project_id, session_id=session_id,
        )
        return {m.item_index: m for m in outcome.output if m.item_index in residue}

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
        sem = asyncio.Semaphore(settings.jev_max_concurrency)
        results: dict[int, VpsMatch] = {}
        in_tok = 0

        async def run(item):
            nonlocal in_tok
            idx = item["item_index"]
            qid = f"item_{idx}"
            state = {"description": item.get("description", ""),
                     "contract_value": item.get("contract_value"),
                     "item_type": item.get("item_type")}
            async with sem:
                data = await self._decide(
                    state=state,
                    questions={qid: {"type": "choice", "instructions": _VPS_INSTRUCTIONS, "criteria": criteria}},
                    model=settings.jev_model, url=settings.jev_decisions_url,
                    api_key=settings.open_router_api_key,
                )
            ans = data["answers"][qid]
            in_tok += int(data.get("usage", {}).get("input_tokens", 0))
            choice = ans.get("choice")
            if choice != NONE_OPTION and choice not in valid_ids:
                logger.warning("JevMatcher: out-of-criteria VPS choice %r for item %s; treating as new record",
                               choice, idx)
            results[idx] = VpsMatch(
                item_index=idx, item_type=item["item_type"],
                matched_id=choice if choice in valid_ids else None,
                confidence=float(ans.get("confidence", 0.0)),
            )

        await asyncio.gather(*(run(i) for i in items))
        output = [results[k] for k in sorted(results)]
        return MatchOutcome(
            output=output,
            output_json=TypeAdapter(list[VpsMatch]).dump_json(output).decode(),
            input_tokens=in_tok, output_tokens=0,
        )

    async def _match_wbs(self, phase_def, db, project_id, session_id) -> MatchOutcome:
        items = [i for i in await self._read_items(db, session_id) if i.get("item_type") == "contract_work"]
        subcats = await wbs_subcategories(db=db, project_id=project_id)
        criteria, key_to_id = build_wbs_criteria(subcats)
        by_id = {s.id: s for s in subcats}

        sem = asyncio.Semaphore(settings.jev_max_concurrency)
        results: dict[int, WbsMatch] = {}
        in_tok = 0

        async def run(item):
            nonlocal in_tok
            idx = item["item_index"]
            qid = f"item_{idx}"
            state = {"description": item.get("description", ""),
                     "contract_value": item.get("contract_value"),
                     "item_type": item.get("item_type")}
            async with sem:
                ans, usage = await self._choose(qid, state, criteria)
            in_tok += int(usage.get("input_tokens", 0))
            choice = ans.get("choice")
            conf = float(ans.get("confidence", 0.0))
            if choice != NONE_OPTION and choice not in key_to_id:
                logger.warning("JevMatcher: out-of-criteria choice %r for item %s; treating as none/new", choice, idx)
            if choice == NONE_OPTION or choice not in key_to_id:
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
        residue = {idx for idx, m in results.items()
                   if m.is_new or m.wbs_code_id is None or m.confidence < floor}
        if residue:
            logger.info("JevMatcher routing %d/%d WBS item(s) to LLM (none/low-confidence): %s",
                        len(residue), len(results), sorted(residue))
            resolved = await self._resolve_residue(residue, phase_def, db, project_id, session_id)
            missing = residue - set(resolved)
            if missing:
                logger.warning("JevMatcher: residue items not resolved by LLM, keeping placeholder: %s",
                               sorted(missing))
            results.update(resolved)
        output = [results[k] for k in sorted(results)]
        return MatchOutcome(
            output=output,
            output_json=TypeAdapter(list[WbsMatch]).dump_json(output).decode(),
            input_tokens=in_tok, output_tokens=0,
        )
