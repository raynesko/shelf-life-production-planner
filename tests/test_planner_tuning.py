"""ADR-007: per-run changeover estimate for the decomposition and the simulator-evaluated cost KPI."""
import numpy as np
import pandas as pd

from shelflife.opt.model import Instance, approx_changeover_per_run, build_and_solve, load_costs
from shelflife.sim.engine import SimPlant, SimResult
from shelflife.sim.kpis import evaluated_cost


def plant():
    return SimPlant(["P", "Q"], np.array([14.0, 14.0]), np.array([1000.0, 1000.0]), 10.0, 0.5,
                    np.array([[0.0, 3.0], [3.0, 0.0]]), np.zeros((2, 2), bool))


def inst(est=None):
    return Instance(plant(), np.full((2, 4), 1000.0), np.array([500.0, 500.0]), np.array([9000.0, 9000.0]),
                    load_costs(), initial_last_sku=0, changeover_est=est)


def test_default_estimate_equals_explicit_mean():
    a = build_and_solve(inst(), "approx", time_limit_s=10)
    b = build_and_solve(inst(approx_changeover_per_run(plant())), "approx", time_limit_s=10)
    assert np.allclose(a.qty, b.qty) and abs(a.objective - b.objective) < 1e-6


def test_lower_estimate_charges_less_changeover():
    hi = build_and_solve(inst(np.array([3.0, 3.0])), "approx", time_limit_s=10)
    lo = build_and_solve(inst(np.array([0.5, 0.5])), "approx", time_limit_s=10)
    assert lo.objective < hi.objective
    # with 10 h/week and 1 h of production per SKU-week, a 3 h estimate cannot fit both SKUs every week
    assert (hi.qty > 1e-6).sum() <= (lo.qty > 1e-6).sum()


def test_evaluated_cost_matches_hand_sum():
    c = load_costs()
    sw = pd.DataFrame({"produced": [10.0, 5.0], "lost": [1.0, 0.0], "expired": [2.0, 0.0],
                       "end_inventory": [3.0, 4.0]})
    wk = pd.DataFrame({"changeover_hours": [1.5]})
    r = SimResult(sw, wk, 0.0, [])
    want = (c["production_per_case"] * 15 + c["lost_sale_per_case"] * 1 + c["expiry_per_case"] * 2
            + c["holding_per_case_week"] * 7 + c["changeover_per_hour"] * 1.5)
    assert abs(evaluated_cost(r, c) - want) < 1e-9
