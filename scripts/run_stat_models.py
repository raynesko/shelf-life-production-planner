"""T3.2.1 (and T3.2.2): fit statistical models through the rolling-origin harness, one SKU per process.

Run: python scripts/run_stat_models.py --models arima ets [arima52] [prophet] [--workers 14]
     [--skus SKU-02 SKU-08] [--chunks 8]   (subset of SKUs; split each SKU's origins into parallel chunks)
Outputs: results/forecast/<model>_forecasts.parquet, results/forecast/model_metrics.csv (benchmarks + all
models found on disk), results/logs/forecast_runtime.txt (appended).
"""
from __future__ import annotations

import argparse
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd

from shelflife.forecast import backtest as B

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "forecast"
PANEL = ROOT / "data" / "processed" / "demand_weekly.parquet"


def get_model(name: str):
    if name in ("prophet", "prophet_hol"):
        from shelflife.forecast import prophet_model
        return getattr(prophet_model, name)
    from shelflife.forecast.arima_ets import MODELS
    return MODELS[name]


def one_sku(args: tuple) -> tuple[pd.DataFrame, int, float]:
    from shelflife.forecast.arima_ets import with_fallback
    model, sku, origins = args if len(args) == 3 else (*args, None)
    panel = pd.read_parquet(PANEL)
    win = B.make_windows(panel.week_start)
    fn = with_fallback(get_model(model))
    t0 = time.perf_counter()
    fc = B.run_backtest(panel[panel.sku_id == sku], fn, model, win, origins=origins)
    return fc, fn.failures, time.perf_counter() - t0


def tasks_for(model: str, skus: list[str], chunks: int) -> list[tuple]:
    if chunks <= 1:
        return [(model, s) for s in skus]
    panel = pd.read_parquet(PANEL)
    win = B.make_windows(panel.week_start)
    weeks = pd.DatetimeIndex(sorted(panel.week_start.unique()))
    origins = weeks[(weeks >= win.val_start) & (weeks <= win.test_end)]
    parts = [set(c) for c in np.array_split(origins, chunks)]
    return [(model, s, part) for s in skus for part in parts]


def combined_metrics() -> pd.DataFrame:
    panel = pd.read_parquet(PANEL)
    win = B.make_windows(panel.week_start)
    files = [OUT / "benchmark_forecasts.parquet"] + sorted(OUT.glob("*_forecasts.parquet"))
    fc = pd.concat([pd.read_parquet(f) for f in dict.fromkeys(files) if f.exists()], ignore_index=True)
    m = B.metrics(fc, B.mase_scales(panel, win.val_start))
    m.to_csv(OUT / "model_metrics.csv", index=False)
    return m


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", nargs="+", default=["arima", "ets"])
    ap.add_argument("--workers", type=int, default=14)
    ap.add_argument("--skus", nargs="*")
    ap.add_argument("--chunks", type=int, default=1)
    a = ap.parse_args()
    skus = a.skus or sorted(pd.read_parquet(PANEL).sku_id.unique())
    log = ROOT / "results" / "logs" / "forecast_runtime.txt"
    for model in a.models:
        t0 = time.perf_counter()
        with ProcessPoolExecutor(max_workers=a.workers) as ex:
            res = list(ex.map(one_sku, tasks_for(model, skus, a.chunks)))
        fc = pd.concat([r[0] for r in res], ignore_index=True).sort_values(
            ["sku_id", "window", "origin", "horizon"]).reset_index(drop=True)
        assert fc.yhat.notna().all() and (fc.yhat >= 0).all(), f"{model}: forecasts must be finite and >= 0"
        dest = OUT / f"{model}_forecasts.parquet"
        if a.skus and dest.exists():      # subset run: replace only these SKUs, keep the rest of the file
            old = pd.read_parquet(dest)
            fc = pd.concat([old[~old.sku_id.isin(skus)], fc], ignore_index=True).sort_values(
                ["sku_id", "window", "origin", "horizon"]).reset_index(drop=True)
        fc.to_parquet(dest, index=False)
        fails, wall = sum(r[1] for r in res), time.perf_counter() - t0
        cpu = sum(r[2] for r in res)
        line = (f"{time.strftime('%Y-%m-%d %H:%M')} model={model} rows={len(fc)} fits={len(fc.drop_duplicates(['sku_id', 'origin']))} "
                f"failed_fits_fallback_ma4={fails} wall_s={wall:.1f} cpu_s={cpu:.1f} workers={a.workers}")
        with log.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
        print(line, flush=True)
    m = combined_metrics()
    agg = m[m.sku_id == "ALL"].pivot(index="model", columns="window", values=["wape", "bias", "mase"]).round(2)
    print(agg.to_string())


if __name__ == "__main__":
    main()
