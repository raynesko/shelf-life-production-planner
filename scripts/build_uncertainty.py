"""T3.3.1: error sigma table, interval coverage on the test year, scenario sanity plot.

Needs: results/forecast/forecasts_validation.parquet and forecasts_test.parquet (scripts/select_forecasts.py)
Outputs: results/forecast/error_sigma.csv, results/forecast/interval_coverage.csv,
         results/figures/scenario_paths.png
Run: python scripts/build_uncertainty.py
"""
from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from shelflife import viz
from shelflife.forecast.scenarios import ScenarioGenerator, coverage, sigma_table

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "forecast"
PLOT_SKU = "SKU-05"


def main() -> None:
    val = pd.read_parquet(OUT / "forecasts_validation.parquet")
    test = pd.read_parquet(OUT / "forecasts_test.parquet")
    sig = sigma_table(val)
    sig.round(4).to_csv(OUT / "error_sigma.csv", index=False)
    cov = coverage(test, sig)
    cov.round(4).to_csv(OUT / "interval_coverage.csv", index=False)
    print(cov.round(3).to_string(index=False))
    print("rel_sigma (h=1) by SKU:", sig[sig.horizon == 1].set_index("sku_id").rel_sigma.round(3).to_dict())

    g = ScenarioGenerator.from_frames(val, test, sig)
    paths = g.generate(20, seed=2026)
    i = g.sku_ids.index(PLOT_SKU)
    actual = test[(test.sku_id == PLOT_SKU) & (test.horizon == 1)].sort_values("target_week")
    viz.apply_style()
    fig, ax = plt.subplots(figsize=(10, 4))
    for k in range(paths.shape[0]):
        ax.plot(actual.target_week, paths[k, i] / 1000, color=viz.FAMILY_COLOR["DELI"], lw=0.8, alpha=0.35,
                label="20 simulated demand paths" if k == 0 else None)
    ax.plot(actual.target_week, actual.yhat / 1000, color=viz.INK_2, lw=1.4, ls="--", label="one-step forecast")
    ax.plot(actual.target_week, actual.y / 1000, color=viz.INK, lw=1.8, label="actual demand")
    ax.set_ylim(bottom=0)
    ax.set_ylabel("thousand units / week")
    ax.set_title(f"{PLOT_SKU}: demand scenarios vs actuals, test year", loc="left", pad=24)
    ax.legend(loc="lower left", bbox_to_anchor=(0, 1.0), ncols=3)
    viz.source_note(fig, "Scenarios: actual demand + block bootstrap (4 weeks) of standardised validation-year residuals (ADR-008). "
                         "Demand: Corporacion Favorita (Kaggle).")
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(ROOT / "results" / "figures" / "scenario_paths.png", dpi=150)


if __name__ == "__main__":
    main()
