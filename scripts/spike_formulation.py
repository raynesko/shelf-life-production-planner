"""T4.2.1 spike: single MIP with arc sequencing (A) vs decomposition lot-sizing + CP-SAT sequencing (B).

Synthetic demand (seeded) only; no real data needed. Every plan is scored by the SAME evaluator: the
simulator replays the plan against the planning demand and costs come from configs/costs.yaml.
Run: python scripts/spike_formulation.py [--quick]
Output: results/logs/spike_formulation.csv (+ printed table)
"""
from __future__ import annotations

import argparse
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd

from shelflife.opt.model import Instance, build_and_solve, load_costs
from shelflife.opt.sequencing import sequence_week
from shelflife.plant.changeover import build_matrix
from shelflife.plant.config import load
from shelflife.sim.engine import SimPlant, simulate

ROOT = Path(__file__).resolve().parents[1]


def subplant(plant: SimPlant, idx: list[int]) -> SimPlant:
    ix = np.ix_(idx, idx)
    return replace(plant, sku_ids=[plant.sku_ids[i] for i in idx], shelf_life_days=plant.shelf_life_days[idx],
                   rate=plant.rate[idx], changeover_hours=plant.changeover_hours[ix],
                   allergen_clean=plant.allergen_clean[ix])


def synth_demand(plant: SimPlant, H: int, load: float, seed: int) -> np.ndarray:
    """Demand whose total run hours ~= load x available hours; skewed mix, seasonal wiggle, noise."""
    rng = np.random.default_rng(seed)
    n = plant.n
    share = rng.dirichlet(np.full(n, 1.5))
    hours = load * plant.available_hours * share
    mean = hours * plant.rate
    t = np.arange(H)
    season = 1 + 0.15 * np.sin(2 * np.pi * (t[None, :] + rng.integers(0, 52, (n, 1))) / 52)
    return np.rint(mean[:, None] * season * rng.lognormal(0, 0.15, (n, H)))


def evaluate(plant: SimPlant, plans, demand, costs, last0) -> dict:
    r = simulate(plant, plans, demand, initial_last_sku=last0)
    sw, wk = r.sku_week, r.week
    cost = (costs["production_per_case"] * sw.produced.sum() + costs["lost_sale_per_case"] * sw.lost.sum()
            + costs["expiry_per_case"] * sw.expired.sum()
            + costs["holding_per_case_week"] * sw.end_inventory.sum()
            + costs["changeover_per_hour"] * wk.changeover_hours.sum())
    return {"eval_cost": cost, "changeover_h": wk.changeover_hours.sum(), "lost": sw.lost.sum(),
            "expired": sw.expired.sum(), "fill_rate": sw.shipped.sum() / sw.demand.sum(),
            "capacity_breach_weeks": int(wk.capacity_breach.sum()), "max_util": wk.utilisation.max()}


def decompose(inst: Instance, solver: str, tl: float) -> tuple[list, dict]:
    sol = build_and_solve(inst, "approx", solver, tl)
    if not sol.feasible:
        return [], {"status": sol.status, "solve_s": sol.solve_seconds}
    plant, last, plans, repaired, seq_s = inst.plant, inst.initial_last_sku, [], 0, 0.0
    import time
    for t in range(inst.H):
        q = sol.qty[:, t].copy()
        for _ in range(plant.n + 1):
            t0 = time.perf_counter()
            order, co = sequence_week([p for p in range(plant.n) if q[p] > 0], plant.changeover_hours, last)
            seq_s += time.perf_counter() - t0
            run = float(np.sum(q / plant.rate))
            if run + co <= plant.available_hours + 1e-9:
                break
            repaired += 1
            q = q * max(plant.available_hours - co, 0) / run
            q = np.where(q + 1e-9 >= inst.min_run_cases, q, 0.0)
        plans.append([(p, float(q[p])) for p in order if q[p] > 0])
        last = order[-1] if order else last
    return plans, {"status": sol.status, "solve_s": sol.solve_seconds + seq_s, "gap": sol.gap,
                   "mip_obj": sol.objective, "repair_iters": repaired, "n_vars": sol.n_vars}


def main(quick: bool) -> None:
    cfg = load()
    full = SimPlant.from_config(cfg, build_matrix(cfg))
    costs = load_costs()
    d = cfg.sku_defaults
    cases = {
        "toy_4x8": (subplant(full, [0, 3, 7, 10]), 8),        # yogurt, pudding, guacamole, tuna salad
        "full_12x13": (full, 13),
    }
    runs = [("A_arc", "SCIP"), ("A_arc", "HIGHS"), ("B_decomp", "SCIP"), ("B_decomp", "HIGHS")]
    if not quick:
        runs.append(("A_arc", "CBC"))
    rows = []
    for name, (plant, H) in cases.items():
        demand = synth_demand(plant, H, load=0.78, seed=11)
        inst = Instance(plant, demand, plant.rate * d.min_run_hours.value, plant.rate * d.max_run_hours.value,
                        costs, initial_last_sku=0)
        tl = 30 if name.startswith("toy") else (60 if quick else 120)
        for approach, solver in runs:
            if approach == "A_arc":
                sol = build_and_solve(inst, "arc", solver, tl)
                info = {"status": sol.status, "solve_s": sol.solve_seconds, "gap": sol.gap,
                        "mip_obj": sol.objective, "n_vars": sol.n_vars}
                plans = sol.week_plans() if sol.feasible else []
            else:
                plans, info = decompose(inst, solver, tl)
            ev = evaluate(plant, plans, demand, costs, 0) if plans else {}
            rows.append({"instance": name, "approach": approach, "solver": solver, "time_limit_s": tl,
                         **info, **ev})
            print({k: (round(v, 3) if isinstance(v, float) else v) for k, v in rows[-1].items()}, flush=True)
    df = pd.DataFrame(rows)
    out = ROOT / "results" / "logs" / "spike_formulation.csv"
    df.to_csv(out, index=False)
    cols = ["instance", "approach", "solver", "status", "solve_s", "gap", "eval_cost", "changeover_h",
            "lost", "expired", "capacity_breach_weeks"]
    print("\n" + df[[c for c in cols if c in df]].round(3).to_string(index=False))
    print(f"wrote {out.relative_to(ROOT)}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    main(ap.parse_args().quick)
