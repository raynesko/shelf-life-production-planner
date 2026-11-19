"""Weekly plan viewer: line sequence (Gantt) and inventory by age, baseline vs optimised side by side."""
from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st
from common import ARM_NAME, GRID, INK_2, MUTED, PROFILE_COLORS, csv, footer, plotly_layout

AGE_COLORS = ["#86b3ea", "#3f86dc", "#1f5fb0", "#123c74", "#0a2447"]   # one hue, light (fresh) -> dark (old)

st.title("Weekly plan viewer")
st.markdown("Historical replay of the test year. Each bar is a production run coloured by allergen profile; grey "
            "blocks are changeovers (hatched = allergen clean); the dashed line is the 72 h available. Below: stock "
            "left at week end by age, with each SKU's maximum age still shippable (max N, in weeks). Hover for details.")
plans, info, ages = csv("plans.csv"), csv("sku_info.csv"), csv("inventory_age.csv")
if plans is None or info is None or ages is None:
    st.warning("App data missing. Run `python scripts/build_app_data.py`.")
    st.stop()

info = info.set_index("sku_id")
profiles = sorted(info.allergens.unique(), key=lambda a: (a != "none", a.count(","), a))
pcolor = {p: PROFILE_COLORS[i % len(PROFILE_COLORS)] for i, p in enumerate(profiles)}
weeks = plans[["week", "week_start"]].drop_duplicates().sort_values("week")
c0, c1 = st.columns([3, 2])
wk_label = c0.select_slider("Week", options=weeks.week_start.tolist(), value=weeks.week_start.iloc[0])
week = int(weeks[weeks.week_start == wk_label].week.iloc[0])
view = c1.radio("Show", ["Side by side", "B1 tuned", "Rule-of-thumb B1", "Optimised"], horizontal=True)
arms = {"Side by side": ["B1_TUNED", "OPT"], "B1 tuned": ["B1_TUNED"], "Rule-of-thumb B1": ["B1"],
        "Optimised": ["OPT"]}[view]


def gantt(arm: str) -> go.Figure:
    p = plans[(plans.arm == arm) & (plans.week == week)].sort_values("position")
    fig = go.Figure()
    t, shown = 0.0, set()
    for r in p.itertuples():
        co = float(r.changeover_hours_before)
        if co > 0:
            fig.add_bar(x=[co], base=[t], y=["line"], orientation="h", marker_color=GRID,
                        marker_pattern_shape="/" if r.clean_type == "allergen" else "",
                        marker_line_color=MUTED, marker_line_width=0.5, showlegend=False,
                        hovertemplate=f"Changeover into {r.sku_id}<br>{co:.1f} h, {r.clean_type} clean<extra></extra>")
            t += co
        s = info.loc[r.sku_id]
        h = r.qty / s.rate_cases_per_hour
        prof = s.allergens
        fig.add_bar(x=[h], base=[t], y=["line"], orientation="h", marker_color=pcolor[prof],
                    marker_line_color="white", marker_line_width=2, text=r.sku_id, textposition="inside",
                    insidetextanchor="middle", textangle=0, name=f"allergens: {prof}", legendgroup=prof,
                    legendrank=profiles.index(prof), showlegend=prof not in shown,
                    hovertemplate=(f"<b>{r.sku_id} {s['name']}</b><br>{r.qty:,.0f} cases, {h:.1f} h<br>"
                                   f"allergens: {prof}<br>changeover before: {co:.1f} h ({r.clean_type})"
                                   "<extra></extra>"))
        shown.add(prof)
        t += h
    avail = float(info.available_hours.iloc[0])
    fig.add_vline(x=avail, line_dash="dash", line_color=INK_2)
    used_co = p.changeover_hours_before.sum()
    fig.update_yaxes(visible=False)
    fig.update_xaxes(range=[0, avail * 1.02], ticksuffix=" h", dtick=12)
    plotly_layout(fig, 300, barmode="overlay", title=f"{ARM_NAME[arm]}: {len(p)} runs, {used_co:.1f} h changeover", showlegend=True, uniformtext={"minsize": 8, "mode": "hide"})
    fig.update_layout(legend={"orientation": "h", "y": -0.25, "font": {"size": 10}}, margin={"b": 90})
    return fig


def age_chart(arm: str) -> go.Figure:
    a = ages[(ages.arm == arm) & (ages.week == week)]
    fig = go.Figure()
    for age in sorted(ages.age.unique()):
        g = a[a.age == age].set_index("sku_id")[["qty"]].reindex(info.index).fillna(0.0)
        fig.add_bar(x=info.index, y=g.qty, name=f"{age} wk old", marker_color=AGE_COLORS[min(age, 5) - 1],
                    marker_line_color="white", marker_line_width=1,
                    hovertemplate="%{x}: %{y:,.0f} cases aged " + str(age) + " wk<extra></extra>")
    fig.update_xaxes(tickvals=list(info.index), tickangle=0, tickfont={"size": 9},
                     ticktext=[f"{s.replace('SKU-', '')}<br>max {m}" for s, m in zip(info.index, info.max_ship_age_weeks,
                                                                                    strict=True)])
    return plotly_layout(fig, 340, barmode="stack", title=f"{ARM_NAME[arm]}: stock at week end, by age",
                         yaxis_title="cases", legend={"orientation": "h", "y": -0.3, "traceorder": "normal"})


cols = st.columns(len(arms))
for col, arm in zip(cols, arms, strict=True):
    col.plotly_chart(gantt(arm), use_container_width=True)
cols = st.columns(len(arms))
for col, arm in zip(cols, arms, strict=True):
    col.plotly_chart(age_chart(arm), use_container_width=True)
with st.expander("Run table"):
    st.dataframe(plans[(plans.week == week) & plans.arm.isin(arms)]
                 .merge(info[["name", "allergens"]], left_on="sku_id", right_index=True), hide_index=True)
footer()
