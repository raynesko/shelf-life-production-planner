"""T4.3.2: 52-week historical replay (Layer A), baseline B1 vs optimised rolling planner.

Both arms start the test year from the SAME state: B1 run continuously from 2013 to the week before
2016-04-04 (inventory by age + last SKU on the line). Real demand (x calibration scale), real out-of-sample
forecasts of the selected models (results/forecast/forecasts_test.parquet), validation-year sigma.

Outputs: results/optimized_replay.csv, results/replay_comparison.csv, results/logs/solves.csv,
         results/replay_sku_weeks.parquet (per SKU x week, both arms),
         results/optimized_plan_test.csv
Planner settings (mode, per-run changeover estimate) come from configs/planner.yaml, chosen on the VALIDATION year
by scripts/tune_planner_validation.py (ADR-007); the test year is run once with them.
Run: python scripts/run_rolling_replay.py [--time-limit 60] [--alpha 0.95] [--mode approx|arc]
"""
from __future__ import annotations

import argparse
import time
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from shelflife.checks.plan_checker import check
from shelflife.forecast.backtest import make_windows
from shelflife.opt.model import load_costs
from shelflife.opt.rolling import OptimisedPolicy, forecast_cube, run_arm
from shelflife.plant.changeover import build_matrix
from shelflife.plant.config import load
from shelflife.sim import kpis
from shelflife.sim.baseline import BaselineB1
from shelflife.sim.engine import SimPlant, plan_to_frame, simulate_policy
from shelflife.sim.kpis import evaluated_cost

ROOT = Path(__file__).resolve().parents[1]
WARMUP = 4


def setup(window: str = "test"):
    """Common state for a 52-week replay of `window` ("test" or "validation"): B1 runs continuously from 2013 to the
    week before the window, and both arms start from that state."""
    cfg = load()
    plant = SimPlant.from_config(cfg, build_matrix(cfg))
    k = yaml.safe_load((ROOT / "configs" / "calibration.yaml").read_text())["scale_factor"]
    panel = pd.read_parquet(ROOT / "data" / "processed" / "demand_weekly.parquet")
    win = make_windows(panel.week_start)
    wide = panel.pivot(index="sku_id", columns="week_start", values="units").loc[plant.sku_ids]
    d = wide.to_numpy(float) * k
    weeks = wide.columns
    lo, hi = win.bounds(window)
    first = int(np.where(weeks == lo)[0][0])
    last = int(np.where(weeks == hi)[0][0]) + 1
    b1 = BaselineB1.from_config(cfg, plant)
    pre, _ = simulate_policy(plant, b1, d[:, WARMUP:first], d[:, :WARMUP], initial_last_sku=0)
    start_inv = pre.ending_cohorts
    start_last = plant.sku_ids.index(pre.week.last_sku.iloc[-1])
    return (cfg, plant, k, win, d[:, first:last], d[:, first - WARMUP:first], weeks[first:last], start_inv,
            start_last, b1)


def planner_settings(path: Path = ROOT / "configs" / "planner.yaml") -> dict:
    """Chosen on the VALIDATION year (ADR-007); missing file = ADR-003 defaults."""
    if not path.exists():
        return {"mode": "approx", "changeover_est": None}
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def make_policy(plant, cfg, b1, k, weeks, window, *, alpha=0.95, time_limit=60.0, mode="approx",
                changeover_est=None):
    fc = pd.read_parquet(ROOT / "results" / "forecast" / f"forecasts_{window}.parquet")
    cube = forecast_cube(fc, plant.sku_ids, weeks, H=13, scale=k)
    sig = pd.read_csv(ROOT / "results" / "forecast" / "error_sigma.csv")
    sigma = sig.pivot(index="sku_id", columns="horizon", values="sigma").loc[plant.sku_ids].to_numpy() * k
    d = cfg.sku_defaults
    est = None if changeover_est is None else np.array([changeover_est[s] for s in plant.sku_ids], float)
    return OptimisedPolicy(plant, cube, sigma, plant.rate * d.min_run_hours.value, plant.rate * d.max_run_hours.value,
                           load_costs(), alpha=alpha, time_limit_s=time_limit, mode=mode, fallback=b1,
                           changeover_est=est)


