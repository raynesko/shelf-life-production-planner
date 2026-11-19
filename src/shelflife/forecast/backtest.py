"""Rolling-origin backtest harness, naive benchmarks and metrics (T3.1.1).

Definitions
- origin: the first week being forecast. A model sees only history with week_start < origin.
- horizon h = 1..H: target_week = origin + 7 * (h - 1) days.
- windows: the last `test_weeks` weeks are TEST (reporting only); the `val_weeks` before them are
  VALIDATION (model selection, error calibration); everything earlier is train-only.
  Each window has one origin per week. Rows whose target falls outside the origin's window are
  dropped, so validation metrics never touch test-year actuals.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import numpy as np
import pandas as pd

SCHEMA = ["sku_id", "origin", "horizon", "target_week", "y", "yhat", "model", "window"]
# A model gets one SKU's history (Series indexed by week_start, ascending) and returns H forecasts.
ModelFn = Callable[[pd.Series, int], np.ndarray]


@dataclass(frozen=True)
class Windows:
    val_start: pd.Timestamp
    val_end: pd.Timestamp
    test_start: pd.Timestamp
    test_end: pd.Timestamp

    def bounds(self, name: str) -> tuple[pd.Timestamp, pd.Timestamp]:
        return (self.val_start, self.val_end) if name == "validation" else (self.test_start, self.test_end)

    def to_dict(self) -> dict[str, str]:
        return {k: str(v.date()) for k, v in self.__dict__.items()}


def make_windows(weeks: pd.DatetimeIndex | pd.Series, test_weeks: int = 52, val_weeks: int = 52,
                 min_train_weeks: int = 104) -> Windows:
    w = pd.DatetimeIndex(sorted(pd.unique(pd.DatetimeIndex(weeks))))
    if len(w) < min_train_weeks + val_weeks + test_weeks:
        raise ValueError(f"need >= {min_train_weeks + val_weeks + test_weeks} weeks, have {len(w)}")
    if not (w.to_series().diff().dropna() == np.timedelta64(7, "D")).all():
        raise ValueError("weeks must be contiguous weekly dates")
    return Windows(w[-test_weeks - val_weeks], w[-test_weeks - 1], w[-test_weeks], w[-1])


def run_backtest(panel: pd.DataFrame, model: ModelFn, model_name: str, windows: Windows,
                 horizon: int = 13, which: tuple[str, ...] = ("validation", "test"),
                 origins: set[pd.Timestamp] | None = None) -> pd.DataFrame:
    """panel: long frame with sku_id, week_start, units (contiguous weeks per SKU).
    origins: optional subset of origins to run (for parallel chunks); window truncation is unchanged."""
    out = []
    for sku, g in panel.sort_values("week_start").groupby("sku_id", sort=True):
        y = g.set_index("week_start")["units"].astype(float)
        for win in which:
            lo, hi = windows.bounds(win)
            for origin in y.index[(y.index >= lo) & (y.index <= hi)]:
                if origins is not None and origin not in origins:
                    continue
                hist = y[y.index < origin]
                yhat = np.asarray(model(hist, horizon), float)
                if yhat.shape != (horizon,):
                    raise ValueError(f"{model_name} returned shape {yhat.shape}, expected ({horizon},)")
                for h in range(1, horizon + 1):
                    tw = origin + np.timedelta64(7 * (h - 1), "D")
                    if tw > hi or tw not in y.index:
                        continue
                    out.append((sku, origin, h, tw, y[tw], max(yhat[h - 1], 0.0), model_name, win))
    return pd.DataFrame(out, columns=SCHEMA)


# ---------------------------------------------------------------- benchmarks
def naive(hist: pd.Series, h: int) -> np.ndarray:
    return np.repeat(hist.iloc[-1], h)


def seasonal_naive(hist: pd.Series, h: int, m: int = 52) -> np.ndarray:
    if len(hist) < m:
        return naive(hist, h)
    last = hist.iloc[-m:].to_numpy()
    return np.array([last[i % m] for i in range(h)])


def moving_average(hist: pd.Series, h: int, k: int = 4) -> np.ndarray:
    return np.repeat(hist.iloc[-k:].mean(), h)


BENCHMARKS: dict[str, ModelFn] = {"naive": naive, "seasonal_naive": seasonal_naive,
                                  "ma4": moving_average}


# ---------------------------------------------------------------- metrics
def wape(y: np.ndarray, yhat: np.ndarray) -> float:
    s = np.sum(np.abs(y))
    return float(100 * np.sum(np.abs(np.asarray(y) - yhat)) / s) if s > 0 else float("nan")


def bias(y: np.ndarray, yhat: np.ndarray) -> float:
    s = np.sum(y)
    return float(100 * np.sum(np.asarray(yhat) - y) / s) if s > 0 else float("nan")


def mase_scales(panel: pd.DataFrame, before: pd.Timestamp, m: int = 52) -> pd.Series:
    """Per-SKU in-sample seasonal-naive MAE using only weeks < `before` (m=1 if too short)."""
    out = {}
    for sku, g in panel[panel.week_start < before].sort_values("week_start").groupby("sku_id"):
        y = g["units"].to_numpy(float)
        lag = m if len(y) > 2 * m else 1
        out[sku] = np.mean(np.abs(y[lag:] - y[:-lag]))
    return pd.Series(out, name="mase_scale")


def metrics(fc: pd.DataFrame, scales: pd.Series) -> pd.DataFrame:
    """Per SKU and aggregate ('ALL') WAPE, bias and MASE by model and window."""
    rows = []
    for (model, win), g in fc.groupby(["model", "window"]):
        for sku, gs in list(g.groupby("sku_id")) + [("ALL", g)]:
            err = np.abs(gs.y - gs.yhat)
            if sku == "ALL":
                m = float(np.mean(err / gs.sku_id.map(scales)))
            else:
                m = float(err.mean() / scales[sku])
            rows.append((model, win, sku, wape(gs.y, gs.yhat), bias(gs.y, gs.yhat), m, len(gs)))
    return pd.DataFrame(rows, columns=["model", "window", "sku_id", "wape", "bias", "mase", "n"])
