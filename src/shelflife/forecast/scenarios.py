"""Forecast-error model and demand-scenario generator (T3.3.1).

sigma[p, h]  : std of (y - yhat) of the SELECTED model at horizon h, VALIDATION window only.
Scenarios    : demand[path, p, t] = center[p, t] + sigma[p, 1] * e[path, p, t], clipped at 0, where e is a
               moving block bootstrap (block = 4 weeks) of standardised one-step validation residuals. Blocks
               are drawn jointly for all SKUs, keeping autocorrelation and cross-SKU correlation.
               center = "actual" (default, ADR-008): the real test-year demand, so the planner's real forecast
               errors (bias, missed swings) are kept in every path. center = "forecast": the one-step forecast
               (the first design; it hands a planner that uses that forecast the true mean of every path).
Coverage     : share of test-year actuals inside yhat +/- z * sigma[p, h] (normal intervals), per level.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.stats import norm


def sigma_table(val_sel: pd.DataFrame) -> pd.DataFrame:
    if set(val_sel.window.unique()) != {"validation"}:
        raise ValueError("sigma must be estimated on validation rows only")
    r = val_sel.assign(err=val_sel.y - val_sel.yhat)
    t = r.groupby(["sku_id", "horizon"]).agg(sigma=("err", "std"), n=("err", "size"), bias=("err", "mean"),
                                             mean_y=("y", "mean")).reset_index()
    t["rel_sigma"] = t.sigma / t.mean_y
    return t


def coverage(test_sel: pd.DataFrame, sig: pd.DataFrame, levels=(0.8, 0.95)) -> pd.DataFrame:
    d = test_sel.merge(sig[["sku_id", "horizon", "sigma"]], on=["sku_id", "horizon"])
    rows = []
    for lv in levels:
        z = norm.ppf(0.5 + lv / 2)
        inside = (d.y - d.yhat).abs() <= z * d.sigma
        rows.append({"level": lv, "empirical": float(inside.mean()), "n": int(len(d)),
                     **{f"h{h}": float(inside[d.horizon == h].mean()) for h in (1, 4, 13)}})
    return pd.DataFrame(rows)


@dataclass
class ScenarioGenerator:
    sku_ids: list[str]
    center: np.ndarray         # (n_sku, n_weeks) path centre: actual demand (default) or one-step forecast
    sigma1: np.ndarray         # (n_sku,)
    std_resid: np.ndarray      # (n_sku, n_val) standardised one-step validation residuals (aligned in time)
    block: int = 4

    @classmethod
    def from_frames(cls, val_sel: pd.DataFrame, test_sel: pd.DataFrame, sig: pd.DataFrame,
                    block: int = 4, center: str = "actual") -> ScenarioGenerator:
        if center not in ("actual", "forecast"):
            raise ValueError(center)
        skus = sorted(test_sel.sku_id.unique())
        s1 = sig[sig.horizon == 1].set_index("sku_id").sigma.loc[skus].to_numpy()
        v = val_sel[val_sel.horizon == 1].pivot(index="sku_id", columns="target_week", values="y") \
            - val_sel[val_sel.horizon == 1].pivot(index="sku_id", columns="target_week", values="yhat")
        std = (v.loc[skus].to_numpy() - v.loc[skus].to_numpy().mean(axis=1, keepdims=True)) / s1[:, None]
        t1 = test_sel[test_sel.horizon == 1].pivot(index="sku_id", columns="target_week",
                                                   values="y" if center == "actual" else "yhat")
        return cls(skus, t1.loc[skus].to_numpy(float), s1, std, block)

    def generate(self, n_paths: int, seed: int, error_scale: float = 1.0) -> np.ndarray:
        """(n_paths, n_sku, T) non-negative demand; error_scale multiplies the error term (T5.2.1)."""
        rng = np.random.default_rng(seed)
        n, T = self.center.shape
        L = self.std_resid.shape[1]
        nb = -(-T // self.block)
        starts = rng.integers(0, L - self.block + 1, size=(n_paths, nb))
        idx = (starts[:, :, None] + np.arange(self.block)[None, None, :]).reshape(n_paths, -1)[:, :T]
        e = self.std_resid[:, idx]                          # (n_sku, n_paths, T)
        e = np.transpose(e, (1, 0, 2))                      # (n_paths, n_sku, T)
        return np.clip(self.center[None] + error_scale * self.sigma1[None, :, None] * e, 0, None)
