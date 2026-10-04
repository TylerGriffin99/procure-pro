"""Pure scoring, aggregation and reporting for the Jev matcher eval.

No I/O, no network, no DB — just arithmetic over the per-run results the eval
collects. Kept separate from the eval orchestration so the eval's own maths is
unit-testable (see tests/unit/test_eval_metrics.py) without API calls.
"""
from __future__ import annotations

import statistics
from dataclasses import dataclass


@dataclass
class RunResult:
    """Metrics from ONE matcher run over ONE claim (harness phases 4 & 5)."""

    wbs_jev_alone: float      # WBS accuracy (correct / scored) BEFORE LLM residue
    wbs_post_residue: float   # WBS accuracy AFTER the LLM residue resolver
    vps_reident: float        # VPS re-identification: fraction of items linked to the
                              # existing record created upstream (not duplicated as new)
    wbs_scored: int           # WBS items that have ground truth (unambiguous exact-sum)
    vps_scored: int           # VPS items scored
    wbs_items: int            # total WBS decisions this run (grounding denominator)
    vps_items: int            # total VPS decisions this run
    ooc_wbs: int              # WBS out-of-criteria (grounding) violations
    ooc_vps: int              # VPS out-of-criteria (grounding) violations
    residue: int              # WBS items routed to the LLM residue resolver
    fell_back: int            # items that fell back after a Jev error
    input_tokens: int
    output_tokens: int
    cost_usd: float


@dataclass
class Spread:
    mean: float
    min: float
    max: float
    std: float


def spread(values: list[float]) -> Spread:
    """min / max / mean / population-stddev of a list of per-run accuracies."""
    if not values:
        return Spread(0.0, 0.0, 0.0, 0.0)
    return Spread(
        mean=statistics.fmean(values),
        min=min(values),
        max=max(values),
        std=statistics.pstdev(values) if len(values) > 1 else 0.0,
    )


@dataclass
class Calibration:
    mean_conf_correct: float
    mean_conf_incorrect: float
    overconfident_errors: int   # wrong AND confidence >= threshold
    n_correct: int
    n_incorrect: int


def calibration(pairs: list[tuple[float, bool]], *, overconfidence_threshold: float = 0.9) -> Calibration:
    """Confidence-vs-correctness: does the matcher reserve high confidence for right answers?

    ``pairs`` is (confidence, was_correct) for every scored decision.
    """
    correct = [c for c, ok in pairs if ok]
    incorrect = [c for c, ok in pairs if not ok]
    return Calibration(
        mean_conf_correct=statistics.fmean(correct) if correct else 0.0,
        mean_conf_incorrect=statistics.fmean(incorrect) if incorrect else 0.0,
        overconfident_errors=sum(1 for c, ok in pairs if not ok and c >= overconfidence_threshold),
        n_correct=len(correct),
        n_incorrect=len(incorrect),
    )


@dataclass
class ClaimEval:
    name: str
    runs: list[RunResult]
    # (confidence, correct) for Jev-alone WBS decisions, pooled across this claim's runs.
    calibration_pairs: list[tuple[float, bool]]


def gate(
    claims: list[ClaimEval], *, wbs_floor: float, vps_floor: float, max_fell_back_rate: float = 0.05
) -> tuple[bool, dict]:
    """Pass/fail gate. FOUR independent conditions must all hold:

      * WBS mean post-residue accuracy >= wbs_floor
      * VPS mean accuracy            >= vps_floor
      * grounding: ZERO out-of-criteria selections (structural hallucinations)
      * reliability: fell_back RATE <= max_fell_back_rate (a Jev OUTAGE must not pass)

    The last two matter because a Jev outage or a hallucination both demote to a
    "safe" value (new record / is_new) that the accuracy floors alone would score
    as fine — so the numbers can look healthy while Jev is broken. Reliability is a
    RATE, not a count: the decisions API throws transient 5xx, so one blip among
    hundreds of decisions must not fail the gate, but a systemic outage (most/all
    items falling back) must. Means are pooled over every run of every claim; a
    single bad sampling day does not flip the gate, a sustained regression does.
    No runs at all fails closed.
    """
    runs = [r for c in claims for r in c.runs]
    wbs_mean = statistics.fmean([r.wbs_post_residue for r in runs]) if runs else 0.0
    vps_mean = statistics.fmean([r.vps_reident for r in runs]) if runs else 0.0
    ooc_total = sum(r.ooc_wbs + r.ooc_vps for r in runs)
    fell_back_total = sum(r.fell_back for r in runs)
    decisions = sum(r.wbs_items + r.vps_items for r in runs)
    fell_back_rate = (fell_back_total / decisions) if decisions else 1.0
    detail = {
        "n_runs": len(runs),
        "wbs_mean": wbs_mean, "wbs_floor": wbs_floor, "wbs_pass": bool(runs) and wbs_mean >= wbs_floor,
        "vps_mean": vps_mean, "vps_floor": vps_floor, "vps_pass": bool(runs) and vps_mean >= vps_floor,
        "ooc_total": ooc_total, "grounding_pass": ooc_total == 0,
        "fell_back_total": fell_back_total, "fell_back_rate": fell_back_rate,
        "reliability_pass": bool(runs) and fell_back_rate <= max_fell_back_rate,
    }
    passed = bool(runs) and all(
        detail[k] for k in ("wbs_pass", "vps_pass", "grounding_pass", "reliability_pass"))
    return passed, detail


