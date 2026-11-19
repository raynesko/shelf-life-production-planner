"""Rolling-horizon planner and arm runner (T4.3.2).

Each week t of the evaluation window:
  1. take that week's forecast for horizons 1..H (missing tail horizons near the end of the data are filled by
     repeating the last available horizon; affects only the final weeks, documented),
  2. compute soft safety stock (opt.safety_stock) from validation-year sigma,
  3. solve the lot-sizing MIP (ADR-003 default: decomposition = "approx" MIP + CP-SAT sequencing) from the
     CURRENT simulated state (inventory by age, last SKU on the line),
  4. sequence week 1 with CP-SAT given the line state, repair capacity pro rata if needed,
  5. execute week 1 in the simulator against ACTUAL demand; log status/gap/time; re-plan next week.
If the solver returns no plan, the week falls back to baseline B1's plan (counted).
"""
from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from shelflife.opt.model import Instance, build_and_solve
from shelflife.opt.safety_stock import safety_stock
from shelflife.opt.sequencing import sequence_week
from shelflife.sim.engine import PlantState, SimPlant, WeekPlan


def sequence_and_repair(q: np.ndarray, plant: SimPlant, last: int | None, min_run: np.ndarray
                        ) -> tuple[WeekPlan, int]:
    # Solver noise: with the run switch off, SCIP may still return q of a few 1e-3 cases (inside its feasibility
    # tolerance). Such a "run" would cost a changeover and break the min-run rule (caught by the checker in 2 of
    # ~2,000 sensitivity plans). Below half a minimum run -> 0; just under the minimum -> raised to it.
    q = np.where(q < 0.5 * min_run, 0.0, np.maximum(q, min_run))
    repairs = 0
    order: list[int] = []
    for _ in range(plant.n + 1):
        order, co = sequence_week([p for p in range(plant.n) if q[p] > 1e-6], plant.changeover_hours, last)
        run = float(np.sum(q / plant.rate))
        if run + co <= plant.available_hours + 1e-9:
            break
        repairs += 1
        q = q * max(plant.available_hours - co, 0.0) / run
        q = np.where(q + 1e-9 >= min_run, q, 0.0)
    return [(p, float(q[p])) for p in order if q[p] > 1e-6], repairs


@dataclass
class OptimisedPolicy:
    plant: SimPlant
    forecasts: np.ndarray            # (n, T, H): forecast made at evaluation week t for horizons 1..H
    sigma: np.ndarray                # (n, H_max) error std by horizon (same units as forecasts)
    min_run: np.ndarray
    max_run: np.ndarray
    costs: dict[str, float]
    alpha: float = 0.95
    use_safety_stock: bool = True
    time_limit_s: float = 60.0
    rel_gap: float = 0.02
    mode: str = "approx"
    changeover_est: np.ndarray | None = None   # (n,) per-run estimate for "approx" (ADR-007); None = mean
    fallback: Callable[[PlantState, np.ndarray], WeekPlan] | None = None
    log: list[dict] = field(default_factory=list)

    def __call__(self, state: PlantState, observed: np.ndarray) -> WeekPlan:
        t = state.t_eval
        f = self.forecasts[:, t, :]
        ss = safety_stock(self.sigma, f, self.plant.max_ship_age, self.alpha) if self.use_safety_stock else None
        inst = Instance(self.plant, f, self.min_run, self.max_run, self.costs,
                        initial_inventory=[dict(c) for c in state.inv], initial_last_sku=state.last_sku,
                        safety_stock=ss, changeover_est=self.changeover_est)
        t0 = time.perf_counter()
        sol = build_and_solve(inst, self.mode, "SCIP", self.time_limit_s, self.rel_gap)
        rec = {"week": t, "status": sol.status, "gap": sol.gap, "solve_s": sol.solve_seconds,
               "fallback_used": False, "repairs": 0}
        if not sol.feasible:
            rec["fallback_used"] = True
            wp = list(self.fallback(state, observed)) if self.fallback else []
        elif self.mode == "arc":
            wp = sol.week_plans()[0]
        else:
            wp, rec["repairs"] = sequence_and_repair(sol.qty[:, 0], self.plant, state.last_sku, self.min_run)
        rec["total_s"] = time.perf_counter() - t0
        rec["runs"] = len(wp)
        self.log.append(rec)
        return wp


def forecast_cube(fc: pd.DataFrame, sku_ids: list[str], eval_weeks: pd.DatetimeIndex, H: int = 13,
                  scale: float = 1.0) -> np.ndarray:
    """Harness rows (origin = first forecast week) -> (n, T, H) array; tail horizons filled forward."""
    cube = np.full((len(sku_ids), len(eval_weeks), H), np.nan)
    sidx = {s: i for i, s in enumerate(sku_ids)}
    widx = {w: i for i, w in enumerate(eval_weeks)}
    for r in fc[fc.origin.isin(eval_weeks) & fc.sku_id.isin(sidx) & (fc.horizon <= H)].itertuples():
        cube[sidx[r.sku_id], widx[r.origin], r.horizon - 1] = r.yhat
    if np.isnan(cube[:, :, 0]).any():
        raise ValueError("missing horizon-1 forecasts for some evaluation weeks")
    for h in range(1, H):
        miss = np.isnan(cube[:, :, h])
        cube[:, :, h][miss] = cube[:, :, h - 1][miss]
    return cube * scale


def run_arm(plant: SimPlant, policy, demand: np.ndarray, observed_hist: np.ndarray,
            start_inventory: list[dict[int, float]], start_last_sku: int | None):
    """Run a policy over the evaluation weeks from a given start state (both arms use the same start)."""
    st = PlantState(plant, start_inventory, start_last_sku)
    plans: list[WeekPlan] = []
    for t in range(demand.shape[1]):
        st.t_eval = t
        observed = np.concatenate([observed_hist, demand[:, :t]], axis=1)
        wp = list(policy(st, observed))
        plans.append(wp)
        st.step(wp, demand[:, t])
    return st.result(), plans
