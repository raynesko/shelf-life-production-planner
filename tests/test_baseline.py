import numpy as np
import pytest

from shelflife.plant.changeover import build_matrix
from shelflife.plant.config import load
from shelflife.sim import kpis
from shelflife.sim.baseline import BaselineB1, allergen_ladder
from shelflife.sim.engine import SimPlant, simulate_policy


@pytest.fixture(scope="module")
def setup():
    cfg = load()
    plant = SimPlant.from_config(cfg, build_matrix(cfg))
    return cfg, plant, BaselineB1.from_config(cfg, plant)


def test_ladder_fewest_allergens_first(setup):
    cfg, _, _ = setup
    counts = [len(cfg.skus[i].allergens) for i in allergen_ladder(cfg)]
    assert counts == sorted(counts)
    assert len(set(allergen_ladder(cfg))) == len(cfg.skus)


def test_zero_demand_zero_production(setup):
    _, plant, b1 = setup
    r, plans = simulate_policy(plant, b1, np.zeros((plant.n, 10)), np.zeros((plant.n, 4)))
    assert r.sku_week["produced"].sum() == 0
    assert all(len(w) == 0 for w in plans)


def test_policy_sees_no_future_demand(setup):
    _, plant, b1 = setup
    seen = []

    def spy(state, observed):
        seen.append(observed.shape[1])
        return b1(state, observed)

    simulate_policy(plant, spy, np.full((plant.n, 6), 500.0), np.full((plant.n, 4), 500.0))
    assert seen == [4, 5, 6, 7, 8, 9]


def test_capacity_feasible_under_heavy_demand(setup):
    _, plant, b1 = setup
    rng = np.random.default_rng(7)
    demand = rng.gamma(2.0, 2500.0, size=(plant.n, 52))     # far above line capacity
    r, _ = simulate_policy(plant, b1, demand, demand[:, :4])
    assert not r.week["capacity_breach"].any()
    assert (r.week["utilisation"] <= 1 + 1e-9).all()


def test_min_and_max_run_respected(setup):
    _, plant, b1 = setup
    rng = np.random.default_rng(11)
    demand = rng.gamma(1.5, 300.0, size=(plant.n, 30))
    _, plans = simulate_policy(plant, b1, demand, demand[:, :4])
    for wp in plans:
        for p, q in wp:
            assert q + 1e-6 >= b1.min_run_cases[p]
            assert q <= b1.max_run_cases[p] + 1e-6


def test_steady_demand_serves_well_and_wastes_little(setup):
    # Sanity: constant demand, moderate load -> high fill rate. Not a calibration claim.
    _, plant, b1 = setup
    demand = np.full((plant.n, 30), 600.0)
    r, _ = simulate_policy(plant, b1, demand, demand[:, :4])
    s = kpis.summarise(r)
    assert s["fill_rate"] > 0.95
    assert s["capacity_breach_weeks"] == 0


def test_sequence_follows_ladder(setup):
    cfg, plant, b1 = setup
    demand = np.full((plant.n, 3), 800.0)
    _, plans = simulate_policy(plant, b1, demand, demand)
    pos = {p: k for k, p in enumerate(allergen_ladder(cfg))}
    for wp in plans:
        order = [pos[p] for p, _ in wp]
        assert order == sorted(order)


def test_reorder_point_gives_two_week_cycle(setup):
    """ADR-006: steady demand, capacity not binding -> each SKU runs every other week, not every week."""
    _, plant, b1 = setup
    demand = np.full((plant.n, 20), 300.0)    # 2 weeks of all SKUs ~ 24 run h + 29.5 h changeover < 72 h
    r, plans = simulate_policy(plant, b1, demand, demand[:, :4])
    assert not r.week["capacity_breach"].any()
    runs = np.zeros(plant.n)
    for wp in plans[4:]:                      # skip start-up
        for p, _ in wp:
            runs[p] += 1
    assert np.all(runs == 8)                  # 16 weeks -> exactly every other week


def test_capacity_repair_defers_most_covered_sku_not_all(setup):
    """ADR-010: when over capacity, B1 defers the SKUs that can wait (highest cover) and keeps the urgent ones;
    it never zeroes every run while a smaller set would fit (the old pro-rata death spiral)."""
    cfg, plant, b1 = setup
    q = b1.max_run_cases.copy()                       # every SKU at max run: far above 72 h
    cover = np.arange(plant.n, dtype=float)           # SKU index = weeks of cover
    out = b1.fit_capacity(q, None, cover)
    kept = np.flatnonzero(out > 0)
    assert len(kept) > 0
    assert set(kept) == set(range(len(kept))), "least-covered SKUs must be the ones kept"
    assert np.all(out[kept] + 1e-9 >= b1.min_run_cases[kept])
    order = [p for p in b1.ladder if out[p] > 0]
    from shelflife.sim.baseline import sequence_hours
    assert float(np.sum(out / plant.rate)) + sequence_hours(plant, order, None) <= plant.available_hours + 1e-6


def test_long_changeovers_do_not_starve_the_line(setup):
    """Doubled changeover times: B1 must keep producing (pre-ADR-010 it fell to ~8% fill rate)."""
    import dataclasses
    cfg, plant, _ = setup
    slow = dataclasses.replace(plant, changeover_hours=plant.changeover_hours * 2)
    b1 = BaselineB1.from_config(cfg, slow)
    demand = np.full((plant.n, 30), 0.2 * plant.available_hours * plant.rate.mean() / plant.n)
    r, _ = simulate_policy(slow, b1, demand, demand[:, :4])
    assert kpis.summarise(r)["fill_rate"] > 0.95
