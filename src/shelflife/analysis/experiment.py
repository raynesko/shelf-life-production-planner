"""Experiment engine (T5.1.1; reused by the ablation T5.1.3 and sensitivity T5.2.1).

Layer A (replay): the real test-year demand, one run per arm.
Layer B (Monte Carlo): N demand paths from the block-bootstrap scenario generator (T3.3.1) around the real
test-year one-step forecasts. COMMON RANDOM NUMBERS: all paths are drawn once from one seed and every arm is
replayed on the identical path array, so arm differences are paired per path.

Every arm starts the test year from the same state: B1 run on actual demand from 2013 to the week before the
test year (under the same plant overrides).

Limitation (recorded in docs/methods/experiments.md): in Layer B the optimiser's forecasts are the real
test-year forecasts; they are NOT refit to each simulated path, while B1's moving average does see the path.
This favours B1 slightly when a path drifts away from the real forecast.

Arms
- B1        : baseline B1 (moving average 4, reorder point, cover `b1_cover`)
- OPT       : rolling-horizon optimiser with the selected forecast + safety stock (configs/planner.yaml)
- B1_SELFC  : B1 sizing, but its forecast is the selected model's one-step forecast (ablation)
- OPT_MA4   : optimiser planning on a flat MA(4) forecast of the observed demand (ablation)
- B1_TUNED  : B1 with the cover chosen on the validation year by the optimiser's tuning rule
              (configs/baseline.yaml, ADR-009); same start state as every arm.
"""
from __future__ import annotations

import dataclasses
import hashlib
import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from shelflife.checks.plan_checker import check
from shelflife.forecast.backtest import make_windows
from shelflife.forecast.scenarios import ScenarioGenerator
from shelflife.opt.model import load_costs
from shelflife.opt.rolling import OptimisedPolicy, forecast_cube, run_arm
from shelflife.plant.changeover import build_matrix
from shelflife.plant.config import load
from shelflife.sim import kpis
from shelflife.sim.baseline import BaselineB1
from shelflife.sim.engine import SimPlant, plan_to_frame, simulate_policy

ROOT = Path(__file__).resolve().parents[3]
FC = ROOT / "results" / "forecast"
WARMUP = 4
ARMS = ("B1", "OPT", "B1_SELFC", "OPT_MA4", "B1_TUNED")


@dataclass(frozen=True)
class Overrides:
    """One-at-a-time sensitivity knobs (T5.2.1). Defaults reproduce the main experiment."""
    shelf_life_scale: float = 1.0
    changeover_scale: float = 1.0
    error_scale: float = 1.0          # Monte Carlo error amplitude AND the planner's sigma
    demand_scale: float = 1.0         # utilisation lever: demand and forecasts scaled together
    msl: float | None = None          # min remaining shelf life at shipment; None = plant.yaml
    b1_cover: float = 1.0
    alpha: float = 0.95
    costs: dict[str, float] = field(default_factory=dict)   # cost-weight overrides

    def key(self) -> str:
        return json.dumps(dataclasses.asdict(self), sort_keys=True)


@dataclass
class Context:
    plant: SimPlant
    cfg: object
    b1: BaselineB1
    k: float
    weeks: pd.DatetimeIndex
    actual: np.ndarray            # (n, 52) cases
    hist: np.ndarray              # (n, WARMUP) observed demand before the test year
    start_inv: list
    start_last: int
    cube: np.ndarray              # (n, 52, H) selected-model forecasts, cases
    sigma: np.ndarray             # (n, H) cases
    yhat1: np.ndarray             # (n, 52) one-step forecasts, cases
    costs: dict[str, float]
    planner: dict
    ov: Overrides


def planner_settings() -> dict:
    p = ROOT / "configs" / "planner.yaml"
    if not p.exists():
        return {"mode": "approx", "changeover_est": None, "variant": "mean"}
    return yaml.safe_load(p.read_text(encoding="utf-8"))


def tuned_b1_cover() -> float:
    p = ROOT / "configs" / "baseline.yaml"
    return float(yaml.safe_load(p.read_text(encoding="utf-8"))["cover_weeks"]) if p.exists() else 1.0


def build_context(ov: Overrides = Overrides()) -> Context:
    cfg = load()
    base = SimPlant.from_config(cfg, build_matrix(cfg), msl=ov.msl, shelf_life_scale=ov.shelf_life_scale)
    plant = dataclasses.replace(base, changeover_hours=base.changeover_hours * ov.changeover_scale)
    k = yaml.safe_load((ROOT / "configs" / "calibration.yaml").read_text())["scale_factor"] * ov.demand_scale
    panel = pd.read_parquet(ROOT / "data" / "processed" / "demand_weekly.parquet")
    win = make_windows(panel.week_start)
    wide = panel.pivot(index="sku_id", columns="week_start", values="units").loc[plant.sku_ids]
    d = wide.to_numpy(float) * k
    weeks = wide.columns
    first = int(np.where(weeks == win.test_start)[0][0])
    b1 = BaselineB1.from_config(cfg, plant, cover_weeks=ov.b1_cover)
    pre, _ = simulate_policy(plant, b1, d[:, WARMUP:first], d[:, :WARMUP], initial_last_sku=0)
    fc = pd.read_parquet(FC / "forecasts_test.parquet")
    test_weeks = weeks[first:]
    cube = forecast_cube(fc, plant.sku_ids, test_weeks, H=13, scale=k)
    sig = pd.read_csv(FC / "error_sigma.csv")
    sigma = sig.pivot(index="sku_id", columns="horizon", values="sigma").loc[plant.sku_ids].to_numpy() * k
    costs = {**load_costs(), **ov.costs}
    return Context(plant, cfg, b1, k, test_weeks, d[:, first:], d[:, first - WARMUP:first], pre.ending_cohorts,
                   plant.sku_ids.index(pre.week.last_sku.iloc[-1]), cube, sigma * ov.error_scale,
                   cube[:, :, 0].copy(), costs, planner_settings(), ov)


