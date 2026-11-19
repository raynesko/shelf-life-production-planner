"""Prophet forecaster for the rolling-origin harness (T3.2.2).

Weekly data, yearly seasonality only (no weekly/daily terms). Variant `prophet_hol` adds Ecuador NATIONAL
holidays from Favorita's holidays_events.csv (non-transferred; 'Work Day' excluded), each mapped to the
Monday of its week because the series is weekly. Holidays are kept only if they improve VALIDATION WAPE.

Fits are cached on disk (results/forecast/cache/), keyed by variant + horizon + the exact history bytes,
so a re-run with unchanged inputs skips fitting.
"""
from __future__ import annotations

import hashlib
import logging
import warnings
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
CACHE = ROOT / "results" / "forecast" / "cache"
HOLIDAYS_CSV = ROOT / "data" / "raw" / "favorita" / "holidays_events.csv"


@lru_cache(maxsize=1)
def national_holiday_weeks() -> pd.DataFrame:
    h = pd.read_csv(HOLIDAYS_CSV, parse_dates=["date"])
    h = h[(h.locale == "National") & (~h.transferred) & (h.type != "Work Day")]
    wk = h.date - pd.to_timedelta(h.date.dt.dayofweek, unit="D")
    name = h.description.str.replace(r"[^A-Za-z]+", "_", regex=True).str.strip("_").str.lower().str[:30]
    return pd.DataFrame({"holiday": name, "ds": wk}).drop_duplicates().reset_index(drop=True)


def _key(variant: str, hist: pd.Series, h: int) -> str:
    m = hashlib.sha1(variant.encode() + str(h).encode())
    m.update(hist.index.asi8.tobytes())
    m.update(hist.to_numpy(float).tobytes())
    return m.hexdigest()


def _fit(variant: str, hist: pd.Series, h: int) -> np.ndarray:
    CACHE.mkdir(parents=True, exist_ok=True)
    f = CACHE / f"{_key(variant, hist, h)}.npy"
    if f.exists():
        return np.load(f)
    from prophet import Prophet
    logging.getLogger("cmdstanpy").setLevel(logging.ERROR)
    logging.getLogger("prophet").setLevel(logging.ERROR)
    kw = {"yearly_seasonality": True, "weekly_seasonality": False, "daily_seasonality": False}
    if variant == "prophet_hol":
        kw["holidays"] = national_holiday_weeks()
    df = pd.DataFrame({"ds": hist.index, "y": hist.to_numpy(float)})
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        try:
            m = Prophet(**kw).fit(df)
            fut = pd.DataFrame({"ds": hist.index[-1] + pd.to_timedelta(7 * np.arange(1, h + 1), unit="D")})
            out = np.clip(m.predict(fut)["yhat"].to_numpy(float), 0, None)
        except Exception:
            return np.full(h, np.nan)      # caller falls back to MA(4) and counts it
    np.save(f, out)
    return out


def prophet(hist: pd.Series, h: int) -> np.ndarray:
    return _fit("prophet", hist, h)


def prophet_hol(hist: pd.Series, h: int) -> np.ndarray:
    return _fit("prophet_hol", hist, h)
