"""ADR-007: choose the optimiser's changeover treatment on the VALIDATION year (2015-04-06 .. 2016-03-28).

Why: the first test-year replay (ADR-003 default, "approx" with mean-incoming per-run changeover) ran short-life
SKUs too rarely. Any fix must be chosen WITHOUT the test year, so every variant below is replayed on the
validation year only, and the test year is then run exactly once with the winner (scripts/run_rolling_replay.py).

Selection rule (fixed before any run, 2026-11-18): lowest simulator-evaluated cost with the optimiser's own weights
(configs/costs.yaml, kpis.evaluated_cost). Ties within 0.5% -> fewer expired cases. The rule does NOT look at the
baseline's numbers; B1 is replayed only for reference.

Variants
- mean      : ADR-003 default, per-run estimate = mean incoming changeover over all other SKUs
- min       : optimistic lower bound, = cheapest incoming changeover (capacity repaired after sequencing)
- iterK     : fixed point on realised sequences: start at `mean`, replay, set each SKU's estimate to its
              realised mean incoming changeover, repeat (K = 1..3)
- arc       : exact sequence-dependent changeovers inside the MIP (slow; 60 s per week limit)

Caveat: the validation-year forecasts and error sigma are in-sample for this year (selection and sigma were fitted
on it), so absolute validation KPIs are optimistic; only the RANKING of variants is used.

Outputs: results/planner_tuning_validation.csv, configs/planner.yaml
Run: python scripts/tune_planner_validation.py [--skip-arc]
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from run_rolling_replay import make_policy, setup, summarise  # noqa: E402
from shelflife.opt.model import approx_changeover_per_run, load_costs  # noqa: E402
from shelflife.opt.rolling import run_arm  # noqa: E402
from shelflife.sim.kpis import evaluated_cost  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-arc", action="store_true")
    ap.add_argument("--iterations", type=int, default=3)
    ap.add_argument("--table", default=str(ROOT / "results" / "planner_tuning_validation.csv"))
    a = ap.parse_args()
    cfg, plant, k, win, d, hist, weeks, start_inv, start_last, b1 = setup("validation")
    assert weeks[0] == win.val_start and weeks[-1] == win.val_end and d.shape[1] == 52
    costs = load_costs()
    rows, ests = [], {}

    def run(name, mode="approx", est=None):
        t0 = time.perf_counter()
        if name == "baseline_B1":
            r, plans = run_arm(plant, b1, d, hist, start_inv, start_last)
            log = None
        else:
            pol = make_policy(plant, cfg, b1, k, weeks, "validation", mode=mode, changeover_est=est)
            r, plans = run_arm(plant, pol, d, hist, start_inv, start_last)
            log = pd.DataFrame(pol.log)
        row, plan, v = summarise(name, r, plans, plant, cfg, start_last)
        row["evaluated_cost"] = evaluated_cost(r, costs)
        row["fallback_weeks"] = 0 if log is None else int(log.fallback_used.sum())
        row["runtime_s"] = round(time.perf_counter() - t0, 1)
        if v:
            raise SystemExit(f"ABORT: {name} failed the independent checker: {v[:5]}")
        rows.append(row)
        print({kk: (round(vv, 3) if isinstance(vv, float) else vv) for kk, vv in row.items()}, flush=True)
        realised = plan.groupby("sku_id").changeover_hours_before.mean()
        return realised

    run("baseline_B1")
    mean_est = dict(zip(plant.sku_ids, approx_changeover_per_run(plant), strict=True))
    C = plant.changeover_hours.copy()
    np.fill_diagonal(C, np.inf)
    ests["mean"] = mean_est
    ests["min"] = dict(zip(plant.sku_ids, C.min(axis=0), strict=True))
    realised = run("mean", est=mean_est)
    run("min", est=ests["min"])
    est = dict(mean_est)
    for i in range(1, a.iterations + 1):
        est = {s: float(realised.get(s, est[s])) for s in plant.sku_ids}
        ests[f"iter{i}"] = est
        realised = run(f"iter{i}", est=est)
    if not a.skip_arc:
        run("arc", mode="arc")

    t = pd.DataFrame(rows)
    t["evaluated_cost_index_vs_B1"] = 100 * t.evaluated_cost / t.loc[t.arm == "baseline_B1", "evaluated_cost"].iloc[0]
    t.round(4).to_csv(a.table, index=False)
    cand = t[t.arm != "baseline_B1"].sort_values("evaluated_cost")
    best_cost = cand.evaluated_cost.iloc[0]
    near = cand[cand.evaluated_cost <= best_cost * 1.005].sort_values("expired_cases")
    win_name = near.arm.iloc[0]
    settings = {
        "note": "Chosen on the VALIDATION year by scripts/tune_planner_validation.py (ADR-007); test year not read.",
        "variant": win_name,
        "mode": "arc" if win_name == "arc" else "approx",
        "changeover_est": None if win_name == "arc" else {s: round(float(v), 4) for s, v in ests[win_name].items()},
    }
    (ROOT / "configs" / "planner.yaml").write_text(yaml.safe_dump(settings, sort_keys=False), encoding="utf-8")
    print(t[["arm", "evaluated_cost_index_vs_B1", "expired_cases", "lost_cases", "fill_rate", "changeover_hours",
             "fallback_weeks", "runtime_s"]].round(3).to_string(index=False))
    print("chosen:", win_name)


if __name__ == "__main__":
    main()
