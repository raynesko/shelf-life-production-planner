"""Shelf-Life-Aware Production Planner - dashboard entry point.

Run: streamlit run app/streamlit_app.py   (reads only small committed files; no raw data needed)
"""
from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent))

st.set_page_config(page_title="Shelf-life production planner", layout="wide")

pages = [
    st.Page("views/overview.py", title="Overview", default=True),
    st.Page("views/forecast.py", title="Forecasts", url_path="forecasts"),
    st.Page("views/plan_viewer.py", title="Weekly plan viewer", url_path="plan_viewer"),
    st.Page("views/scenarios.py", title="Scenario explorer", url_path="scenarios"),
]
st.navigation(pages).run()
