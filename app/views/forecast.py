"""Forecasts: actual vs one-week-ahead forecast per SKU, and test-year accuracy of all models."""
from __future__ import annotations

import streamlit as st
from common import APP_DATA, csv, footer

st.title("Demand forecasts")
st.markdown("Rolling-origin backtest: models refit every week on history only. Model per SKU chosen on the "
            "**validation** year; the **test** year is reported here.")
info = csv("sku_info.csv")
skus = info.sku_id.tolist() if info is not None else []
names = dict(zip(info.sku_id, info.name, strict=True)) if info is not None else {}
sku = st.selectbox("SKU", skus, format_func=lambda s: f"{s} - {names.get(s, '')}")
img = APP_DATA / f"forecast_{sku}.png"
if img.exists():
    st.image(str(img), use_container_width=True)
else:
    st.info("Forecast chart not built. Run `python scripts/build_app_data.py`.")

m = csv("model_metrics.csv")
if m is not None:
    st.subheader("Test-year accuracy, all 12 SKUs pooled")
    t = m[(m.sku_id == "ALL") & (m.window == "test")].set_index("model")[["wape", "bias", "mase"]]
    hl = csv("headline_forecast.csv")
    if hl is not None:
        t.loc["selected per SKU (used by planner)", "wape"] = float(hl.set_index("model").test_wape["selected_per_sku"])
    t = (t.rename(index={"prophet": "prophet (rejected on validation)"}).sort_values("wape").round(2)
         .rename(columns={"wape": "WAPE %", "bias": "Bias %", "mase": "MASE"}))
    st.dataframe(t, use_container_width=False)
    st.caption("Honest result: the per-SKU selected forecast is no better than a 4-week moving average on the test "
               "year (see docs/methods/forecasting.md); the ablation separates forecast and planning effects.")
footer()
