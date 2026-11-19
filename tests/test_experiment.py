"""T5.1.1: paired (common-random-number) structure and reproducibility of the experiment runner.

Uses the fast arms (B1, B1_SELFC) so the test runs in seconds; the optimiser arms go through the same code path
(`experiment.run_one`) and are covered by test_rolling.py.
"""
import importlib.util
from pathlib import Path

import numpy as np
import pytest

from shelflife.analysis import experiment as X

ROOT = Path(__file__).resolve().parents[1]
NEEDED = [ROOT / "data" / "processed" / "demand_weekly.parquet",
          ROOT / "results" / "forecast" / "forecasts_test.parquet",
          ROOT / "results" / "forecast" / "forecasts_validation.parquet"]
pytestmark = pytest.mark.skipif(not all(p.exists() for p in NEEDED), reason="panel/forecasts not built")


def runner():
    spec = importlib.util.spec_from_file_location("run_experiment", ROOT / "scripts" / "run_experiment.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


CFG = {"name": "t", "arms": ["B1", "B1_SELFC"], "replay": True, "monte_carlo": {"n_paths": 3, "seed": 11},
       "workers": 1, "overrides": {}}


def test_paths_are_common_and_seeded():
    ctx = X.build_context()
    a, b = X.scenario_paths(ctx, 4, 7), X.scenario_paths(ctx, 4, 7)
    assert a.shape == (4, ctx.plant.n, 52) and np.array_equal(a, b) and (a >= 0).all()
    assert not np.array_equal(a, X.scenario_paths(ctx, 4, 8))


def test_arms_are_paired_and_rerun_is_identical(tmp_path):
    rx = runner()
    out1, df1 = rx.run(CFG, tmp_path / "a")
    out2, df2 = rx.run(CFG, tmp_path / "b")
    mc = df1[df1.layer == "mc"]
    keys = {arm: set(zip(g.path_id, g.seed, strict=True)) for arm, g in mc.groupby("arm")}
    assert keys["B1"] == keys["B1_SELFC"] == {(i, 11) for i in range(3)}
    # paired: on each path both arms face the same total demand
    dem = mc.pivot(index="path_id", columns="arm", values="demand_cases")
    assert np.allclose(dem["B1"], dem["B1_SELFC"])
    assert X.kpi_hash(df1) == X.kpi_hash(df2)
    for f in ("kpis.parquet", "config.yaml", "meta.json"):
        assert (out1 / f).exists()
    assert (df1.checker_violations == 0).all()


def test_replay_b1_matches_baseline_replay():
    import pandas as pd
    ref = pd.read_csv(ROOT / "results" / "baseline_replay.csv").iloc[0]
    row = X.run_one(X.build_context(), "B1", X.build_context().actual)
    assert abs(row["expired_cases"] - ref.expired_cases) < 1e-3 and abs(row["fill_rate"] - ref.fill_rate) < 1e-4