def _fmt(s: Spread) -> str:
    return f"{s.mean:5.2f}  {s.min:5.2f}   {s.max:5.2f}   {s.std:5.3f}"


def _pct(n: int, d: int) -> str:
    return f"{n} / {d}  ({(100.0 * n / d) if d else 0.0:.1f}%)"


def format_report(
    claims: list[ClaimEval],
    *,
    model: str,
    n_runs: int,
    wbs_floor: float,
    vps_floor: float,
    overconfidence_threshold: float = 0.9,
    date: str = "",
) -> str:
    """Render the console report (see docstring of the eval for the layout)."""
    runs = [r for c in claims for r in c.runs]
    pairs = [p for c in claims for p in c.calibration_pairs]
    bar = "=" * 68
    rule = "-" * 68
    names = ", ".join(c.name for c in claims)

    wbs_alone = spread([r.wbs_jev_alone for r in runs])
    wbs_post = spread([r.wbs_post_residue for r in runs])
    vps = spread([r.vps_reident for r in runs])

    ooc_wbs = sum(r.ooc_wbs for r in runs)
    ooc_vps = sum(r.ooc_vps for r in runs)
    wbs_items = sum(r.wbs_items for r in runs)
    vps_items = sum(r.vps_items for r in runs)

    cal = calibration(pairs, overconfidence_threshold=overconfidence_threshold)

    n = max(len(runs), 1)
    mean_residue = sum(r.residue for r in runs) / n
    mean_fell = sum(r.fell_back for r in runs) / n
    mean_in = sum(r.input_tokens for r in runs) / n
    mean_out = sum(r.output_tokens for r in runs) / n
    mean_cost = sum(r.cost_usd for r in runs) / n

    passed, g = gate(claims, wbs_floor=wbs_floor, vps_floor=vps_floor)

    lines = [
        bar,
        f" JEV MATCHER EVAL · {date} · model={model}",
        f" runs={n_runs} · claims=[{names}] · phases 4-5 (frozen parsed_claim)",
        bar,
        "",
        "MATCH ACCURACY  (correct / scored, across all runs)",
        "                     mean    min     max      sd",
        f" WBS  jev-alone     {_fmt(wbs_alone)}",
        f" WBS  post-residue  {_fmt(wbs_post)}",
        f" VPS  re-identify   {_fmt(vps)}",
        "",
        "GROUNDING  (structural hallucinations = out-of-criteria selections)",
        f" WBS   {_pct(ooc_wbs, wbs_items)}",
        f" VPS   {_pct(ooc_vps, vps_items)}"
        + ("                 invariant held" if (ooc_wbs + ooc_vps) == 0 else ""),
        "",
        "CALIBRATION  (Jev confidence vs correctness)",
        f" mean conf · correct     {cal.mean_conf_correct:.2f}   (n={cal.n_correct})",
        f" mean conf · incorrect   {cal.mean_conf_incorrect:.2f}   (n={cal.n_incorrect})",
        f" overconfident errors (wrong & conf>={overconfidence_threshold:g})    {cal.overconfident_errors}",
        "",
        "ROUTING & COST  (mean per run)",
        f" residue {mean_residue:.1f}   fell_back {mean_fell:.1f}   "
        f"in/out tok {mean_in:.0f}/{mean_out:.0f}   ${mean_cost:.3f}",
        "",
        "PER-CLAIM  (WBS post-residue accuracy: mean [min-max], n scored)",
    ]
    for c in claims:
        s = spread([r.wbs_post_residue for r in c.runs])
        scored = c.runs[0].wbs_scored if c.runs else 0
        lines.append(f" {c.name:<22} {s.mean:5.2f}  [{s.min:4.2f}-{s.max:4.2f}]   n={scored}")

    grounding = "OK" if g["grounding_pass"] else f"FAIL ({g['ooc_total']} out-of-criteria)"
    reliability = (f"OK ({g['fell_back_rate']:.1%} fell_back)" if g["reliability_pass"]
                   else f"FAIL ({g['fell_back_rate']:.1%} fell_back)")
    lines += [
        rule,
        f" GATE  accuracy : WBS {g['wbs_mean']:.2f} {'>=' if g['wbs_pass'] else '< '} {wbs_floor:.2f}"
        f"  ·  VPS {g['vps_mean']:.2f} {'>=' if g['vps_pass'] else '< '} {vps_floor:.2f}",
        f"       integrity: grounding {grounding}  ·  reliability {reliability}",
        f"       => {'PASS' if passed else 'FAIL'}",
        bar,
    ]
    return "\n".join(lines)
