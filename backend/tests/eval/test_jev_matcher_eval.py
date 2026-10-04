"""
EVAL (not a test): measures the quality DISTRIBUTION of the Jev matcher against
the committed golden dataset, over N nondeterministic runs.

Why this is an eval and not a test: the matcher calls the real Jev decisions API
and the real LLM residue resolver, neither pinned to temperature 0. A single run
proves nothing; running phases 4-5 N times and reporting the min/max/mean/sd of
match accuracy is what shows whether the harness performs.

Design (settled by grilling):
  * Deterministic upstream (phases 0-3) runs ONCE per claim; parsed_claim.json is
    frozen. Only the nondeterministic matcher phases (4 WBS, 5 VPS) run N times,
    so the spread is attributable to the matcher, not the plumbing.
  * Ground truth: the unambiguous exact contract-sum mapping (a claim item whose
    contract_value equals exactly one WBS subcategory's contract_sum). Same honest
    basis the proto-eval (test_e2e_jev_pipeline) uses.
  * Each claim uploads to a FRESH project -> no pre-existing variation/PS records,
    so VPS "accuracy" is a no-false-positive check (every item should be new).
  * Jev-alone vs post-residue: both scored from ONE set of Jev calls by memoising
    the Jev responses across two matcher passes (pass A stubs the residue resolver,
    pass B runs it). The gap is the value the LLM residue fallback adds.
  * Grounding / hallucination: MatchOutcome.out_of_criteria counts selections the
    model named that were never offered — a structural grounding violation.
  * Calibration: Jev's confidence paired with whether Jev was right.
  * Gate: mean post-residue accuracy, WBS and VPS independently (Q19).

Run it:   just eval            (N=10)   |   just eval runs=3   (demo)
Requires: OPEN_ROUTER_API_KEY, Docker (testcontainers) or E2E_DATABASE_URL, and
the Gilmours claim PDFs. Skips cleanly when the key or PDFs are absent.
"""
from __future__ import annotations

import datetime
import json
import os
from pathlib import Path

import pytest
from httpx import AsyncClient

import app.harness.matchers.jev as jev_module
from app.config import settings
from app.harness.definitions.claim_parse import claim_parse_definition
from app.harness.matchers.base import MatchOutcome
from app.harness.matchers.jev import JevMatcher
from app.repos import harness_repo
from tests.e2e.fixtures import gilmours_claim1 as c1
from tests.e2e.fixtures import gilmours_claim2 as c2
from tests.e2e.fixtures import gilmours_claim3 as c3
from tests.e2e.helpers import get_auth_headers
from tests.eval.metrics import ClaimEval, RunResult, format_report, gate

# ── Config ───────────────────────────────────────────────────────────────────
N_RUNS = int(os.environ.get("EVAL_RUNS", "10"))

# Gate floors, tuned from the first real N=10 run (2026-10-04): WBS jev-alone and
# post-residue were both 1.00 with zero variance across 630 scored decisions, and VPS
# re-identification was 1.00. Floors sit a margin below observed so the gate fails on a
# real regression, not on sampling variance. Re-tune if the golden set or model changes.
WBS_FLOOR = 0.95
VPS_FLOOR = 0.95
OVERCONFIDENCE_THRESHOLD = 0.9

_CLAIMS_DIR = Path(__file__).parent.parent.parent.parent / "claim" / "Gilmours" / "claims"


def _pdf(n: int) -> Path:
    return _CLAIMS_DIR / f"Gilmours Central_Progress Claim No. {n}.pdf"


# (name, pdf, expected_line_items). Claims 2 & 3 reuse claim 1's PROJECT/WBS_CODES.
CLAIMS = [
    ("Gilmours Claim 1", _pdf(1), c1.EXPECTED_CLAIM_LINE_ITEMS),
    ("Gilmours Claim 2", _pdf(2), c2.EXPECTED_CLAIM_2_LINE_ITEMS),
    ("Gilmours Claim 3", _pdf(3), c3.EXPECTED_CLAIM_3_LINE_ITEMS),
]

WBS_PHASE = claim_parse_definition.phases[4]
VPS_PHASE = claim_parse_definition.phases[5]


# ── Ground truth ──────────────────────────────────────────────────────────────
def _expected_codes(expected_line_items: list[dict]) -> dict[str, str]:
    """ref_code -> WBS code, for contract_work items whose contract_value equals
    exactly one subcategory's contract_sum (ground truth independent of the matcher)."""
    subs = [w for w in c1.WBS_CODES if w.get("parent_code")]
    out: dict[str, str] = {}
    for item in expected_line_items:
        if item["item_type"] != "contract_work":
            continue
        hits = [w["code"] for w in subs
                if abs(float(w["contract_sum"]) - float(item["contract_value"])) < 0.01]
        if len(hits) == 1:
            out[item["ref_code"]] = hits[0]
    return out


