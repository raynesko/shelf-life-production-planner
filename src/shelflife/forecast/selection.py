"""Forecast model selection (T3.2.3). Rule fixed BEFORE seeing arima52/prophet test results (2026-11-17):

- Candidates: every model with forecasts on disk, including the naive benchmarks, except variants rejected on
  validation in their own ticket (scripts/select_forecasts.py EXCLUDED: plain prophet, T3.2.2).
- Primary: per SKU, the model with the lowest VALIDATION-window WAPE (ties -> simpler model order below).
- Also reported: the single global model with the lowest validation WAPE (overfitting check).
- The test window is never read here: `select` receives validation rows only and asserts it.
Headline comparisons (reported on TEST): selected vs MA(4) (best naive benchmark, also baseline B1's forecast;
recommended headline, open question O-09) and vs seasonal naive (the charter's original comparator).
"""
from __future__ import annotations

import pandas as pd

from shelflife.forecast.backtest import wape

SIMPLICITY = ["naive", "ma4", "seasonal_naive", "ets", "arima", "arima52", "prophet", "prophet_hol"]


def _rank(model: str) -> int:
    return SIMPLICITY.index(model) if model in SIMPLICITY else len(SIMPLICITY)


def select(val_fc: pd.DataFrame) -> tuple[dict[str, str], str, pd.DataFrame]:
    """val_fc: harness rows for the VALIDATION window only. Returns (per-SKU choice, global choice, table)."""
    if set(val_fc.window.unique()) != {"validation"}:
        raise ValueError("selection must only see validation-window rows")
    t = (val_fc.groupby(["sku_id", "model"]).apply(lambda g: wape(g.y, g.yhat), include_groups=False)
         .rename("val_wape").reset_index())
    t["rank"] = t.model.map(_rank)
    per_sku = (t.sort_values(["sku_id", "val_wape", "rank"]).groupby("sku_id").head(1)
               .set_index("sku_id").model.to_dict())
    glob = (val_fc.groupby("model").apply(lambda g: wape(g.y, g.yhat), include_groups=False)
            .rename("val_wape").reset_index())
    glob["rank"] = glob.model.map(_rank)
    global_model = glob.sort_values(["val_wape", "rank"]).model.iloc[0]
    return per_sku, global_model, t.drop(columns="rank")


def assemble(fc: pd.DataFrame, per_sku: dict[str, str], label: str = "selected") -> pd.DataFrame:
    parts = [fc[(fc.sku_id == s) & (fc.model == m)] for s, m in per_sku.items()]
    return pd.concat(parts, ignore_index=True).assign(source_model=lambda d: d.model, model=label)


def headline(test_sel: pd.DataFrame, test_all: pd.DataFrame) -> pd.DataFrame:
    rows = {"selected_per_sku": wape(test_sel.y, test_sel.yhat)}
    for m in sorted(test_all.model.unique()):
        g = test_all[test_all.model == m]
        rows[m] = wape(g.y, g.yhat)
    out = pd.DataFrame({"model": list(rows), "test_wape": list(rows.values())})
    sel = rows["selected_per_sku"]
    out["improvement_of_selected_vs_this_pct"] = 100 * (1 - sel / out.test_wape)
    return out
