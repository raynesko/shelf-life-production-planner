"""T4.3.1: safety stock monotone in alpha, shelf-life cap, and the optimiser responds to it."""
from dataclasses import replace

import numpy as np
import pytest

from shelflife.opt.model import Instance, build_and_solve, load_costs
from shelflife.opt.safety_stock import safety_stock
from shelflife.plant.changeover import build_matrix
from shelflife.plant.config import load
from shelflife.sim.engine import SimPlant, simulate


def test_monotone_in_alpha():
    sigma = np.full((3, 13), 50.0)
    f = np.full((3, 13), 1000.0)
    A = np.array([1, 2, 4])
    means = [safety_stock(sigma, f, A, a).mean() for a in (0.80, 0.90, 0.95, 0.99)]
    assert all(b > a for a, b in zip(means, means[1:], strict=False))


def test_cap_binds_for_slow_short_life_sku():
    # Slow mover (20 cases/week), noisy (sigma 100), sellable for 1 more week -> cap = next week's forecast.
    sigma = np.full((1, 13), 100.0)
    f = np.full((1, 6), 20.0)
    ss = safety_stock(sigma, f, np.array([1]), 0.95)
    assert np.allclose(ss[0, :-1], 20.0)          # capped by 1 week of forecast
    assert ss[0, -1] == 0.0                       # nothing left to sell beyond the horizon
    assert np.all(safety_stock(sigma, f, np.array([0]), 0.95) == 0)   # must ship the week it is made


def test_alpha_out_of_range():
    with pytest.raises(ValueError):
        safety_stock(np.ones((1, 13)), np.ones((1, 3)), np.array([1]), 1.0)


def test_optimiser_holds_more_stock_with_safety_stock():
    cfg = load()
    plant = SimPlant.from_config(cfg, build_matrix(cfg))
    idx = [0, 1, 2]
    ix = np.ix_(idx, idx)
    p = replace(plant, sku_ids=[plant.sku_ids[i] for i in idx], shelf_life_days=plant.shelf_life_days[idx],
                rate=plant.rate[idx], changeover_hours=plant.changeover_hours[ix],
                allergen_clean=plant.allergen_clean[ix])
    d = cfg.sku_defaults
    demand = np.full((3, 5), 800.0)
    base = Instance(p, demand, p.rate * d.min_run_hours.value, p.rate * d.max_run_hours.value, load_costs(),
                    initial_last_sku=0)
    ss = safety_stock(np.full((3, 13), 150.0), demand, p.max_ship_age, 0.95)
    s0 = build_and_solve(base, "approx", "SCIP", 20, rel_gap=1e-6)
    s1 = build_and_solve(replace(base, safety_stock=ss), "approx", "SCIP", 20, rel_gap=1e-6)
    assert s0.status == s1.status == "OPTIMAL"
    # Same total (no end-of-horizon value) but timing changes: with SS, end-of-week stock never drops below
    # target before the last week; without it, stock runs to zero mid-horizon.
    def end_inv(sol):
        r = simulate(p, sol.week_plans(), demand, initial_last_sku=0)
        inv = r.sku_week.pivot(index="sku_id", columns="week", values="end_inventory")
        return inv.loc[p.sku_ids].to_numpy()
    e0, e1 = end_inv(s0), end_inv(s1)
    assert np.all(e1[:, :-1] >= ss[:, :-1] - 1e-6)
    assert np.any(e0[:, :-1] < ss[:, :-1] - 1e-6)
    assert s1.qty.sum() == pytest.approx(s0.qty.sum())
