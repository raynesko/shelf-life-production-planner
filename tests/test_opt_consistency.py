"""Optimiser <-> simulator consistency and sequencing correctness (T4.2.1 spike guards)."""
from dataclasses import replace

import numpy as np
import pytest

from shelflife.opt.model import Instance, build_and_solve, load_costs
from shelflife.opt.sequencing import brute_force, sequence_week
from shelflife.plant.changeover import build_matrix
from shelflife.plant.config import load
from shelflife.sim.engine import SimPlant, simulate


@pytest.fixture(scope="module")
def full():
    cfg = load()
    return cfg, SimPlant.from_config(cfg, build_matrix(cfg))


def small(plant, idx):
    ix = np.ix_(idx, idx)
    return replace(plant, sku_ids=[plant.sku_ids[i] for i in idx], shelf_life_days=plant.shelf_life_days[idx],
                   rate=plant.rate[idx], changeover_hours=plant.changeover_hours[ix],
                   allergen_clean=plant.allergen_clean[ix])


def sim_cost(plant, plans, demand, costs, last):
    r = simulate(plant, plans, demand, initial_last_sku=last)
    sw, wk = r.sku_week, r.week
    return (costs["production_per_case"] * sw.produced.sum() + costs["lost_sale_per_case"] * sw.lost.sum()
            + costs["expiry_per_case"] * sw.expired.sum()
            + costs["holding_per_case_week"] * sw.end_inventory.sum()
            + costs["changeover_per_hour"] * wk.changeover_hours.sum()), r


@pytest.mark.parametrize("seed", [0, 1, 2, 3, 4])
def test_arc_model_cost_equals_simulator_cost(full, seed):
    cfg, plant = full
    p = small(plant, [0, 3, 7, 10])
    rng = np.random.default_rng(seed)
    demand = np.rint(rng.uniform(500, 3500, (4, 4)))
    costs = load_costs()
    d = cfg.sku_defaults
    inst = Instance(p, demand, p.rate * d.min_run_hours.value, p.rate * d.max_run_hours.value, costs,
                    initial_last_sku=1)
    sol = build_and_solve(inst, "arc", "SCIP", 30, rel_gap=1e-6)
    assert sol.status == "OPTIMAL"
    cost, r = sim_cost(p, sol.week_plans(), demand, costs, 1)
    assert cost == pytest.approx(sol.objective, rel=1e-6)
    assert r.week.changeover_hours.to_numpy() == pytest.approx(sol.changeover_hours, abs=1e-6)
    assert not r.week.capacity_breach.any()


def test_arc_order_is_cheapest_for_chosen_set(full):
    """Within each week, the MIP's run order must be no worse than the brute-force best order."""
    cfg, plant = full
    p = small(plant, [0, 3, 4, 7, 10])
    demand = np.full((5, 3), 1500.0)
    d = cfg.sku_defaults
    inst = Instance(p, demand, p.rate * d.min_run_hours.value, p.rate * d.max_run_hours.value, load_costs(),
                    initial_last_sku=2)
    sol = build_and_solve(inst, "arc", "SCIP", 30, rel_gap=1e-6)
    last = 2
    for t, order in enumerate(sol.order):
        _, best = brute_force(order, p.changeover_hours, last)
        assert sol.changeover_hours[t] == pytest.approx(best, abs=1e-6)
        last = order[-1] if order else last


def test_cpsat_sequencing_matches_brute_force(full):
    _, plant = full
    C = plant.changeover_hours
    rng = np.random.default_rng(0)
    for _ in range(15):
        skus = [int(s) for s in rng.choice(12, size=rng.integers(2, 7), replace=False)]
        last = int(rng.integers(0, 12))
        order, h = sequence_week(skus, C, last)
        assert sorted(order) == sorted(skus)
        assert h == pytest.approx(brute_force(skus, C, last)[1])


def test_zero_demand_produces_nothing(full):
    cfg, plant = full
    p = small(plant, [0, 1, 2])
    d = cfg.sku_defaults
    inst = Instance(p, np.zeros((3, 3)), p.rate * d.min_run_hours.value, p.rate * d.max_run_hours.value,
                    load_costs(), initial_last_sku=0)
    for mode in ("arc", "approx"):
        sol = build_and_solve(inst, mode, "SCIP", 10)
        assert sol.feasible and sol.qty.sum() == 0


def test_zero_changeover_arc_equals_pure_lot_sizing(full):
    """T4.2.3 regression: with all changeover times 0, sequencing must not change the optimum."""
    cfg, plant = full
    p = replace(small(plant, [0, 3, 7, 10]), changeover_hours=np.zeros((4, 4)))
    rng = np.random.default_rng(9)
    demand = np.rint(rng.uniform(500, 3500, (4, 5)))
    d = cfg.sku_defaults
    inst = Instance(p, demand, p.rate * d.min_run_hours.value, p.rate * d.max_run_hours.value, load_costs(),
                    initial_last_sku=0)
    arc = build_and_solve(inst, "arc", "SCIP", 30, rel_gap=1e-9)
    lot = build_and_solve(inst, "approx", "SCIP", 30, rel_gap=1e-9)   # approx estimate is 0 here too
    assert arc.status == lot.status == "OPTIMAL"
    assert arc.objective == pytest.approx(lot.objective, rel=1e-9)
