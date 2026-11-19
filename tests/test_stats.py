"""T5.1.2: the paired bootstrap covers a known true effect, and its bookkeeping is right."""
import numpy as np
import pandas as pd

from shelflife.analysis.stats import bootstrap, n_for_half_width, summarise_experiment


def test_bootstrap_ci_covers_known_reduction_in_at_least_90pct_of_trials():
    rng = np.random.default_rng(42)
    true_reduction = 30.0                 # E[new] = 0.7 E[base]
    hits = 0
    for trial in range(100):
        base = rng.gamma(4.0, 2500.0, 200)                       # mean 10,000
        new = 0.7 * base * rng.lognormal(-0.02, 0.2, 200)        # E[lognormal(-0.02, 0.2)] = 1
        r = bootstrap(base, new, "reduction_pct", n_boot=2000, seed=trial)
        hits += r["ci_lo"] <= true_reduction <= r["ci_hi"]
    assert hits >= 90, hits


def test_delta_pts_and_pairing():
    base = np.array([0.95, 0.96, 0.97, 0.98])
    new = base + 0.01
    r = bootstrap(base, new, "delta_pts", n_boot=500)
    assert abs(r["estimate"] - 1.0) < 1e-9 and abs(r["ci_lo"] - 1.0) < 1e-9  # constant shift: zero width


def test_summarise_uses_mc_rows_only_and_pairs_by_path():
    rows = []
    for i in range(5):
        for arm, f in (("B1", 1.0), ("OPT", 0.5)):
            rows.append({"layer": "mc", "path_id": i, "arm": arm, "expired_cases": 100 * f * (i + 1),
                         "lost_cases": 10.0 * (i + 1), "fill_rate": 0.99, "changeover_hours": 1000 * f,
                         "allergen_clean_hours": 800 * f, "evaluated_cost": 1e6 * f})
    rows.append({"layer": "replay", "path_id": 0, "arm": "OPT", "expired_cases": 1e9})
    s = summarise_experiment(pd.DataFrame(rows), n_boot=200).set_index("metric")
    assert abs(s.loc["expired_waste_reduction_pct", "estimate"] - 50) < 1e-9
    assert abs(s.loc["lost_cases_reduction_pct", "estimate"]) < 1e-9
    assert s.loc["expired_waste_reduction_pct", "n"] == 5


def test_n_for_half_width():
    assert n_for_half_width(6.0, 30, 3.0) == 120
