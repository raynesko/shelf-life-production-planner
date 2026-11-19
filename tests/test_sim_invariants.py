import json
import time
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from shelflife.plant.changeover import build_matrix
from shelflife.plant.config import load
from shelflife.sim import kpis
from shelflife.sim.engine import SimPlant, plan_from_frame, simulate

FIX = json.loads((Path(__file__).parent / "fixtures" / "handcalc.json").read_text())


def hand_plant():
    p = FIX["plant"]
    return SimPlant(p["sku_ids"], np.array(p["shelf_life_days"], float), np.array(p["rate"], float),
                    p["available_hours"], p["msl"], np.array(p["changeover_hours"]),
                    np.array(p["allergen_clean"]))


def hand_result():
    plan = [[tuple(x) for x in w] for w in FIX["plan"]]
    return simulate(hand_plant(), plan, np.array(FIX["demand"]))


def test_handcalc_matches():
    exp = FIX["expected"]
    plant, r = hand_plant(), hand_result()
    assert plant.max_ship_age.tolist() == exp["max_ship_age"]
    tot = r.sku_week.groupby("sku_id")[["produced", "shipped", "lost", "expired"]].sum()
    for sku, vals in exp["per_sku"].items():
        for k, v in vals.items():
            assert tot.loc[sku, k] == pytest.approx(v), (sku, k)
    for sku, series in exp["end_inventory"].items():
        got = r.sku_week[r.sku_week.sku_id == sku]["end_inventory"].tolist()
        assert got == pytest.approx(series), sku
    for col, series in exp["week"].items():
        assert r.week[col].tolist() == pytest.approx(series), col
    s = kpis.summarise(r)
    for k, v in exp["kpis"].items():
        assert s[k] == pytest.approx(v, rel=1e-6), k


@pytest.fixture(scope="module")
def real_plant():
    cfg = load()
    return SimPlant.from_config(cfg, build_matrix(cfg))


def random_case(plant, rng, n_weeks=12):
    n = plant.n
    demand = rng.gamma(2.0, 400.0, size=(n, n_weeks)) * (rng.random((n, n_weeks)) > 0.1)
    plan = []
    for _ in range(n_weeks):
        k = rng.integers(0, n + 1)
        skus = rng.choice(n, size=k, replace=True)
        plan.append([(int(p), float(rng.integers(0, 3000))) for p in skus])
    init = [{int(a): float(rng.integers(0, 500)) for a in rng.choice(6, size=2)} for _ in range(n)]
    return plan, demand, init


def test_conservation_1000_random_plans(real_plant):
    rng = np.random.default_rng(42)
    for _ in range(1000):
        plan, demand, init = random_case(real_plant, rng)
        r = simulate(real_plant, plan, demand, initial_inventory=init,
                     initial_last_sku=int(rng.integers(0, real_plant.n)))
        sw = r.sku_week
        ending = sum(sum(c.values()) for c in r.ending_cohorts)
        lhs = r.initial_inventory + sw["produced"].sum()
        rhs = sw["shipped"].sum() + sw["expired"].sum() + ending
        assert lhs == pytest.approx(rhs, abs=1e-6)
        assert (sw["shipped"] <= sw["demand"] + 1e-9).all()
        assert (sw[["shipped", "lost", "expired", "end_inventory"]] >= -1e-9).all().all()


def test_never_ships_past_msl(real_plant):
    # 1 production run, then demand only far later: nothing may ship after max ship age.
    n, A = real_plant.n, real_plant.max_ship_age
    plan = [[(p, 1000.0) for p in range(n)]] + [[] for _ in range(9)]
    demand = np.zeros((n, 10))
    demand[:, -1] = 500
    r = simulate(real_plant, plan, demand)
    for p in range(n):
        shipped_last = r.sku_week[(r.sku_week.sku_id == real_plant.sku_ids[p]) & (r.sku_week.week == 9)]
        assert shipped_last["shipped"].item() == (500 if A[p] >= 9 else 0)
        assert r.sku_week[r.sku_week.sku_id == real_plant.sku_ids[p]]["expired"].sum() == \
            pytest.approx(0 if A[p] >= 9 else 1000)


def test_deterministic(real_plant):
    rng = np.random.default_rng(1)
    plan, demand, init = random_case(real_plant, rng)
    a = simulate(real_plant, plan, demand, initial_inventory=init)
    b = simulate(real_plant, plan, demand, initial_inventory=init)
    pd.testing.assert_frame_equal(a.sku_week, b.sku_week)
    pd.testing.assert_frame_equal(a.week, b.week)


def test_kpi_names_match_spec():
    spec = (Path(__file__).parents[1] / "docs" / "research" / "kpi_definitions.md").read_text()
    for k in kpis.summarise(hand_result()):
        if k == "capacity_breach_weeks":
            continue  # simulator-only flag, not a reported KPI
        assert f"`{k}`" in spec, k


def test_capacity_breach_flag():
    plant = hand_plant()
    r = simulate(plant, [[(0, 2000)]], np.zeros((3, 1)))   # 20 h > 10 h available
    assert bool(r.week["capacity_breach"].iloc[0])


def test_plan_from_frame_roundtrip():
    df = pd.DataFrame({"week": [0, 0, 1], "position": [1, 0, 0], "sku_id": ["B", "A", "C"],
                       "qty": [5.0, 7.0, 9.0]})
    assert plan_from_frame(df, ["A", "B", "C"], 2) == [[(0, 7.0), (1, 5.0)], [(2, 9.0)]]


def test_speed_52x12(real_plant):
    rng = np.random.default_rng(3)
    plan, demand, _ = random_case(real_plant, rng, n_weeks=52)
    t0 = time.perf_counter()
    simulate(real_plant, plan, demand)
    assert time.perf_counter() - t0 < 5
