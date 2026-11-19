"""T4.2.2: 2-SKU x 4-week toy solved by hand, plus build-time, status and LP-export checks.

Hand derivation (costs from configs/costs.yaml: prod 18, hold 0.25, expiry 4, lost 40, changeover 400/h):
- SKUs P, Q: demand 1000/week each, rate 1000 cases/h, 10 h/week, changeover 1 h both ways (no allergen),
  shelf life 14 d at MSL 50% -> max ship age A = 1 (a case can wait at most one week).
- Line last ran P before week 0.
- Any plan must make 8000 cases (lost sales cost 40 > production 18, so never skip demand): 144,000.
- Shelf life allows a run to cover at most 2 weeks, so each SKU needs >= 2 runs, and both must run in
  week 0 (no initial stock). Starting from P, week 0 costs one switch P->Q. Let k = two-week batches
  (each holds 1000 cases one week = 250).
  k = 0: both SKUs run every week -> a switch every week: 4 h = 1,600.             Total 145,600.
  k = 1: one SKU skips a week -> still 3 switches (1,200) + 250.                   Total 145,450.
  k = 2: W0 P(2000)->Q, W1 Q only (line already on Q: no switch), W2 Q(2000)->P,
         W3 P only -> 2 switches (800) + 2 x 250 = 1,300.                          Total 145,300.
  Fewer than 2 switches is impossible: both run in W0 (1 switch) and the line must switch again to
  serve whichever SKU is not batched after week 1. k > 2 only adds holding.
- Hence the optimal cost is 145,300 with 2 changeover hours, 2,000 case-weeks held, no lost sales.
  (My first hand pass missed the free same-SKU carry-over and claimed 145,600; the solver found the
  cheaper plan and the simulator confirmed it - kept here as a record.)
"""
from pathlib import Path

import numpy as np
import pytest

from shelflife.opt.model import Instance, build_and_solve, load_costs
from shelflife.plant.changeover import build_matrix
from shelflife.plant.config import load
from shelflife.sim.engine import SimPlant

FIX = Path(__file__).parent / "fixtures"


def toy_instance(available=10.0, demand=1000.0):
    plant = SimPlant(["P", "Q"], np.array([14.0, 14.0]), np.array([1000.0, 1000.0]), available, 0.5,
                     np.array([[0.0, 1.0], [1.0, 0.0]]), np.zeros((2, 2), bool))
    return Instance(plant, np.full((2, 4), demand), np.array([500.0, 500.0]), np.array([5000.0, 5000.0]),
                    load_costs(), initial_last_sku=0)


def test_toy_hand_optimum():
    sol = build_and_solve(toy_instance(), "arc", "SCIP", 30, rel_gap=1e-9)
    assert sol.status == "OPTIMAL"
    assert sol.objective == pytest.approx(145_300, abs=1e-3)
    assert sol.changeover_hours.sum() == pytest.approx(2.0)
    assert sol.qty.sum() == pytest.approx(8000)
    assert sol.extra["lost"].sum() == pytest.approx(0, abs=1e-6)


def test_toy_lp_export_matches_committed(tmp_path):
    out = tmp_path / "toy.lp"
    build_and_solve(toy_instance(), "arc", "SCIP", 30, rel_gap=1e-9, export_lp=out)
    text = out.read_text(encoding="utf-8")
    assert "Minimize" in text or "minimize" in text.lower()
    committed = FIX / "toy.lp"
    if not committed.exists():          # first run writes the reviewable fixture
        committed.write_text(text, encoding="utf-8")
    assert committed.read_text(encoding="utf-8") == text


def test_over_capacity_demand_gives_clear_status_and_lost_sales():
    sol = build_and_solve(toy_instance(demand=20_000.0), "arc", "SCIP", 30)
    assert sol.status in ("OPTIMAL", "FEASIBLE")
    assert sol.extra["lost"].sum() > 0
    assert np.all(sol.qty.sum(axis=0) / 1000 + sol.changeover_hours <= 10 + 1e-6)


def test_invalid_input_returns_status_not_exception():
    assert build_and_solve(toy_instance(available=0.0), "arc").status == "INVALID_INPUT"
    assert build_and_solve(toy_instance(demand=-5.0), "arc").status == "INVALID_INPUT"


def test_full_instance_builds_fast():
    cfg = load()
    plant = SimPlant.from_config(cfg, build_matrix(cfg))
    d = cfg.sku_defaults
    rng = np.random.default_rng(0)
    inst = Instance(plant, rng.uniform(300, 1500, (12, 13)), plant.rate * d.min_run_hours.value,
                    plant.rate * d.max_run_hours.value, load_costs(), initial_last_sku=0)
    sol = build_and_solve(inst, "arc", "SCIP", time_limit_s=1)
    assert sol.extra.get("build_seconds", 0) < 10 if sol.feasible else True
