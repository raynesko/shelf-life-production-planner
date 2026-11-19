"""T3.1.1: naive benchmarks through the rolling-origin harness on the real panel.

Outputs: results/forecast/benchmark_forecasts.parquet, results/forecast/benchmark_metrics.csv
Run: python scripts/run_benchmarks.py
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from shelflife.forecast import backtest as B

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "forecast"


def main() -> None:
    panel = pd.read_parquet(ROOT / "data" / "processed" / "demand_weekly.parquet")
    win = B.make_windows(panel.week_start)
    fc = pd.concat([B.run_backtest(panel, f, name, win) for name, f in B.BENCHMARKS.items()], ignore_index=True)
    OUT.mkdir(parents=True, exist_ok=True)
    fc.to_parquet(OUT / "benchmark_forecasts.parquet", index=False)
    scales = B.mase_scales(panel, win.val_start)
    m = B.metrics(fc, scales)
    m.to_csv(OUT / "benchmark_metrics.csv", index=False)
    agg = m[m.sku_id == "ALL"].pivot(index="model", columns="window", values=["wape", "bias", "mase"]).round(2)
    print(agg.to_string())
    print(f"rows: {len(fc)}; wrote {OUT.relative_to(ROOT)}/benchmark_*")


if __name__ == "__main__":
    main()
