"""T4.3.2: rolling-horizon driver on a short synthetic run with the real plant."""
import numpy as np
import pandas as pd
import pytest

from shelflife.checks.plan_checker import check
from shelflife.opt.model import load_costs
from shelflife.opt.rolling import OptimisedPolicy, forecast_cube, run_arm
from shelflife.plant.changeover import build_matrix
from shelflife.plant.config import load
from shelflife.sim.baseline import BaselineB1
from shelflife.sim.engine import SimPlant, plan_to_frame


def test_forecast_cube_fills_tail_and_rejects_missing_h1():
    weeks = pd.date_range("2016-01-04", periods=3, freq="W-MON")
    rows = [("A", w, h, 100.0 + h) for w in weeks for h in (1, 2) ] + [("A", weeks[0], 3, 103.0)]
    fc = pd.DataFrame(rows, columns=["sku_id", "origin", "horizon", "yhat"])
    cube = forecast_cube(fc, ["A"], weeks, H=4, scale=2.0)
    assert cube.shape == (1, 3, 4)
    assert cube[0, 0].tolist() == [202, 204, 206, 206]       # h4 filled from h3
    assert cube[0, 1].tolist() == [202, 204, 204, 204]
    with pytest.raises(ValueError):
        forecast_cube(fc[~((fc.origin == weeks[2]) & (fc.horizon == 1))], ["A"], weeks)


@pytest.fixture(scope="module")
def short_run():
    cfg = load()
    plant = SimPlant.from_config(cfg, build_matrix(cfg))
    rng = np.random.default_rng(3)
    T, H = 4, 13
    mean = rng.uniform(500, 1200, plant.n)
    demand = np.rint(mean[:, None] * rng.lognormal(0, 0.1, (plant.n, T)))
    cube = np.repeat(mean[:, None, None], T, axis=1).repeat(H, axis=2)
    d = cfg.sku_defaults
    b1 = BaselineB1.from_config(cfg, plant)
    pol = OptimisedPolicy(plant, cube, np.full((plant.n, H), 0.1 * mean[:, None].repeat(H, 1)[:, 0:1].mean()),
                          plant.rate * d.min_run_hours.value, plant.rate * d.max_run_hours.value, load_costs(),
                          time_limit_s=10, fallback=b1)
    start = [{1: float(m)} for m in mean]
    r, plans = run_arm(plant, pol, demand, np.repeat(mean[:, None], 4, axis=1), start, 0)
    return cfg, plant, pol, r, plans


def test_rolling_logs_every_week_and_no_fallback(short_run):
    _, _, pol, r, plans = short_run
    assert [x["week"] for x in pol.log] == [0, 1, 2, 3]
    assert not any(x["fallback_used"] for x in pol.log)
    assert len(r.week) == 4 and len(plans) == 4


def test_rolling_plans_pass_independent_checker(short_run):
    cfg, plant, _, r, plans = short_run
    plan = plan_to_frame(plans, plant, 0)
    assert check(plan, cfg, initial_last_sku=plant.sku_ids[0], shipments=r.shipments) == []
    assert not r.week.capacity_breach.any()


def test_solver_noise_runs_are_dropped():
    """A near-zero quantity from the MIP (inside solver tolerance) must not become a 0-hour run."""
    import numpy as np

    from shelflife.opt.rolling import sequence_and_repair
    from shelflife.plant.changeover import build_matrix
    from shelflife.plant.config import load
    from shelflife.sim.engine import SimPlant
    cfg = load()
    plant = SimPlant.from_config(cfg, build_matrix(cfg))
    min_run = plant.rate * cfg.sku_defaults.min_run_hours.value
    q = np.zeros(plant.n)
    q[0], q[1], q[2] = 1e-3, min_run[1] * (1 - 1e-7), 2 * min_run[2]
    wp, _ = sequence_and_repair(q, plant, None, min_run)
    got = dict(wp)
    assert 0 not in got
    assert got[1] >= min_run[1] and got[2] == 2 * min_run[2]
