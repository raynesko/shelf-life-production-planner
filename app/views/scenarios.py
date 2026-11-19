"""Scenario explorer: look up the precomputed one-at-a-time sensitivity grid (no live solving)."""
from __future__ import annotations

import numpy as np
import streamlit as st
from common import ROOT, csv, footer

SLIDERS = {
    "shelf_life_scale": ("Shelf life multiplier", 0.5, 1.25, 1.0),
    "changeover_scale": ("Changeover time multiplier", 0.5, 2.0, 1.0),
    "error_scale": ("Forecast error multiplier", 0.5, 2.0, 1.0),
    "demand_scale": ("Demand multiplier (utilisation)", 0.8, 1.15, 1.005),
}

st.title("Scenario explorer")
s = csv("summary.csv")
if s is None:
    st.warning("Sensitivity results not found. Run `python scripts/run_sensitivity.py` and "
               "`python scripts/analyze_sensitivity.py`.")
    st.stop()
bases = {"B1_TUNED": "B1 tuned on validation (headline)", "B1": "Rule-of-thumb B1"}
if "base" not in s:
    s = s.assign(base="B1")
avail = [b for b in bases if b in set(s.base)]
base = st.radio("Compare the optimiser with", avail, format_func=bases.get, horizontal=True)
s = s[s.base == base]
n = int(s.n.min())
st.markdown(f"Precomputed one-at-a-time sweeps: one parameter changes, all others stay at their defaults. "
            f"Each cell is a paired Monte Carlo with **N = {n} demand paths** (reduced from the main run's N).")
param = st.radio("Parameter", list(SLIDERS), format_func=lambda p: SLIDERS[p][0], horizontal=True)
label, lo, hi, default = SLIDERS[param]
grid = np.sort(s[s.parameter == param].value.unique())
x = st.slider(label, float(lo), float(hi), float(default), step=0.05)
nearest = float(grid[np.abs(grid - x).argmin()])
if abs(nearest - x) > 1e-9:
    st.info(f"{x:g} is not on the precomputed grid {', '.join(f'{g:g}' for g in grid)}; showing the nearest "
            f"point, {nearest:g}.")
r = s[(s.parameter == param) & (np.isclose(s.value, nearest))].iloc[0]
cols = st.columns(4)
for col, (k, title, unit) in zip(cols, [("waste_pts", "Expired waste reduction", "pts of production"),
                                        ("fill_delta", "Fill rate change", "pts"),
                                        ("co_red", "Changeover hours reduction", "%"),
                                        ("cost_red", "Planning cost reduction", "%")], strict=True):
    with col.container(border=True):
        st.markdown(f"**{title}**")
        st.markdown(f"<span style='font-size:1.8rem;font-weight:600'>{r[k]:+.1f}</span> {unit}",
                    unsafe_allow_html=True)
        st.caption(f"95% CI [{r[k + '_lo']:+.1f}, {r[k + '_hi']:+.1f}]; positive = optimiser better  \n"
                   "simulation on a synthetic plant model")
c1, c2 = st.columns(2)
tor = "tornado.png" if base == "B1_TUNED" else "tornado_b1_default.png"
for col, f, cap in ((c1, tor, "Range of each effect per parameter"),
                    (c2, "frontier.png", "Waste and line time vs service, each planner swept along its own lever")):
    p = ROOT / "results" / "figures" / f
    if p.exists():
        col.image(str(p), caption=cap, use_container_width=True)
footer()
