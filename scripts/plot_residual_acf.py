"""T3.2.1: residual diagnostics for ARIMA and ETS.

Residual = one-step-ahead error (y - yhat at horizon 1) over the VALIDATION year only (52 origins per SKU);
the test year is never read. Two SKUs are fixed in advance: SKU-11 (hardest, highest validation WAPE) and
SKU-04 (a typical SKU). Ljung-Box (lag 8) p-values are written to results/forecast/residual_ljungbox.csv
for all 12 SKUs.

Run: python scripts/plot_residual_acf.py
Outputs: results/figures/residual_acf.png, results/forecast/residual_ljungbox.csv
"""
from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from statsmodels.stats.diagnostic import acorr_ljungbox
from statsmodels.tsa.stattools import acf

from shelflife import viz

ROOT = Path(__file__).resolve().parents[1]
FC = ROOT / "results" / "forecast"
SKUS = ["SKU-11", "SKU-04"]
MODELS = ["arima", "ets"]
LAGS = 16


def residuals(model: str) -> pd.DataFrame:
    fc = pd.read_parquet(FC / f"{model}_forecasts.parquet", filters=[("window", "==", "validation")])
    r = fc[fc.horizon == 1].sort_values(["sku_id", "origin"])
    return r.assign(resid=r.y - r.yhat)[["sku_id", "origin", "resid"]]


def main() -> None:
    viz.apply_style()
    res = {m: residuals(m) for m in MODELS}
    lb = []
    for m, r in res.items():
        for sku, g in r.groupby("sku_id"):
            t = acorr_ljungbox(g.resid.to_numpy(), lags=[8])
            lb.append({"model": m, "sku_id": sku, "n": len(g), "lb_stat_lag8": float(t.lb_stat.iloc[0]),
                       "lb_pvalue_lag8": float(t.lb_pvalue.iloc[0])})
    lb = pd.DataFrame(lb)
    lb.round(4).to_csv(FC / "residual_ljungbox.csv", index=False)

    fig, axes = plt.subplots(len(SKUS), len(MODELS), figsize=(8, 5.2), sharey=True)
    lags = np.arange(1, LAGS + 1)
    for i, sku in enumerate(SKUS):
        for j, m in enumerate(MODELS):
            ax = axes[i, j]
            e = res[m].query("sku_id == @sku").resid.to_numpy()
            a = acf(e, nlags=LAGS, fft=False)[1:]
            band = 1.96 / np.sqrt(len(e))
            ax.axhspan(-band, band, color=viz.GRID, alpha=0.8, lw=0)
            ax.axhline(0, color=viz.AXIS, lw=0.8)
            ax.vlines(lags, 0, a, color=viz.FAMILY_COLOR["DAIRY"], lw=2)
            ax.plot(lags, a, "o", ms=4, color=viz.FAMILY_COLOR["DAIRY"])
            p = lb.query("model == @m and sku_id == @sku").lb_pvalue_lag8.iloc[0]
            ax.set_title(f"{sku} - {m.upper()}   (Ljung-Box lag 8 p = {p:.2f})", loc="left")
            ax.set_xticks([1, 4, 8, 12, 16])
            ax.grid(axis="x", visible=False)
            if j == 0:
                ax.set_ylabel("autocorrelation")
            if i == len(SKUS) - 1:
                ax.set_xlabel("lag (weeks)")
    fig.suptitle("One-step-ahead forecast residuals, validation year: autocorrelation by lag",
                 x=0.01, ha="left", fontsize=11, color=viz.INK)
    viz.source_note(fig, "Shaded band = approx. 95% bounds (+/-1.96/sqrt(n), n = 52). Favorita weekly demand, "
                         "12-SKU panel; test year not used.")
    fig.tight_layout(rect=(0, 0.03, 1, 0.96))
    out = ROOT / "results" / "figures" / "residual_acf.png"
    fig.savefig(out, dpi=150)
    print(out)
    print(lb.groupby("model").lb_pvalue_lag8.apply(lambda s: f"{(s < 0.05).sum()}/{len(s)} SKUs p<0.05"))


if __name__ == "__main__":
    main()