def summarise(name, r, plans, plant, cfg, start_last):
    plan = plan_to_frame(plans, plant, start_last)
    v = check(plan, cfg, initial_last_sku=plant.sku_ids[start_last], shipments=r.shipments)
    return {"arm": name, **{k: round(float(x), 4) for k, x in kpis.summarise(r).items()},
            "checker_violations": len(v)}, plan, v


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--time-limit", type=float, default=60)
    ap.add_argument("--alpha", type=float, default=0.95)
    ap.add_argument("--mode", default=None, help="override configs/planner.yaml (approx|arc)")
    a = ap.parse_args()
    t0 = time.perf_counter()
    ps = planner_settings()
    mode = a.mode or ps["mode"]
    cfg, plant, k, win, d_test, hist, weeks, start_inv, start_last, b1 = setup("test")
    assert d_test.shape[1] == 52

    rb, pb = run_arm(plant, b1, d_test, hist, start_inv, start_last)
    base_row, _, vb = summarise("baseline_B1", rb, pb, plant, cfg, start_last)
    ref = pd.read_csv(ROOT / "results" / "baseline_replay.csv").iloc[0]
    for key in ("expired_cases", "fill_rate", "changeover_hours"):
        assert abs(ref[key] - base_row[key]) < 1e-3, f"baseline mismatch on {key}: {ref[key]} vs {base_row[key]}"

    pol = make_policy(plant, cfg, b1, k, weeks, "test", alpha=a.alpha, time_limit=a.time_limit, mode=mode,
                      changeover_est=ps.get("changeover_est") if mode == "approx" else None)
    ro, po = run_arm(plant, pol, d_test, hist, start_inv, start_last)
    opt_row, plan_o, vo = summarise("optimised", ro, po, plant, cfg, start_last)
    if vo:
        raise SystemExit("ABORT: optimised plan failed the independent checker:\n" + "\n".join(map(str, vo[:20])))

    log = pd.DataFrame(pol.log)
    log.rename(columns={"solve_s": "solve_seconds"}).to_csv(ROOT / "results" / "logs" / "solves.csv", index=False)
    sku_weeks = pd.concat([r.sku_week.assign(arm=n) for n, r in (("baseline_B1", rb), ("optimised", ro))])
    sku_weeks.to_parquet(ROOT / "results" / "replay_sku_weeks.parquet", index=False)
    meta = {"window": f"{win.test_start.date()}..{win.test_end.date()}", "scale_factor": k, "alpha": a.alpha,
            "mode": mode, "changeover_est": ps.get("variant", "mean_incoming"), "time_limit_s": a.time_limit,
            "fallback_weeks": int(log.fallback_used.sum()),
            "repair_weeks": int((log.repairs > 0).sum()), "max_gap": float(log.gap.max()),
            "mean_solve_s": float(log.solve_s.mean()), "runtime_s": round(time.perf_counter() - t0, 1)}
    pd.DataFrame([{**opt_row, **meta}]).to_csv(ROOT / "results" / "optimized_replay.csv", index=False)
    plan_o.to_csv(ROOT / "results" / "optimized_plan_test.csv", index=False)
    costs = load_costs()
    base_row["evaluated_cost_index"] = 100.0
    opt_row["evaluated_cost_index"] = round(100 * evaluated_cost(ro, costs) / evaluated_cost(rb, costs), 2)
    comp = pd.DataFrame([base_row, opt_row]).set_index("arm").T
    comp["change_pct"] = 100 * (comp["optimised"] / comp["baseline_B1"] - 1)
    comp.to_csv(ROOT / "results" / "replay_comparison.csv")
    print(comp.round(3).to_string())
    print(meta)


if __name__ == "__main__":
    main()
