"""Overview: headline KPI cards (from results/headline_numbers.json), per-SKU and weekly comparisons."""
from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st
from common import ARM_COLOR, ARM_NAME, ARMS, LABEL, csv, footer, headline, plotly_layout

CARDS = [
    ("changeover_hours_reduction_pct", "Changeover hours", ""),
    ("evaluated_cost_reduction_pct", "Planning cost (model weights)", ""),
    ("expired_waste_reduction_pct", "Expired waste", ""),
    ("fill_rate_delta_pts", "Fill rate", "pts"),
    ("forecast_wape_improvement_pct", "Forecast error (WAPE) vs 4-wk MA", ""),
]


def card_text(h: dict, key: str, kind: str) -> tuple[str, str, str]:
    """Value, unit and CI text. Reductions are shown by direction ('% lower' / '% higher'), never as a negative
    reduction."""
    v = h[key] if key in h and "estimate" in h[key] else h["monte_carlo"][key]
    if kind == "pts":
        return f"{v['estimate']:+.2f}", "pts", f"95% CI [{v['ci_lo']:+.2f}, {v['ci_hi']:+.2f}]"
    if v["estimate"] >= 0:
        return f"{v['estimate']:.1f}", "% lower", f"95% CI [{v['ci_lo']:.1f}, {v['ci_hi']:.1f}]"
    return f"{-v['estimate']:.1f}", "% higher", f"95% CI [{-v['ci_hi']:.1f}, {-v['ci_lo']:.1f}]"


def direction(x: float) -> str:
    return f"{x:.1f}% lower" if x >= 0 else f"{-x:.1f}% higher"


st.title("Shelf-life-aware production planner")
st.markdown(f"**Optimised rolling plan vs a good-practice baseline planner, one refrigerated line, 12 SKUs.** Cards "
            f"compare against B1 with its cover tuned on the validation year (ADR-009); the charts also show the "
            f"rule-of-thumb B1 (2-week cycle). *{LABEL.capitalize()}.*")

h = headline()
if h is None:
    st.warning("results/headline_numbers.json not found. Run `python scripts/analyze_experiment.py` first.")
else:
    cols = st.columns(len(CARDS))
    for col, (key, title, kind) in zip(cols, CARDS, strict=True):
        val, unit, ci = card_text(h, key, kind)
        with col.container(border=True):
            st.markdown(f"**{title}**")
            st.markdown(f"<span style='font-size:2rem;font-weight:600'>{val}</span> {unit}", unsafe_allow_html=True)
            st.caption(f"{ci}  \n{LABEL}")
    st.caption(f"Monte Carlo: N = {h['n_paths']} paired demand paths (both planners see identical demand). Forecast "
               f"card: test-year WAPE of the selected model vs the 4-week moving average, CI over forecast weeks. "
               f"Independent plan checker: {h['checker_violations_total']} violations.")
    r = h["replay_layer_a"]
    st.markdown(
        f"**Historical replay of the test year (Apr 2016 - Mar 2017, real demand), optimiser vs tuned B1:** expired "
        f"waste {direction(r['expired_waste_reduction_pct'])}, changeover hours "
        f"{direction(r['changeover_hours_reduction_pct'])}, fill rate {r['fill_rate_delta_pts']:+.2f} pts, lost cases "
        f"{direction(r['lost_cases_reduction_pct'])}.")

st.subheader("By SKU (historical replay of the test year)")
sk, info = csv("sku_kpis.csv"), csv("sku_info.csv")
if sk is not None and info is not None:
    sk = sk.merge(info[["sku_id", "name", "shelf_life_days"]], on="sku_id")
    sk["label"] = sk.sku_id + " " + sk.name + " (" + sk.shelf_life_days.astype(int).astype(str) + " d)"
    c1, c2 = st.columns(2)
    for col, metric, title, scale in ((c1, "expired", "Expired cases", 1), (c2, "fill_rate", "Fill rate (%)", 100)):
        fig = go.Figure()
        for arm in [a for a in ARMS if a in set(sk.arm)]:
            g = sk[sk.arm == arm]
            fig.add_bar(y=g.label, x=g[metric] * scale, orientation="h", name=ARM_NAME[arm],
                        marker_color=ARM_COLOR[arm],
                        hovertemplate="%{y}<br>" + title + ": %{x:,.1f}<extra>" + ARM_NAME[arm] + "</extra>")
        fig.update_yaxes(autorange="reversed")
        if metric == "fill_rate":
            fig.update_xaxes(range=[90, 100.5])
        col.plotly_chart(plotly_layout(fig, 430, title=title, barmode="group", bargap=0.25), use_container_width=True)

st.subheader("Week by week (historical replay)")
wk = csv("weekly_kpis.csv")
if wk is not None:
    c1, c2 = st.columns(2)
    for col, metric, title in ((c1, "expired", "Expired cases per week"),
                               (c2, "changeover_hours", "Changeover hours per week")):
        fig = go.Figure()
        for arm in [a for a in ARMS if a in set(wk.arm)]:
            g = wk[wk.arm == arm]
            fig.add_scatter(x=g.week_start, y=g[metric], mode="lines", name=ARM_NAME[arm],
                            line={"color": ARM_COLOR[arm], "width": 2})
        col.plotly_chart(plotly_layout(fig, 320, title=title, hovermode="x unified"), use_container_width=True)
footer()