def scenario_paths(ctx: Context, n_paths: int, seed: int) -> np.ndarray:
    """(n_paths, n, 52) demand in cases; identical for every arm (common random numbers)."""
    val = pd.read_parquet(FC / "forecasts_validation.parquet")
    test = pd.read_parquet(FC / "forecasts_test.parquet")
    gen = ScenarioGenerator.from_frames(val, test, pd.read_csv(FC / "error_sigma.csv"))
    assert gen.sku_ids == ctx.plant.sku_ids, "scenario SKU order must match the plant"
    return gen.generate(n_paths, seed, error_scale=ctx.ov.error_scale) * ctx.k


class _SelectedForecastB1(BaselineB1):
    """B1 whose forecast is the selected model's one-step forecast for the current week (ablation)."""
    yhat1: np.ndarray

    def forecast(self, observed: np.ndarray) -> np.ndarray:
        t = observed.shape[1] - WARMUP
        return self.yhat1[:, t]


def _policy(ctx: Context, arm: str, demand: np.ndarray):
    pl, c = ctx.plant, ctx.cfg.sku_defaults
    if arm == "B1":
        return ctx.b1, None
    if arm == "B1_TUNED":
        return BaselineB1(pl, ctx.b1.ladder, ctx.b1.min_run_cases, ctx.b1.max_run_cases, tuned_b1_cover()), None
    if arm == "B1_SELFC":
        b = _SelectedForecastB1(pl, ctx.b1.ladder, ctx.b1.min_run_cases, ctx.b1.max_run_cases,
                                ctx.b1.cover_weeks)
        b.yhat1 = ctx.yhat1
        return b, None
    cube = ctx.cube
    if arm == "OPT_MA4":
        hist_all = np.concatenate([ctx.hist, demand], axis=1)
        ma = np.stack([hist_all[:, t:t + WARMUP].mean(axis=1) for t in range(demand.shape[1])], axis=1)
        cube = np.repeat(ma[:, :, None], cube.shape[2], axis=2)
    ps = ctx.planner
    mode = ps.get("mode", "approx")
    est = ps.get("changeover_est")
    est = None if (est is None or mode != "approx") else \
        np.array([est[s] for s in pl.sku_ids], float) * ctx.ov.changeover_scale
    pol = OptimisedPolicy(pl, cube, ctx.sigma, pl.rate * c.min_run_hours.value, pl.rate * c.max_run_hours.value,
                          ctx.costs, alpha=ctx.ov.alpha, time_limit_s=60.0, mode=mode, fallback=ctx.b1,
                          changeover_est=est)
    return pol, pol


def run_one(ctx: Context, arm: str, demand: np.ndarray, *, check_plan: bool = True) -> dict:
    """Replay one arm on one 52-week demand matrix (cases) from the common start state."""
    policy, opt = _policy(ctx, arm, demand)
    r, plans = run_arm(ctx.plant, policy, demand, ctx.hist, ctx.start_inv, ctx.start_last)
    row = {k: float(v) for k, v in kpis.summarise(r).items()}
    row["evaluated_cost"] = kpis.evaluated_cost(r, ctx.costs)
    row["produced_cases"] = float(r.sku_week.produced.sum())
    row["demand_cases"] = float(r.sku_week.demand.sum())
    if opt is not None:
        log = pd.DataFrame(opt.log)
        row["fallback_weeks"] = int(log.fallback_used.sum())
        row["max_gap"] = float(log.gap.max())
        row["solve_s_total"] = float(log.solve_s.sum())
    if check_plan:
        plan = plan_to_frame(plans, ctx.plant, ctx.start_last)
        v = check(plan, ctx.cfg, initial_last_sku=ctx.plant.sku_ids[ctx.start_last], shipments=r.shipments,
                  available_hours=ctx.plant.available_hours, msl=ctx.plant.msl,
                  changeover_scale=ctx.ov.changeover_scale, shelf_life_scale=ctx.ov.shelf_life_scale)
        row["checker_violations"] = len(v)
    return row


def kpi_hash(df: pd.DataFrame) -> str:
    cols = sorted(c for c in df.columns if c not in ("runtime_s", "solve_s_total"))
    s = df.sort_values(["layer", "path_id", "arm"])[cols].round(6).to_csv(index=False)
    return hashlib.sha256(s.encode()).hexdigest()


def code_version() -> dict:
    out = {}
    try:
        out["git_hash"] = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True,
                                         check=True).stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        out["git_hash"] = None
    try:
        dirty = subprocess.run(["git", "status", "--porcelain", "src", "scripts", "configs"], cwd=ROOT,
                               capture_output=True, text=True, check=True).stdout
        out["git_dirty"] = bool(dirty.strip())
    except (subprocess.CalledProcessError, FileNotFoundError):
        out["git_dirty"] = None
    h = hashlib.sha256()
    for p in sorted((ROOT / "src").rglob("*.py")) + sorted((ROOT / "configs").glob("*.yaml")):
        h.update(p.read_bytes())
    out["source_sha256"] = h.hexdigest()
    return out
