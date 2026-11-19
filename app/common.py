"""Shared loaders and style for the Streamlit app. Reads only small committed files (results/, configs/)."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
APP_DATA = ROOT / "results" / "app_data"
HEADLINE = ROOT / "results" / "headline_numbers.json"
LABEL = "simulation on a synthetic plant model"

# reference categorical palette (light); colour follows the entity, never its rank
ARM_COLOR = {"B1_TUNED": "#2a78d6", "B1": "#898781", "OPT": "#eb6834"}
ARMS = ("B1_TUNED", "B1", "OPT")
ARM_NAME = {"B1_TUNED": "B1 tuned (headline baseline)", "B1": "Rule-of-thumb B1", "OPT": "Optimised"}
PROFILE_COLORS = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
INK, INK_2, MUTED, GRID, SURFACE = "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#fcfcfb"


@st.cache_data
def headline() -> dict | None:
    return json.loads(HEADLINE.read_text(encoding="utf-8")) if HEADLINE.exists() else None


@st.cache_data
def csv(name: str) -> pd.DataFrame | None:
    for base in (APP_DATA, ROOT / "results", ROOT / "results" / "forecast", ROOT / "results" / "sensitivity"):
        p = base / name
        if p.exists():
            return pd.read_csv(p)
    return None


def plotly_layout(fig, height: int = 360, **kw):
    base = {"height": height, "paper_bgcolor": SURFACE, "plot_bgcolor": SURFACE, "font": {"color": INK_2, "size": 12},
            "margin": {"l": 10, "r": 10, "t": 40, "b": 10}, "legend": {"orientation": "h", "y": -0.18},
            "hoverlabel": {"bgcolor": "white"}}
    fig.update_layout(**{**base, **kw})
    fig.update_xaxes(gridcolor=GRID, zerolinecolor=GRID)
    fig.update_yaxes(gridcolor=GRID, zerolinecolor=GRID)
    return fig


def footer() -> None:
    st.caption(f"All results: {LABEL}. Demand patterns from Corporacion Favorita (Kaggle); plant, costs and "
               "changeover times are documented assumptions. No real-plant savings are claimed.")
