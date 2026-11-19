"""Statistical forecasters for the rolling-origin harness (T3.2.1).

Each model is a harness ModelFn: (history Series, horizon) -> np.ndarray. A model is refit at every origin
on history strictly before it (the harness enforces this). Negative forecasts are clipped to 0.
- arima      : statsforecast AutoARIMA, non-seasonal (fast; yearly seasonality is weak here, see EDA)
- arima52    : AutoARIMA with a 52-week season (slow: ~14 s per fit, run in parallel)
- ets        : AutoETS with season_length=52; automatic selection decides whether a seasonal term helps
"""
from __future__ import annotations

import warnings

import numpy as np
import pandas as pd
from statsforecast.models import AutoARIMA, AutoETS


def _fit(model, hist: pd.Series, h: int) -> np.ndarray:
    y = hist.to_numpy(float)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        try:
            f = model.forecast(y=y, h=h)["mean"]
        except Exception:      # rare numerical failure on a window -> fall back to MA(4), counted by caller
            return np.full(h, np.nan)
    return np.clip(np.asarray(f, float), 0, None)


def arima(hist: pd.Series, h: int) -> np.ndarray:
    return _fit(AutoARIMA(season_length=1), hist, h)


def arima52(hist: pd.Series, h: int) -> np.ndarray:
    return _fit(AutoARIMA(season_length=52), hist, h)


def ets(hist: pd.Series, h: int) -> np.ndarray:
    return _fit(AutoETS(season_length=52), hist, h)


MODELS = {"arima": arima, "arima52": arima52, "ets": ets}


def with_fallback(fn, fallback_k: int = 4):
    """Wrap a model so a failed fit (NaN) falls back to the k-week moving average; failures are recorded."""
    def wrapped(hist: pd.Series, h: int) -> np.ndarray:
        f = fn(hist, h)
        if np.isnan(f).any():
            wrapped.failures += 1
            return np.repeat(hist.iloc[-fallback_k:].mean(), h)
        return f
    wrapped.failures = 0
    return wrapped