# ── Scoring ───────────────────────────────────────────────────────────────────
def _score_wbs(output, expected_by_index: dict[int, str]) -> tuple[float, int, list[tuple[float, bool]]]:
    """Accuracy over the FULL expected set. A dropped item (absent from output) counts
    as wrong — it does not shrink the denominator — so losing items can never inflate
    the score. Calibration pairs are only collected for items actually returned."""
    by_index = {m.item_index: m for m in output}
    pairs: list[tuple[float, bool]] = []
    correct = 0
    for idx, code in expected_by_index.items():
        m = by_index.get(idx)
        if m is None:
            continue  # dropped -> wrong (counted via the full denominator), no confidence to pair
        ok = m.wbs_code == code
        correct += int(ok)
        pairs.append((float(m.confidence), ok))
    total = len(expected_by_index)
    return (correct / total if total else 0.0), total, pairs


def _score_vps(output) -> tuple[float, int]:
    """VPS re-identification. The upload's phase 6 (create_records) creates a Variation/PS
    record for each claim item, so when the matcher re-runs against the frozen project it
    SHOULD link each item back to its existing record (matched_id not None) rather than
    duplicate it as new. This mirrors the real production case: later claims re-reference
    variations created by earlier ones. Correct = a record was re-identified."""
    if not output:
        return 1.0, 0
    reidentified = sum(1 for m in output if m.matched_id is not None)
    return reidentified / len(output), len(output)


# ── Harness driving ───────────────────────────────────────────────────────────
async def _upload_and_freeze(client: AsyncClient, project_id: str, pdf_path: Path, headers: dict) -> str:
    """Upload a claim and stream phases 0-6 to completion. Returns the harness session id
    (whose frozen parsed_claim.json the matcher re-reads on every run).

    Asserts the harness actually completed: a mid-stream harness error must fail the
    eval loudly, not leave it scoring against a stale or empty parsed_claim.json.
    """
    with open(pdf_path, "rb") as f:
        resp = await client.post(
            f"/api/projects/{project_id}/claims/upload",
            params={"mode": "deep_mode"},
            files={"file": (pdf_path.name, f, "application/pdf")},
            headers=headers,
        )
    assert resp.status_code == 201, resp.text
    session_id = resp.json()["harness_session_id"]
    event_types: list[str] = []
    async with client.stream(
        "GET", f"/api/harness/sessions/{session_id}/stream", headers=headers, timeout=600.0,
    ) as stream:
        async for line in stream.aiter_lines():
            if not line.startswith("data: "):
                continue
            payload = line[len("data: "):]
            if payload == "[DONE]":
                break
            event_types.append(json.loads(payload).get("type", ""))
    assert "harness_error" not in event_types, f"{pdf_path.name}: harness errored: {event_types}"
    assert "harness_complete" in event_types, f"{pdf_path.name}: harness did not complete: {event_types}"
    return session_id


async def _no_residue(*, phase_def, db, project_id, session_id) -> MatchOutcome:
    """Stub residue resolver: leave Jev's own decisions untouched (Jev-alone pass)."""
    return MatchOutcome(output=[], output_json="[]")


