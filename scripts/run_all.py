"""T7.2.2: run the whole pipeline in order.

  python scripts/run_all.py --quick   (~20-30 min on 14 cores) reproduces the committed decisions and checks the
                                      headline numbers within tolerance. Deterministic outputs are rewritten with
                                      identical values. The quick run refits arima52/prophet only for the SKUs that
                                      use them, so it restores results/forecast/model_metrics.csv,
                                      headline_forecast.csv and configs/forecast_selection.yaml afterwards (their
                                      other rows would be incomplete). The demand scale k is frozen (ADR-011).
  python scripts/run_all.py           full rebuild (~4-5 h; includes seasonal ARIMA for all SKUs, the exact-model
                                      validation run, N = 200, ablation and sensitivity)

Prerequisites: `pip install -r requirements.txt -r requirements-optional.txt`; Favorita CSVs in data/raw/favorita
(`python scripts/download_data.py`, needs your own Kaggle token; Kaggle terms forbid redistributing the data).

Quick mode differs from full mode only where it saves time without changing a decision:
- slow forecast models (arima52, prophet_hol) are refit only for the SKUs that the committed
  configs/forecast_selection.yaml assigns to them; selection is then re-run and must give the same choices
  (the left-out (SKU, model) pairs lost on validation, so they cannot change the per-SKU minimum);
- planner tuning skips the exact (arc) model, and the winner must equal configs/planner.yaml;
- Monte Carlo uses N = 30 paths; sensitivity, ablation and app data are skipped.
Checks (tolerances, docs/results/reproducibility_log.md): replay values within 1e-6 relative; each Monte Carlo
estimate within its committed 95% CI widened by 3 points (N = 30 vs 200 sampling error).
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable
QUICK_HEADLINE = ROOT / "results" / "logs" / "headline_quick.json"
QUICK_RESTORE = (ROOT / "results" / "forecast" / "model_metrics.csv",
                 ROOT / "results" / "forecast" / "headline_forecast.csv",
                 ROOT / "configs" / "forecast_selection.yaml")


def sh(*args: str) -> None:
    t0 = time.perf_counter()
    print(f"\n>>> {' '.join(args)}", flush=True)
    subprocess.run([PY, *args], cwd=ROOT, check=True)
    print(f"    ({time.perf_counter() - t0:.0f} s)", flush=True)


def check_quick(committed: dict, quick: dict) -> list[str]:
    errs = []
    for k, v in committed["replay_layer_a"].items():
        if isinstance(v, float):
            q = quick["replay_layer_a"][k]
            if abs(q - v) > 1e-6 * max(1.0, abs(v)):
                errs.append(f"replay {k}: committed {v} vs quick {q}")
    for k, v in committed["monte_carlo"].items():
        q = quick["monte_carlo"][k]["estimate"]
        if not (v["ci_lo"] - 3 <= q <= v["ci_hi"] + 3):
            errs.append(f"monte carlo {k}: quick {q:.2f} outside committed CI [{v['ci_lo']:.2f}, {v['ci_hi']:.2f}] +/- 3")
    return errs


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    a = ap.parse_args()
    t0 = time.perf_counter()
    sel_before = yaml.safe_load((ROOT / "configs" / "forecast_selection.yaml").read_text())["per_sku"]
    planner_before = yaml.safe_load((ROOT / "configs" / "planner.yaml").read_text())
    committed = json.loads((ROOT / "results" / "headline_numbers.json").read_text())
    keep = {p: p.read_bytes() for p in QUICK_RESTORE if p.exists()} if a.quick else {}
    try:
        run(a, sel_before, planner_before, committed)
    finally:
        for p, b in keep.items():
            p.write_bytes(b)
    print(f"\nrun_all {'--quick ' if a.quick else ''}finished in {(time.perf_counter() - t0) / 60:.1f} min")


def run(a: argparse.Namespace, sel_before: dict, planner_before: dict, committed: dict) -> None:

    if not (ROOT / "data" / "processed" / "demand_weekly.parquet").exists():
        sh("-m", "shelflife.data.favorita")
    sh("scripts/calibrate.py")
    sh("scripts/run_benchmarks.py")
    sh("scripts/run_stat_models.py", "--models", "arima", "ets")
    if a.quick:
        for model in ("arima52", "prophet_hol"):
            skus = sorted(s for s, m in sel_before.items() if m == model)
            if skus:
                sh("scripts/run_stat_models.py", "--models", model, "--skus", *skus, "--chunks", "14")
    else:
        sh("scripts/run_stat_models.py", "--models", "prophet", "prophet_hol")
        sh("scripts/run_stat_models.py", "--models", "arima52", "--chunks", "4")
        sh("scripts/plot_residual_acf.py")
    sh("scripts/select_forecasts.py")
    sel_after = yaml.safe_load((ROOT / "configs" / "forecast_selection.yaml").read_text())["per_sku"]
    assert sel_after == sel_before, f"forecast selection changed: {sel_before} -> {sel_after}"
    sh("scripts/build_uncertainty.py")
    sh("scripts/run_baseline_replay.py")
    sh("scripts/tune_planner_validation.py",
       *(["--skip-arc", "--table", str(ROOT / "results" / "logs" / "planner_tuning_quick.csv")] if a.quick else []))
    planner_after = yaml.safe_load((ROOT / "configs" / "planner.yaml").read_text())
    assert planner_after["variant"] == planner_before["variant"], (planner_before["variant"], planner_after["variant"])
    baseline_before = yaml.safe_load((ROOT / "configs" / "baseline.yaml").read_text())
    sh("scripts/tune_baseline_validation.py")
    baseline_after = yaml.safe_load((ROOT / "configs" / "baseline.yaml").read_text())
    assert baseline_after == baseline_before, (baseline_before, baseline_after)
    sh("scripts/run_rolling_replay.py")
    if a.quick:
        sh("scripts/run_experiment.py", "--config", "configs/experiment_main.yaml", "--n-paths", "30")
        newest = max((ROOT / "results" / "experiments").glob("main_*/kpis.parquet"), key=lambda p: p.stat().st_mtime)
        sh("scripts/analyze_experiment.py", "--run", str(newest.parent), "--out", str(QUICK_HEADLINE))
        errs = check_quick(committed, json.loads(QUICK_HEADLINE.read_text()))
        print("\nQUICK CHECK:", "PASS" if not errs else "FAIL")
        for e in errs:
            print("  -", e)
        if errs:
            sys.exit(1)
    else:
        sh("scripts/run_experiment.py", "--config", "configs/experiment_main.yaml")
        sh("scripts/analyze_experiment.py")
        sh("scripts/run_experiment.py", "--config", "configs/experiment_ablation.yaml")
        sh("scripts/analyze_ablation.py")
        sh("scripts/run_sensitivity.py")
        sh("scripts/run_sensitivity.py", "--append-arms", "B1_TUNED")
        sh("scripts/analyze_sensitivity.py")
        sh("scripts/build_app_data.py")


if __name__ == "__main__":
    main()
