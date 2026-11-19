"""T4.3.3: independence, mutation tests, and baseline/optimised plans pass."""
import ast
from pathlib import Path

import numpy as np
import pytest

from shelflife.checks import plan_checker as PC
from shelflife.opt.model import Instance, build_and_solve, load_costs
from shelflife.plant.changeover import build_matrix
from shelflife.plant.config import load
from shelflife.sim.baseline import BaselineB1
from shelflife.sim.engine import SimPlant, plan_to_frame, simulate, simulate_policy

SRC = Path(PC.__file__)


@pytest.fixture(scope="module")
def env():
    cfg = load()
    plant = SimPlant.from_config(cfg, build_matrix(cfg))
    rng = np.random.default_rng(5)
    demand = np.rint(rng.uniform(200, 1400, (12, 8)))
    return cfg, plant, demand


@pytest.fixture(scope="module")
def baseline_plan(env):
    cfg, plant, demand = env
    r, plans = simulate_policy(plant, BaselineB1.from_config(cfg, plant), demand, demand[:, :4],
                               initial_last_sku=0)
    return plan_to_frame(plans, plant, 0), r


@pytest.fixture(scope="module")
def optimised_plan(env):
    cfg, plant, demand = env
    d = cfg.sku_defaults
    inst = Instance(plant, demand, plant.rate * d.min_run_hours.value, plant.rate * d.max_run_hours.value,
                    load_costs(), initial_last_sku=0)
    sol = build_and_solve(inst, "arc", "SCIP", 6)
    assert sol.feasible
    r = simulate(plant, sol.week_plans(), demand, initial_last_sku=0)
    return plan_to_frame(sol.week_plans(), plant, 0), r


def test_checker_does_not_import_optimiser_or_simulator():
    tree = ast.parse(SRC.read_text(encoding="utf-8"))
    mods = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            mods.add(node.module)
        elif isinstance(node, ast.Import):
            mods.update(a.name for a in node.names)
    banned = [m for m in mods if m.startswith(("shelflife.opt", "shelflife.sim", "shelflife.plant.changeover"))]
    assert not banned, banned


def test_baseline_plan_passes(env, baseline_plan):
    cfg, _, _ = env
    plan, r = baseline_plan
    assert PC.check(plan, cfg, initial_last_sku="SKU-01", shipments=r.shipments) == []


def test_optimised_plan_passes(env, optimised_plan):
    cfg, _, _ = env
    plan, r = optimised_plan
    assert len(plan) > 0
    assert PC.check(plan, cfg, initial_last_sku="SKU-01", shipments=r.shipments) == []


def rules(v):
    return {x.rule for x in v}


def test_mutation_over_capacity(env, optimised_plan):
    cfg, _, _ = env
    plan = optimised_plan[0].copy()
    i = plan.index[0]
    plan.loc[i, "qty"] = plan.loc[i, "qty"] + 30_000
    v = PC.check(plan, cfg, initial_last_sku="SKU-01")
    assert "capacity" in rules(v)


def test_mutation_below_min_run(env, optimised_plan):
    cfg, _, _ = env
    plan = optimised_plan[0].copy()
    plan.loc[plan.index[0], "qty"] = 10.0
    assert "min_run" in rules(PC.check(plan, cfg, initial_last_sku="SKU-01"))


def test_mutation_wrong_changeover_accounting(env, optimised_plan):
    cfg, _, _ = env
    plan = optimised_plan[0].copy()
    i = plan.index[plan.changeover_hours_before > 0][0]
    plan.loc[i, "changeover_hours_before"] = 0.1
    v = PC.check(plan, cfg, initial_last_sku="SKU-01")
    assert "changeover_accounting" in rules(v)


def test_mutation_missing_allergen_clean(env, optimised_plan):
    cfg, _, _ = env
    plan = optimised_plan[0].copy()
    allergen_rows = plan.index[plan.clean_type == "allergen"]
    assert len(allergen_rows), "fixture should contain an allergen clean"
    i = allergen_rows[0]
    plan.loc[i, ["clean_type", "changeover_hours_before"]] = ["routine", 1.0]
    v = PC.check(plan, cfg, initial_last_sku="SKU-01")
    assert "missing_allergen_clean" in rules(v)
    assert any("requires 'allergen'" in x.message for x in v)


def test_mutation_expired_shipment(env, baseline_plan):
    cfg, _, _ = env
    plan, r = baseline_plan
    ships = r.shipments.copy()
    ships.loc[ships.index[0], "age"] = 9          # 63 days: past every SKU's shippable age
    v = PC.check(plan, cfg, initial_last_sku="SKU-01", shipments=ships)
    assert "shelf_life_at_ship" in rules(v)


def test_cli_pass_and_fail(tmp_path, env, optimised_plan, capsys):
    plan = optimised_plan[0]
    ok = tmp_path / "ok.csv"
    plan.to_csv(ok, index=False)
    assert PC.main([str(ok), "--last", "SKU-01"]) == 0
    assert "PASS" in capsys.readouterr().out
    bad = plan.copy()
    bad.loc[bad.index[0], "qty"] = 10.0
    badp = tmp_path / "bad.csv"
    bad.to_csv(badp, index=False)
    assert PC.main([str(badp), "--last", "SKU-01"]) == 1
    assert "FAIL" in capsys.readouterr().out