async def _run_once(db, project_id, session_id, expected_by_index, memo_cache) -> tuple[RunResult, list[tuple[float, bool]]]:
    """One matcher run over one claim. WBS is scored twice (Jev-alone, post-residue)
    from a single memoised set of Jev calls; VPS once."""
    real_call = jev_module.call_decisions

    async def memo(*, state, questions, model, url, api_key, timeout=30.0):
        """Serve each Jev decision once, so the Jev-alone and post-residue passes see
        the SAME decisions. Exceptions are cached and re-raised too, so a Jev failure
        shows up identically in both passes instead of being retried away in pass B."""
        (qid, _), = questions.items()
        if qid not in memo_cache:
            try:
                memo_cache[qid] = (True, await real_call(
                    state=state, questions=questions, model=model, url=url, api_key=api_key, timeout=timeout))
            except Exception as e:  # noqa: BLE001 - cached and re-raised immediately below
                memo_cache[qid] = (False, e)
        ok, value = memo_cache[qid]
        if not ok:
            raise value
        return value

    # Pass A: Jev-alone (residue resolver stubbed out so Jev's raw decisions stand).
    real_llm = jev_module.run_llm_matches
    jev_module.run_llm_matches = _no_residue
    try:
        wbs_alone = await JevMatcher(decide_fn=memo).match(
            phase_def=WBS_PHASE, db=db, project_id=project_id, session_id=session_id)
    finally:
        jev_module.run_llm_matches = real_llm

    # Pass B: post-residue (real LLM resolver; Jev decisions served from the cache).
    wbs_post = await JevMatcher(decide_fn=memo).match(
        phase_def=WBS_PHASE, db=db, project_id=project_id, session_id=session_id)

    # VPS: single pass, real Jev.
    vps = await JevMatcher().match(
        phase_def=VPS_PHASE, db=db, project_id=project_id, session_id=session_id)

    alone_acc, wbs_scored, cal_pairs = _score_wbs(wbs_alone.output, expected_by_index)
    post_acc, _, _ = _score_wbs(wbs_post.output, expected_by_index)
    vps_reident, vps_scored = _score_vps(vps.output)

    result = RunResult(
        wbs_jev_alone=alone_acc,
        wbs_post_residue=post_acc,
        vps_reident=vps_reident,
        wbs_scored=wbs_scored,
        vps_scored=vps_scored,
        wbs_items=len(wbs_post.output),
        vps_items=len(vps.output),
        ooc_wbs=wbs_post.out_of_criteria,
        ooc_vps=vps.out_of_criteria,
        residue=wbs_post.residue,
        fell_back=wbs_post.fell_back + vps.fell_back,
        input_tokens=wbs_post.input_tokens + vps.input_tokens,
        output_tokens=wbs_post.output_tokens + vps.output_tokens,
        cost_usd=(wbs_post.cost_usd or 0.0) + (vps.cost_usd or 0.0),
    )
    return result, cal_pairs


@pytest.mark.eval
@pytest.mark.skipif(not settings.open_router_api_key, reason="OPEN_ROUTER_API_KEY not set")
@pytest.mark.skipif(not all(pdf.exists() for _, pdf, _ in CLAIMS), reason="Gilmours claim PDFs not available")
@pytest.mark.asyncio
async def test_jev_matcher_eval(client: AsyncClient, db_session):
    headers = await get_auth_headers(client)
    claim_evals: list[ClaimEval] = []

    for name, pdf_path, expected_line_items in CLAIMS:
        project = (await client.post("/api/projects", json=c1.PROJECT, headers=headers)).json()
        project_id = project["id"]
        session_id = await _upload_and_freeze(client, project_id, pdf_path, headers)

        parsed = json.loads(await harness_repo.read_workspace_file(db_session, session_id, "parsed_claim.json"))
        idx_by_ref = {i["ref_code"]: i["item_index"]
                      for i in parsed["line_items"] if i["item_type"] == "contract_work"}
        exp_codes = _expected_codes(expected_line_items)
        assert exp_codes, f"{name}: no unambiguous ground-truth WBS items in fixtures"
        # Every expected ref MUST be present in the parsed claim; a shrunk expected set
        # would silently hide a truncated upstream parse, so fail loudly instead.
        missing = sorted(ref for ref in exp_codes if ref not in idx_by_ref)
        assert not missing, f"{name}: expected refs missing from parsed_claim (truncated parse?): {missing}"
        expected_by_index = {idx_by_ref[ref]: code for ref, code in exp_codes.items()}

        runs: list[RunResult] = []
        cal_pairs: list[tuple[float, bool]] = []
        for _ in range(N_RUNS):
            result, pairs = await _run_once(db_session, project_id, session_id, expected_by_index, memo_cache={})
            runs.append(result)
            cal_pairs.extend(pairs)
        # A VPS phase with nothing to score would pass the VPS floor vacuously.
        assert runs[0].vps_scored > 0, f"{name}: no VPS items to score"
        claim_evals.append(ClaimEval(name=name, runs=runs, calibration_pairs=cal_pairs))

    report = format_report(
        claim_evals,
        model=settings.jev_model,
        n_runs=N_RUNS,
        wbs_floor=WBS_FLOOR,
        vps_floor=VPS_FLOOR,
        overconfidence_threshold=OVERCONFIDENCE_THRESHOLD,
        date=datetime.date.today().isoformat(),
    )
    print("\n" + report)

    passed, detail = gate(claim_evals, wbs_floor=WBS_FLOOR, vps_floor=VPS_FLOOR)
    assert detail["n_runs"] > 0, "eval ran zero matcher runs"
    assert detail["wbs_pass"], f"WBS mean post-residue {detail['wbs_mean']:.3f} < floor {WBS_FLOOR}"
    assert detail["vps_pass"], f"VPS re-identification mean {detail['vps_mean']:.3f} < floor {VPS_FLOOR}"
    assert detail["grounding_pass"], f"grounding violated: {detail['ooc_total']} out-of-criteria selection(s)"
    assert detail["reliability_pass"], f"Jev fell back {detail['fell_back_total']} time(s) — matcher unreliable"
    assert passed
