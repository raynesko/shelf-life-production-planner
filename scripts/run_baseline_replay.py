"""T4.1.2: baseline B1 replay on real demand. Reports the 52-week TEST year.

B1 runs continuously from the first panel week (4 warm-up weeks of history) so that inventory, line state
and forecasts at the start of the test year are realistic; only test-year weeks are reported.
Demand = Favorita units x calibration scale factor (configs/calibration.yaml).

Outputs: results/baseline_replay.csv (one row of KPIs), results/baseline_replay_weeks.parquet (detail),
         results/baseline_plan_test.csv (plan table), checked by the independent plan checker.
Run: python scripts/run_baseline_replay.py
"""
from __future__ import annotations

import time
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from shelflife.checks.plan_checker import check
from shelflife.forecast.backtest import make_windows
from shelflife.plant.changeover import build_matrix
from shelflife.plant.config import load
from shelflife.sim import kpis
from shelflife.sim.baseline import BaselineB1
from shelflife.sim.engine import SimPlant, SimResult, plan_to_frame, simulate_policy

ROOT = Path(__file__).resolve().parents[1]
WARMUP = 4


def window_result(r: SimResult, first_week: int, last_sku_before: str | None) -> SimResult:
    sw = r.sku_week[r.sku_week.week >= first_week].copy()
    wk = r.week[r.week.week >= first_week].copy()
    sh = r.shipments[r.shipments.week >= first_week].copy()
    for df in (sw, wk, sh):
        df["week"] -= first_week
    return SimResult(sw, wk, float("nan"), r.ending_cohorts, sh)


def main() -> None:
    t0 = time.perf_counter()
    cfg = load()
    plant = SimPlant.from_config(cfg, build_matrix(cfg))
    k = yaml.safe_load((ROOT / "configs" / "calibration.yaml").read_text())["scale_factor"]
    panel = pd.read_parquet(ROOT / "data" / "processed" / "demand_weekly.parquet")
    win = make_windows(panel.week_start)
    wide = panel.pivot(index="sku_id", columns="week_start", values="units").loc[plant.sku_ids]
    d = wide.to_numpy(float) * k
    weeks = wide.columns
    b1 = BaselineB1.from_config(cfg, plant)
    r, plans = simulate_policy(plant, b1, d[:, WARMUP:], d[:, :WARMUP], initial_last_sku=0)
    first = int(np.where(weeks[WARMUP:] == win.test_start)[0][0])
    test = window_result(r, first, None)
    assert len(test.week) == 52, len(test.week)

    last_before = r.week.last_sku.iloc[first - 1]
    plan = plan_to_frame(plans[first:], plant, plant.sku_ids.index(last_before))
    violations = check(plan, cfg, initial_last_sku=last_before, shipments=test.shipments)
    s = kpis.summarise(test)
    row = {"arm": "baseline_B1", "window": "test", "from": str(win.test_start.date()), "to": str(win.test_end.date()),
           "scale_factor": k, **{key: round(float(v), 4) for key, v in s.items()},
           "checker_violations": len(violations), "runtime_s": round(time.perf_counter() - t0, 2)}
    pd.DataFrame([row]).to_csv(ROOT / "results" / "baseline_replay.csv", index=False)
    test.sku_week.assign(week_start=lambda x: win.test_start + pd.to_timedelta(7 * x.week, unit="D")) \
        .to_parquet(ROOT / "results" / "baseline_replay_weeks.parquet", index=False)
    plan.to_csv(ROOT / "results" / "baseline_plan_test.csv", index=False)
    for key, v in row.items():
        print(f"{key:24} {v}")
    if violations:
        print("CHECKER FAIL:", *violations[:10], sep="\n  ")


if __name__ == "__main__":
    main()
