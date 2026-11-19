"""T5.1.3: attribute the optimiser's effect to forecasting vs planning logic.

Arms (configs/experiment_ablation.yaml, same CRN paths as the main experiment):
  B1 (MA4 forecast + B1 logic), B1_SELFC (selected forecast + B1 logic),
  OPT_MA4 (MA4 forecast + optimiser), OPT (selected forecast + optimiser).
Outputs: results/ablation.csv, results/figures/ablation.png
Run: python scripts/analyze_ablation.py [--run results/experiments/ablation_xxx]
"""
from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from shelflife import viz
from shelflife.analysis.stats import bootstrap

ROOT = Path(__file__).resolve().parents[1]
ARMS = [("B1", "B1: MA(4) forecast + B1 rules"), ("B1_SELFC", "Selected forecast + B1 rules"),
        ("OPT_MA4", "MA(4) forecast + optimiser"), ("OPT", "Selected forecast + optimiser (full)")]
KPIS = [("expired_cases", "Expired waste"), ("lost_cases", "Lost cases"), ("changeover_hours", "Changeover hours"),
        ("evaluated_cost", "Total planning cost")]
# categorical slots 1-4 of the reference palette (fixed by arm, not rank)
COLORS = {"B1": "#2a78d6", "B1_SELFC": "#1baf7a", "OPT_MA4": "#eda100", "OPT": "#eb6834"}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run")
    a = ap.parse_args()
    run = Path(a.run) if a.run else max((ROOT / "results" / "experiments").glob("ablation_*"),
                                        key=lambda p: p.stat().st_mtime)
    df = pd.read_parquet(run / "kpis.parquet")
    mc = df[df.layer == "mc"]
    rows = []
    for arm, label in ARMS:
        r = {"arm": arm, "description": label}
        for col, _ in KPIS + [("fill_rate", "")]:
            r[f"mc_mean_{col}"] = float(mc[mc.arm == arm][col].mean())
            r[f"replay_{col}"] = float(df[(df.layer == "replay") & (df.arm == arm)][col].iloc[0]) \
                if (df.layer == "replay").any() else np.nan
        if arm != "B1":
            for col, _ in KPIS:
                w = mc.pivot(index="path_id", columns="arm", values=col)
                b = bootstrap(w["B1"].to_numpy(), w[arm].to_numpy(), "reduction_pct", n_boot=5000)
                r[f"{col}_reduction_vs_B1_pct"], r[f"{col}_lo"], r[f"{col}_hi"] = b["estimate"], b["ci_lo"], b["ci_hi"]
            w = mc.pivot(index="path_id", columns="arm", values="fill_rate")
            r["fill_rate_delta_pts"] = float(100 * (w[arm] - w["B1"]).mean())
        rows.append(r)
    t = pd.DataFrame(rows)
    t.round(4).drop(columns=[c for c in t.columns if c.startswith("mc_mean_evaluated")]).to_csv(
        ROOT / "results" / "ablation.csv", index=False)

    viz.apply_style()
    fig, ax = plt.subplots(figsize=(8.5, 4))
    x = np.arange(len(KPIS))
    arms = [a for a, _ in ARMS if a != "B1"]
    wbar = 0.24
    for i, arm in enumerate(arms):
        r = t.set_index("arm").loc[arm]
        est = np.array([r[f"{c}_reduction_vs_B1_pct"] for c, _ in KPIS])
        lo = np.array([r[f"{c}_lo"] for c, _ in KPIS])
        hi = np.array([r[f"{c}_hi"] for c, _ in KPIS])
        xs = x + (i - 1) * (wbar + 0.02)
        ax.bar(xs, est, width=wbar, color=COLORS[arm], label=dict(ARMS)[arm])
        ax.errorbar(xs, est, yerr=[est - lo, hi - est], fmt="none", ecolor=viz.INK_2, lw=1, capsize=2)
    ax.axhline(0, color=viz.AXIS, lw=1)
    ax.set_xticks(x, [n for _, n in KPIS])
    ax.set_ylabel("reduction vs B1 (%), positive = better")
    ax.grid(axis="x", visible=False)
    ax.legend(loc="upper left", bbox_to_anchor=(0, -0.12), ncol=3, fontsize=8)
    ax.set_title("Where the improvement comes from: forecast vs planning logic", loc="left")
    viz.source_note(fig, f"Simulation on a synthetic plant model. Paired Monte Carlo, N = {mc.path_id.nunique()}"
                         " paths; bars = mean, whiskers = 95% bootstrap CI.")
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(ROOT / "results" / "figures" / "ablation.png", dpi=150)
    cols = ["arm"] + [f"{c}_reduction_vs_B1_pct" for c, _ in KPIS] + ["fill_rate_delta_pts"]
    print(t[cols].round(2).to_string(index=False))


if __name__ == "__main__":
    main()
