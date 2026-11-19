"""Shared chart style for every project figure (static matplotlib).

Palette: reference categorical slots 1-3 (blue, orange, aqua), validated all-pairs for colour-vision
deficiency (worst CVD dE 9.2, normal-vision dE 24.0, light surface). Aqua is < 3:1 contrast on the
surface, so charts that use it must carry visible direct labels or a table view (relief rule).
Colour follows the entity (family / arm), never its rank. One y-axis per chart.
"""
from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_2 = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
AXIS = "#c3c2b7"

FAMILY_COLOR = {"DAIRY": "#2a78d6", "DELI": "#eb6834", "PREPARED FOODS": "#1baf7a"}
ARM_COLOR = {"baseline": "#2a78d6", "optimised": "#eb6834"}   # same slots, fixed by entity
LABEL = "simulation on a synthetic plant model"


def apply_style() -> None:
    plt.rcParams.update({
        "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
        "axes.edgecolor": AXIS, "axes.labelcolor": INK_2, "axes.titlecolor": INK, "axes.titlesize": 10,
        "axes.titleweight": "regular", "axes.labelsize": 9, "axes.grid": True, "axes.axisbelow": True,
        "grid.color": GRID, "grid.linewidth": 0.6, "xtick.color": MUTED, "ytick.color": MUTED,
        "xtick.labelsize": 8, "ytick.labelsize": 8, "axes.spines.top": False, "axes.spines.right": False,
        "lines.linewidth": 1.6, "legend.frameon": False, "legend.fontsize": 8,
        "font.family": ["Segoe UI", "DejaVu Sans", "sans-serif"], "figure.dpi": 110,
    })


def source_note(fig, text: str) -> None:
    fig.text(0.01, 0.005, text, fontsize=7, color=MUTED, ha="left", va="bottom")
