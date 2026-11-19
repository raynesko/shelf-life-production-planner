"""Shelf-life-aware lot-sizing MIP with optional allergen-aware sequencing (T4.2.1 spike -> T4.2.2/T4.2.3).

Full math: docs/methods/optimization.md. Sets: SKUs p, weeks t = 0..H-1, ages a = 0..A_p.

sequencing="arc"    : exact sequence-dependent changeovers inside the MIP (one run per SKU per week,
                      MTZ subtour elimination, carry-over of the line state between weeks).
sequencing="approx" : capacity charges a per-run changeover estimate; the run order is decided
                      afterwards per week by CP-SAT (decomposition; see opt/sequencing.py).
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import yaml
from ortools.linear_solver import pywraplp

from shelflife.sim.engine import SimPlant

COSTS_PATH = Path(__file__).resolve().parents[3] / "configs" / "costs.yaml"


def load_costs(path: Path | str = COSTS_PATH) -> dict[str, float]:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    return {k: float(v["value"]) for k, v in raw.items()}


@dataclass
class Instance:
    plant: SimPlant
    demand: np.ndarray                      # (n, H) forecast demand to plan against
    min_run_cases: np.ndarray
    max_run_cases: np.ndarray
    costs: dict[str, float]
    initial_inventory: list[dict[int, float]] | None = None   # ages at start of week 0 (>= 1)
    initial_last_sku: int | None = None
    safety_stock: np.ndarray | None = None  # (n, H) soft floor on usable end-of-week stock (T4.3.1)
    changeover_est: np.ndarray | None = None  # (n,) per-run changeover hours for "approx"; None = mean incoming

    @property
    def n(self) -> int:
        return self.plant.n

    @property
    def H(self) -> int:
        return self.demand.shape[1]


@dataclass
class Solution:
    status: str
    objective: float
    best_bound: float
    gap: float
    solve_seconds: float
    qty: np.ndarray                          # (n, H)
    order: list[list[int]]                   # run order per week (exact for "arc"; None-free)
    changeover_hours: np.ndarray             # (H,) model's own accounting
    n_vars: int = 0
    n_cons: int = 0
    extra: dict = field(default_factory=dict)

    @property
    def feasible(self) -> bool:
        return self.status in ("OPTIMAL", "FEASIBLE")

    def week_plans(self) -> list[list[tuple[int, float]]]:
        return [[(p, float(self.qty[p, t])) for p in self.order[t] if self.qty[p, t] > 1e-6]
                for t in range(self.qty.shape[1])]


STATUS = {pywraplp.Solver.OPTIMAL: "OPTIMAL", pywraplp.Solver.FEASIBLE: "FEASIBLE",
          pywraplp.Solver.INFEASIBLE: "INFEASIBLE", pywraplp.Solver.UNBOUNDED: "UNBOUNDED",
          pywraplp.Solver.ABNORMAL: "ABNORMAL", pywraplp.Solver.NOT_SOLVED: "NOT_SOLVED"}


def approx_changeover_per_run(plant: SimPlant) -> np.ndarray:
    """Per-run changeover estimate for the decomposition: mean incoming changeover over other SKUs."""
    C = plant.changeover_hours
    n = plant.n
    return np.array([np.mean([C[i, p] for i in range(n) if i != p]) for p in range(n)])


def build_and_solve(inst: Instance, sequencing: str = "arc", solver_name: str = "SCIP",
                    time_limit_s: float = 60.0, rel_gap: float = 0.02, verbose: bool = False,
                    export_lp: Path | str | None = None) -> Solution:
    t_build = time.perf_counter()
    plant, n, H, c = inst.plant, inst.n, inst.H, inst.costs
    if plant.available_hours <= 0 or np.any(np.asarray(inst.demand) < 0):
        return Solution("INVALID_INPUT", float("nan"), float("nan"), float("nan"), 0.0,
                        np.zeros((n, H)), [[] for _ in range(H)], np.zeros(H))
    A = plant.max_ship_age
    C = plant.changeover_hours
    d = np.asarray(inst.demand, float)
    s = pywraplp.Solver.CreateSolver(solver_name)
    if s is None:
        raise ValueError(f"solver {solver_name} unavailable")
    if verbose:
        s.EnableOutput()
    s.SetTimeLimit(int(time_limit_s * 1000))
    inf = s.infinity()
    init = inst.initial_inventory or [{} for _ in range(n)]

    x = {(p, t): s.NumVar(0, inf, f"x_{p}_{t}") for p in range(n) for t in range(H)}
    y = {(p, t): s.BoolVar(f"y_{p}_{t}") for p in range(n) for t in range(H)}
    sh = {(p, a, t): s.NumVar(0, inf, f"s_{p}_{a}_{t}") for p in range(n) for a in range(A[p] + 1)
          for t in range(H)}
    # I[p,a,t]: stock of age a available in week t (age 0 = this week's production)
    I: dict[tuple[int, int, int], object] = {}
    for p in range(n):
        for t in range(H):
            I[p, 0, t] = x[p, t]
            for a in range(1, A[p] + 1):
                if t == 0:
                    I[p, a, t] = float(init[p].get(a, 0.0))
                else:
                    I[p, a, t] = I[p, a - 1, t - 1] - sh[p, a - 1, t - 1]
            for a in range(A[p] + 1):
                s.Add(sh[p, a, t] <= I[p, a, t])
            s.Add(sum(sh[p, a, t] for a in range(A[p] + 1)) <= d[p, t])
            s.Add(x[p, t] >= inst.min_run_cases[p] * y[p, t])
            s.Add(x[p, t] <= inst.max_run_cases[p] * y[p, t])

    shipped = {(p, t): sum(sh[p, a, t] for a in range(A[p] + 1)) for p in range(n) for t in range(H)}
    lost = {(p, t): d[p, t] - shipped[p, t] for p in range(n) for t in range(H)}
    expired = {(p, t): I[p, A[p], t] - sh[p, A[p], t] for p in range(n) for t in range(H)}
    carried = {(p, t): sum(I[p, a, t] - sh[p, a, t] for a in range(A[p])) for p in range(n) for t in range(H)}

    run_h = {t: sum(x[p, t] * (1.0 / plant.rate[p]) for p in range(n)) for t in range(H)}
    co_h: dict[int, object] = {}
    order_vars = {}
    if sequencing == "arc":
        z = {(i, j, t): s.BoolVar(f"z_{i}_{j}_{t}")
             for t in range(H) for i in range(n) for j in range(n) if i != j}
        fr = {(p, t): s.BoolVar(f"fr_{p}_{t}") for p in range(n) for t in range(H)}
        lr = {(p, t): s.BoolVar(f"lr_{p}_{t}") for p in range(n) for t in range(H)}
        L = {(p, t): s.NumVar(0, 1, f"L_{p}_{t}") for p in range(n) for t in range(H)}
        r = {t: s.BoolVar(f"r_{t}") for t in range(H)}
        pos = {(p, t): s.NumVar(0, n, f"pos_{p}_{t}") for p in range(n) for t in range(H)}
        w = {(i, j, t): s.NumVar(0, 1, f"w_{i}_{j}_{t}") for t in range(H) for i in range(n) for j in range(n)
             if i != j}
        L_prev0 = [1.0 if inst.initial_last_sku == p else 0.0 for p in range(n)]
        for t in range(H):
            for p in range(n):
                s.Add(sum(z[i, p, t] for i in range(n) if i != p) + fr[p, t] == y[p, t])
                s.Add(sum(z[p, j, t] for j in range(n) if j != p) + lr[p, t] == y[p, t])
                s.Add(r[t] >= y[p, t])
                Lp = L_prev0[p] if t == 0 else L[p, t - 1]
                s.Add(L[p, t] >= lr[p, t])
                s.Add(L[p, t] >= Lp - r[t])
            s.Add(r[t] <= sum(y[p, t] for p in range(n)))
            s.Add(sum(fr[p, t] for p in range(n)) == r[t])
            s.Add(sum(lr[p, t] for p in range(n)) == r[t])
            s.Add(sum(L[p, t] for p in range(n)) == 1)
            for i in range(n):
                for j in range(n):
                    if i == j:
                        continue
                    s.Add(pos[j, t] >= pos[i, t] + 1 - n * (1 - z[i, j, t]))
                    Li = L_prev0[i] if t == 0 else L[i, t - 1]
                    s.Add(w[i, j, t] >= Li + fr[j, t] - 1)
            co_h[t] = sum(C[i, j] * (z[i, j, t] + w[i, j, t]) for i in range(n) for j in range(n) if i != j)
        order_vars = {"pos": pos, "y": y}
    elif sequencing == "approx":
        est = (approx_changeover_per_run(plant) if inst.changeover_est is None
               else np.asarray(inst.changeover_est, float))
        for t in range(H):
            co_h[t] = sum(est[p] * y[p, t] for p in range(n))
    else:
        raise ValueError(sequencing)

    for t in range(H):
        s.Add(run_h[t] + co_h[t] <= plant.available_hours)

    obj = 0
    for p in range(n):
        for t in range(H):
            obj += c["production_per_case"] * x[p, t] + c["lost_sale_per_case"] * lost[p, t] \
                + c["expiry_per_case"] * expired[p, t] + c["holding_per_case_week"] * carried[p, t]
    obj += c["changeover_per_hour"] * sum(co_h[t] for t in range(H))
    ss_short = {}
    if inst.safety_stock is not None:
        for p in range(n):
            for t in range(H):
                usable_next = sum(I[p, a, t] - sh[p, a, t] for a in range(A[p]))
                ss_short[p, t] = s.NumVar(0, inf, f"ssu_{p}_{t}")
                s.Add(ss_short[p, t] >= float(inst.safety_stock[p, t]) - usable_next)
                obj += c["safety_stock_shortfall_per_case"] * ss_short[p, t]
    s.Minimize(obj)
    build_s = time.perf_counter() - t_build
    if export_lp:
        Path(export_lp).write_text(s.ExportModelAsLpFormat(False), encoding="utf-8")

    params = pywraplp.MPSolverParameters()
    params.SetDoubleParam(pywraplp.MPSolverParameters.RELATIVE_MIP_GAP, rel_gap)
    t0 = time.perf_counter()
    st = s.Solve(params)
    secs = time.perf_counter() - t0
    status = STATUS.get(st, f"NO_SOLUTION_{st}")
    if status not in ("OPTIMAL", "FEASIBLE"):
        return Solution(status, float("nan"), float("nan"), float("nan"), secs, np.zeros((n, H)),
                        [[] for _ in range(H)], np.zeros(H), s.NumVariables(), s.NumConstraints())

    def ev(expr):
        return float(expr) if isinstance(expr, (int, float)) else float(_lin_value(expr))

    qty = np.array([[x[p, t].solution_value() for t in range(H)] for p in range(n)])
    qty[qty < 1e-6] = 0.0
    if sequencing == "arc":
        order = [sorted([p for p in range(n) if y[p, t].solution_value() > 0.5],
                        key=lambda p, t=t: order_vars["pos"][p, t].solution_value()) for t in range(H)]
    else:
        order = [[p for p in range(n) if y[p, t].solution_value() > 0.5] for t in range(H)]
    cov = np.array([ev(co_h[t]) for t in range(H)])
    best = s.Objective().BestBound()
    objv = s.Objective().Value()
    gap = abs(objv - best) / max(abs(objv), 1e-9)
    return Solution(status, objv, best, gap, secs, qty, order, cov, s.NumVariables(), s.NumConstraints(),
                    extra={"build_seconds": build_s,
                           "lost": np.array([[ev(lost[p, t]) for t in range(H)] for p in range(n)]),
                           "expired": np.array([[ev(expired[p, t]) for t in range(H)] for p in range(n)])})


def _lin_value(expr) -> float:
    """Evaluate a pywraplp linear expression at the current solution."""
    return expr.solution_value()
