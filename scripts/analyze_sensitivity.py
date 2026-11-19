"""T5.2.2: tornado chart, waste-vs-service frontier, break-even table; extends results/headline_numbers.json.

Inputs: results/sensitivity/*.parquet (scripts/run_sensitivity.py).
Outputs: results/sensitivity/summary.csv, results/figures/tornado.png, results/figures/frontier.png,
         headline_numbers.json keys share_of_cells_improved, sensitivity (vs the headline baseline)
Run: python scripts/analyze_sensitivity.py
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import yaml

from shelflife import viz
from shelflife.analysis.stats import bootstrap

ROOT = Path(__file__).resolve().parents[1]
SENS = ROOT / "results" / "sensitivity"
FIG = ROOT / "results" / "figures"
LABEL = "simulation on a synthetic plant model"
NAMES = {"shelf_life_scale": "Shelf life (x)", "changeover_scale": "Changeover times (x)",
         "error_scale": "Forecast error (x)", "demand_scale": "Demand / utilisation (x)",
         "msl": "Min. remaining shelf life at ship", "costs_expiry_per_case": "Expiry cost weight",
         "costs_changeover_per_hour": "Changeover cost weight", "costs_lost_sale_per_case": "Lost-sale cost weight"}
BASES = ("B1_TUNED", "B1")      # ADR-009: validation-tuned B1 is the headline baseline
DEFAULTS = {"shelf_life_scale": 1.0, "changeover_scale": 1.0, "error_scale": 1.0, "demand_scale": 1.005,
            "msl": 0.5, "costs_expiry_per_case": 4.0, "costs_changeover_per_hour": 400.0,
            "costs_lost_sale_per_case": 40.0}


def summarise_cells() -> pd.DataFrame:
    rows = []
    for f in sorted(SENS.glob("*.parquet")):
        if f.stem == "frontier":
            continue
        df = pd.read_parquet(f)
        for v, g in df.groupby("value"):
            w = g.pivot(index="path_id", columns="arm", values=["expired_cases", "expired_pct", "fill_rate",
                                                               "changeover_hours", "lost_cases", "evaluated_cost"])
            for base in [b for b in BASES if b in set(g.arm)]:
                r = {"parameter": f.stem, "value": v, "base": base, "n": len(w)}
                for col, kind, name in (("expired_cases", "reduction_pct", "waste_red"),
                                        ("fill_rate", "delta_pts", "fill_delta"),
                                        ("changeover_hours", "reduction_pct", "co_red"),
                                        ("lost_cases", "reduction_pct", "lost_red"),
                                        ("evaluated_cost", "reduction_pct", "cost_red")):
                    b = bootstrap(w[col][base].to_numpy(), w[col]["OPT"].to_numpy(), kind, n_boot=2000)
                    r[name], r[name + "_lo"], r[name + "_hi"] = b["estimate"], b["ci_lo"], b["ci_hi"]
                # waste in percentage points of production, base minus optimiser (positive = optimiser better);
                # bounded, unlike a % reduction when the baseline's waste is near zero
                b = bootstrap(w["expired_pct"]["OPT"].to_numpy(), w["expired_pct"][base].to_numpy(), "delta",
                              n_boot=2000)
                r["waste_pts"], r["waste_pts_lo"], r["waste_pts_hi"] = b["estimate"], b["ci_lo"], b["ci_hi"]
                r["base_expired_pct"] = float(w["expired_pct"][base].mean())
                r["opt_expired_pct"] = float(w["expired_pct"]["OPT"].mean())
                r["base_fill_rate"] = float(w["fill_rate"][base].mean())
                r["opt_fill_rate"] = float(w["fill_rate"]["OPT"].mean())
                r["checker_violations"] = int(g.get("checker_violations", pd.Series([0])).sum())
                rows.append(r)
    return pd.DataFrame(rows)


def tornado(s: pd.DataFrame, base: str) -> None:
    """Three panels sharing the parameter axis: range of each effect across the one-at-a-time sweep."""
    s = s[s.base == base]
    viz.apply_style()
    is_def = [DEFAULTS.get(p) == v for p, v in zip(s.parameter, s.value, strict=True)]
    panels = (("cost_red", "planning cost reduction (%)", "{:+.1f}"),
              ("waste_pts", "expired waste reduction\n(pts of production)", "{:+.1f}"),
              ("fill_delta", "fill rate change (pts)", "{:+.1f}"))
    order = (s.groupby("parameter").cost_red.agg(lambda x: x.max() - x.min()).sort_values().index.tolist())
    fig, axes = plt.subplots(1, 3, figsize=(11.5, 0.5 * len(order) + 2.0), sharey=True)
    color = viz.ARM_COLOR["optimised"]
    for ax, (col, label, _f) in zip(axes, panels, strict=True):
        y = np.arange(len(order))
        default = s[is_def][col].median()
        for yi, p in zip(y, order, strict=True):
            g = s[s.parameter == p].sort_values("value")
            lo, hi = g[col].min(), g[col].max()
            ax.barh(yi, hi - lo if hi > lo else 0.02 * (abs(hi) + 1), left=lo, height=0.5, color=color, alpha=0.8)
            vlo, vhi = g.loc[g[col].idxmin(), "value"], g.loc[g[col].idxmax(), "value"]
            ax.annotate(f"{vlo:g}", (lo, yi), xytext=(-3, 0), textcoords="offset points", ha="right",
                        va="center", fontsize=7, color=viz.INK_2)
            ax.annotate(f"{vhi:g}", (hi, yi), xytext=(3, 0), textcoords="offset points", va="center", fontsize=7,
                        color=viz.INK_2)
        ax.axvline(0, color=viz.AXIS, lw=1)
        ax.axvline(default, color=viz.INK_2, lw=1, ls="--")
        ax.set_xlabel(label + "\npositive = optimiser better", fontsize=8.5)
        ax.grid(axis="y", visible=False)
        lo_all, hi_all = s[col].min(), s[col].max()
        pad = 0.18 * (hi_all - lo_all + 1e-9)
        ax.set_xlim(min(lo_all, 0) - pad, max(hi_all, 0) + pad)
    axes[0].set_yticks(np.arange(len(order)), [NAMES.get(p, p) for p in order])
    who = "B1 tuned on validation" if base == "B1_TUNED" else "rule-of-thumb B1"
    fig.suptitle(f"Optimiser vs {who}: range of each effect across one-at-a-time sweeps (dashed = defaults)",
                 x=0.01, ha="left", fontsize=11, color=viz.INK)
    viz.source_note(fig, f"{LABEL.capitalize()}. N = {int(s.n.min())} paired paths per cell; labels at bar ends = "
                         "parameter value giving the min / max.")
    fig.tight_layout(rect=(0, 0.04, 1, 0.94))
    fig.savefig(FIG / ("tornado.png" if base == "B1_TUNED" else "tornado_b1_default.png"), dpi=150)
    plt.close(fig)


def frontier(tuned_cover: float | None) -> pd.DataFrame | None:
    f = SENS / "frontier.parquet"
    if not f.exists():
        return None
    df = pd.read_parquet(f)
    pts = df.groupby(["arm", "lever", "value"]).agg(fill_rate=("fill_rate", "mean"), expired_pct=("expired_pct", "mean"),
                                                   changeover_h_week=("changeover_hours", lambda x: x.mean() / 52),
                                                   evaluated_cost=("evaluated_cost", "mean")).reset_index()
    pts["cost_index"] = 100 * pts.evaluated_cost / pts.evaluated_cost.min()
    viz.apply_style()
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.4))
    for ax, ycol, ylab in ((axes[0], "expired_pct", "expired waste (% of cases produced)"),
                           (axes[1], "changeover_h_week", "changeover hours per week (of 72 available)")):
        for arm, label, marker, ls in (("B1", "Baseline B1, cover 0.5-3 weeks", "s", "--"),
                                       ("OPT", "Optimiser, service target 80-99%", "o", "-")):
            g = pts[pts.arm == arm].sort_values("value")
            c = viz.ARM_COLOR["baseline" if arm == "B1" else "optimised"]
            ax.plot(100 * g.fill_rate, g[ycol], ls, marker=marker, ms=6.5, color=c, label=label)
            for _, r in g.iterrows():
                txt = f"{r.value:g} wk" if arm == "B1" else f"{100 * r.value:g}%"
                ax.annotate(txt, (100 * r.fill_rate, r[ycol]), xytext=(5, 4), textcoords="offset points",
                            fontsize=7, color=viz.INK_2)
            if arm == "B1" and tuned_cover is not None and (g.value == tuned_cover).any():
                r = g[g.value == tuned_cover].iloc[0]
                ax.plot(100 * r.fill_rate, r[ycol], "s", ms=13, mfc="none", mec=viz.INK, mew=1.4,
                        label=f"B1 tuned on validation ({tuned_cover:g} wk)")
        ax.set_xlabel("fill rate (%)")
        ax.set_ylabel(ylab)
    axes[0].set_title("Waste vs service (lower-right is better)", loc="left", fontsize=10)
    axes[1].set_title("Line time vs service (lower-right is better)", loc="left", fontsize=10)
    axes[0].legend(loc="upper left", fontsize=8)
    viz.source_note(fig, f"{LABEL.capitalize()}. Mean over {df.path_id.nunique()} paired demand paths per point; "
                         "both planners see identical paths.")
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    fig.savefig(FIG / "frontier.png", dpi=150)
    plt.close(fig)
    pts.drop(columns="evaluated_cost").round(4).to_csv(SENS / "frontier_points.csv", index=False)
    return pts


def main() -> None:
    s = summarise_cells()
    s.round(3).to_csv(SENS / "summary.csv", index=False)
    head = "B1_TUNED" if (s.base == "B1_TUNED").any() else "B1"
    for base in s.base.unique():
        tornado(s, base)
    cfg_b = ROOT / "configs" / "baseline.yaml"
    tuned = float(yaml.safe_load(cfg_b.read_text())["cover_weeks"]) if cfg_b.exists() else None
    pts = frontier(tuned)
    h = s[s.base == head]
    hn = ROOT / "results" / "headline_numbers.json"
    out = json.loads(hn.read_text()) if hn.exists() else {}
    out.pop("sensitivity_min_waste_reduction_pct", None)
    out["share_of_cells_improved"] = round(float((h.cost_red_lo > 0).mean()), 3)
    out["sensitivity"] = {
        "baseline": head,
        "definition_share_improved": "share of one-at-a-time cells whose 95% CI on planning-cost reduction is > 0",
        "n_cells": int(len(h)), "n_paths_per_cell": int(h.n.min()),
        "share_cells_cost_improved": round(float((h.cost_red_lo > 0).mean()), 3),
        "share_cells_changeover_improved": round(float((h.co_red_lo > 0).mean()), 3),
        "share_cells_waste_improved": round(float((h.waste_pts_lo > 0).mean()), 3),
        "share_cells_fill_non_inferior": round(float((h.fill_delta_lo > -0.5).mean()), 3),
        "cost_reduction_range_pct": [round(float(h.cost_red.min()), 2), round(float(h.cost_red.max()), 2)],
        "worst_cost_cell": {k: (float(v) if not isinstance(v, str) else v) for k, v in
                            h.loc[h.cost_red.idxmin(), ["parameter", "value", "cost_red"]].items()},
        "checker_violations_total": int(s.checker_violations.sum()),
    }
    if pts is not None:
        out["sensitivity"]["frontier"] = pts.drop(columns="evaluated_cost").round(4).to_dict(orient="records")
    hn.write_text(json.dumps(out, indent=2, default=float), encoding="utf-8")
    pd.set_option("display.width", 220)
    print(s[["parameter", "value", "base", "cost_red", "cost_red_lo", "waste_pts", "waste_red", "fill_delta",
             "co_red"]].round(2).to_string(index=False))
    if pts is not None:
        print(pts.round(4).to_string(index=False))


if __name__ == "__main__":
    main()
