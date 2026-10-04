"""Unit tests for the eval's scoring/aggregation maths (tests/eval/metrics.py).

Deterministic and I/O-free, so the eval's own arithmetic is trustworthy before it
is ever pointed at the real API.
"""
import math

from tests.eval.metrics import (
    ClaimEval,
    RunResult,
    calibration,
    format_report,
    gate,
    spread,
)


def _run(wbs_alone=0.9, wbs_post=1.0, vps=1.0, **kw):
    base = dict(
        wbs_jev_alone=wbs_alone, wbs_post_residue=wbs_post, vps_reident=vps,
        wbs_scored=20, vps_scored=3, wbs_items=29, vps_items=3,
        ooc_wbs=0, ooc_vps=0, residue=2, fell_back=0,
        input_tokens=1000, output_tokens=50, cost_usd=0.01,
    )
    base.update(kw)
    return RunResult(**base)


def test_spread_reports_min_max_mean_std():
    s = spread([0.8, 1.0, 0.9])
    assert s.min == 0.8 and s.max == 1.0
    assert math.isclose(s.mean, 0.9)
    assert s.std > 0


def test_spread_empty_is_zeroed():
    s = spread([])
    assert (s.mean, s.min, s.max, s.std) == (0.0, 0.0, 0.0, 0.0)


def test_spread_single_value_has_zero_std():
    s = spread([0.75])
    assert s.mean == 0.75 and s.std == 0.0


def test_calibration_separates_correct_from_incorrect():
    pairs = [(0.95, True), (0.9, True), (0.95, False), (0.3, False)]
    cal = calibration(pairs, overconfidence_threshold=0.9)
    assert math.isclose(cal.mean_conf_correct, 0.925)
    assert math.isclose(cal.mean_conf_incorrect, 0.625)
    # Only the wrong-but-confident (0.95, False) counts as overconfident.
    assert cal.overconfident_errors == 1
    assert cal.n_correct == 2 and cal.n_incorrect == 2


def test_calibration_handles_all_correct():
    cal = calibration([(0.9, True), (0.8, True)])
    assert cal.mean_conf_incorrect == 0.0 and cal.n_incorrect == 0
    assert cal.overconfident_errors == 0


def test_gate_fails_when_either_phase_below_floor():
    weak_wbs = ClaimEval("c", [_run(wbs_post=0.80)], [])
    passed, d = gate([weak_wbs], wbs_floor=0.85, vps_floor=0.95)
    assert not passed and not d["wbs_pass"] and d["vps_pass"]

    weak_vps = ClaimEval("c", [_run(wbs_post=1.0, vps=0.90)], [])
    passed, d = gate([weak_vps], wbs_floor=0.85, vps_floor=0.95)
    assert not passed and d["wbs_pass"] and not d["vps_pass"]


def test_gate_passes_when_both_clear_floor():
    ce = ClaimEval("c", [_run(wbs_post=0.95, vps=1.0), _run(wbs_post=0.90, vps=1.0)], [])
    passed, d = gate([ce], wbs_floor=0.85, vps_floor=0.95)
    assert passed and d["wbs_pass"] and d["vps_pass"]
    assert math.isclose(d["wbs_mean"], 0.925)


def test_gate_pools_means_across_runs_and_claims():
    # One weak run does not sink the gate while the pooled mean holds above the floor.
    ce = ClaimEval("c", [_run(wbs_post=1.0), _run(wbs_post=1.0), _run(wbs_post=0.6)], [])
    passed, d = gate([ce], wbs_floor=0.85, vps_floor=0.95)
    assert math.isclose(d["wbs_mean"], (1.0 + 1.0 + 0.6) / 3)
    assert passed and d["wbs_pass"]  # mean 0.867 >= 0.85

    # But a sustained drop (every run weak) fails, even though no single run is catastrophic.
    ce_bad = ClaimEval("c", [_run(wbs_post=0.80), _run(wbs_post=0.82), _run(wbs_post=0.78)], [])
    passed_bad, d_bad = gate([ce_bad], wbs_floor=0.85, vps_floor=0.95)
    assert not passed_bad and not d_bad["wbs_pass"]


def test_gate_fails_on_grounding_violation_even_when_accuracy_is_perfect():
    # Perfect accuracy must NOT pass if the matcher chose an option that did not exist.
    ce = ClaimEval("c", [_run(wbs_post=1.0, vps=1.0, ooc_wbs=1)], [])
    passed, d = gate([ce], wbs_floor=0.85, vps_floor=0.95)
    assert not passed and d["wbs_pass"] and d["vps_pass"]
    assert not d["grounding_pass"] and d["ooc_total"] == 1


def test_gate_fails_on_systemic_fell_back_even_when_accuracy_is_perfect():
    # A Jev outage (most items fell back to a safe default) must not pass silently.
    # _run has 29 WBS + 3 VPS = 32 decisions; 10 fell_back = 31% >> 5%.
    ce = ClaimEval("c", [_run(wbs_post=1.0, vps=1.0, fell_back=10)], [])
    passed, d = gate([ce], wbs_floor=0.85, vps_floor=0.95)
    assert not passed and not d["reliability_pass"] and d["fell_back_total"] == 10


def test_gate_tolerates_a_transient_fell_back_blip():
    # One transient 5xx among hundreds of decisions must NOT fail the gate.
    runs = [_run(wbs_post=1.0, vps=1.0) for _ in range(10)]
    runs[3].fell_back = 1  # 1 of 320 decisions = 0.3%
    passed, d = gate([ClaimEval("c", runs, [])], wbs_floor=0.85, vps_floor=0.95)
    assert passed and d["reliability_pass"] and d["fell_back_rate"] < 0.05


def test_gate_fails_closed_on_no_runs():
    passed, d = gate([ClaimEval("c", [], [])], wbs_floor=0.85, vps_floor=0.95)
    assert not passed and d["n_runs"] == 0


def test_format_report_renders_headings_and_gate():
    clean = ClaimEval("Claim 1", [_run(wbs_post=1.0, vps=1.0)], [(0.95, True)])
    report = format_report([clean], model="jev-1.13", n_runs=1, wbs_floor=0.85, vps_floor=0.95)
    for heading in ("MATCH ACCURACY", "GROUNDING", "CALIBRATION", "ROUTING & COST", "PER-CLAIM", "GATE"):
        assert heading in report
    assert "PASS" in report
    assert "invariant held" in report  # ooc totals are zero


def test_format_report_flags_grounding_violations():
    bad = ClaimEval("Claim 1", [_run(ooc_wbs=2)], [])
    report = format_report([bad], model="m", n_runs=1, wbs_floor=0.85, vps_floor=0.95)
    assert "invariant held" not in report
