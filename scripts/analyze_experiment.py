"""T5.1.2: statistics for the main experiment -> results/headline_numbers.json (single source of resume numbers).

Reads results/experiments/<run_id>/kpis.parquet (default: newest main_* run), the forecast results, and writes:
  results/headline_numbers.json, results/experiment_summary.csv, results/figures/kpi_comparison.png
Run: python scripts/analyze_experiment.py [--run results/experiments/main_xxx]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from shelflife import viz
from shelflife.analysis import experiment as X
from shelflife.analysis.stats import summarise_experiment
from shelflife.forecast.backtest import wape

ROOT = Path(__file__).resolve().parents[1]
FC = ROOT / "results" / "forecast"
LABEL = "simulation on a synthetic plant model"


def forecast_improvement(bench: str, n_boot: int = 10_000, seed: int = 0) -> dict:
    """Test-year WAPE improvement of the selected forecast over `bench`; CI by resampling forecast origins."""
    sel = pd.read_parquet(FC / "forecasts_test.parquet")
    allm = pd.concat([pd.read_parquet(FC / f"{m}_forecasts.parquet") for m in ("benchmark",)])
    b = allm[(allm.model == bench) & (allm.window == "test")]
    k = ["sku_id", "origin", "horizon"]
    m = sel[k + ["y", "yhat"]].merge(b[k + ["yhat"]], on=k, suffixes=("_sel", "_b"))
    assert len(m) == len(sel), "benchmark must cover every selected-forecast row"
    m["ae_sel"], m["ae_b"] = (m.y - m.yhat_sel).abs(), (m.y - m.yhat_b).abs()
    g = m.groupby("origin")[["ae_sel", "ae_b", "y"]].sum()
    est = 100 * (1 - wape(m.y, m.yhat_sel) / wape(m.y, m.yhat_b))
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(g), size=(n_boot, len(g)))
    a = g.to_numpy()
    boots = 100 * (1 - a[idx, 0].sum(1) / a[idx, 1].sum(1))
    lo, hi = np.quantile(boots, [0.025, 0.975])
    return {"estimate": float(est), "ci_lo": float(lo), "ci_hi": float(hi), "benchmark": bench,
            "wape_selected_pct": float(wape(m.y, m.yhat_sel)), "wape_benchmark_pct": float(wape(m.y, m.yhat_b)),
            "resampling_unit": "forecast origin (week)", "n_origins": int(len(g))}


def plot(sums: dict[str, pd.DataFrame], out: Path, n: int) -> None:
    """Paired effects vs each baseline: filled = validation-tuned B1 (headline), hollow = rule-of-thumb B1."""
    viz.apply_style()
    names = {"expired_waste_reduction_pct": "Expired waste reduction (%)",
             "lost_cases_reduction_pct": "Lost cases reduction (%)",
             "changeover_hours_reduction_pct": "Changeover hours reduction (%)",
             "allergen_clean_hours_reduction_pct": "Allergen-clean hours reduction (%)",
             "evaluated_cost_reduction_pct": "Total planning cost reduction (%)",
             "fill_rate_delta_pts": "Fill rate change (percentage points)"}
    styles = {"B1_TUNED": ("vs B1 tuned on validation (headline)", "o", viz.ARM_COLOR["baseline"], 0.13),
              "B1": ("vs rule-of-thumb B1 (2-week cycle)", "s", viz.MUTED, -0.13)}
    pct_names = [k for k in names if k != "fill_rate_delta_pts"]
    fig, axes = plt.subplots(1, 2, figsize=(10.5, 4.8), gridspec_kw={"width_ratios": [3.2, 1]})
    for base, summary in sums.items():
        label, marker, color, dy = styles[base]
        sm = summary.set_index("metric")
        for ax, keys, f in ((axes[0], pct_names, "{:+.0f}"), (axes[1], ["fill_rate_delta_pts"], "{:+.2f}")):
            part = sm.loc[keys]
            y = np.arange(len(part))[::-1] + dy
            ax.hlines(y, part.ci_lo, part.ci_hi, color=color, lw=2)
            ax.plot(part.estimate, y, marker, ls="none", ms=6.5, color=color,
                    mfc=color if base == "B1_TUNED" else "white", mew=1.6, label=label)
            for yi, (_, r) in zip(y, part.iterrows(), strict=True):
                ax.annotate(f.format(r.estimate), (r.ci_hi, yi), xytext=(5, 0), textcoords="offset points",
                            va="center", fontsize=7.5, color=viz.INK_2)
    for ax, keys, unit in ((axes[0], pct_names, "% (positive = optimiser better)"),
                           (axes[1], ["fill_rate_delta_pts"], "pts (positive = optimiser better)")):
        ax.axvline(0, color=viz.AXIS, lw=1)
        y = np.arange(len(keys))[::-1]
        ax.set_yticks(y, [names[i] for i in keys])
        ax.set_xlabel(unit)
        ax.grid(axis="y", visible=False)
        lo = min(sm.set_index("metric").loc[keys, "ci_lo"].min() for sm in sums.values())
        hi = max(sm.set_index("metric").loc[keys, "ci_hi"].max() for sm in sums.values())
        span = max(abs(lo), abs(hi), 1e-9) * 1.3
        ax.set_xlim(-span, span)
        ax.set_ylim(-0.6, len(keys) - 0.4)
    axes[1].yaxis.tick_right()
    fig.legend(*axes[0].get_legend_handles_labels(), loc="upper left", bbox_to_anchor=(0.01, 0.935), ncol=2,
               fontsize=8.5, frameon=False)
    fig.suptitle(f"Optimiser vs two baselines: paired Monte Carlo, N = {n} demand paths (mean, 95% bootstrap CI)",
                 x=0.01, ha="left", fontsize=11, color=viz.INK)
    viz.source_note(fig, f"{LABEL.capitalize()}. Demand paths: actual Favorita test-year demand + block-bootstrapped "
                         "forecast errors (ADR-008); every planner sees identical paths. Baselines: ADR-006, ADR-009.")
    fig.tight_layout(rect=(0, 0.04, 1, 0.89))
    fig.savefig(out, dpi=150)


def replay_compare(rep: pd.DataFrame, base: str) -> dict:
    b, o = rep.loc[base], rep.loc["OPT"]
    return {"expired_waste_reduction_pct": 100 * (1 - o.expired_cases / b.expired_cases),
            "lost_cases_reduction_pct": 100 * (1 - o.lost_cases / b.lost_cases),
            "fill_rate_delta_pts": 100 * (o.fill_rate - b.fill_rate),
            "changeover_hours_reduction_pct": 100 * (1 - o.changeover_hours / b.changeover_hours),
            "evaluated_cost_reduction_pct": 100 * (1 - o.evaluated_cost / b.evaluated_cost)}


def mc_dict(s: pd.DataFrame) -> dict:
    return {r.metric: {k: (round(float(r[k]), 4) if isinstance(r[k], float | np.floating) else r[k])
                       for k in ("estimate", "ci_lo", "ci_hi", "n", "effect_size_dz", "wilcoxon_p")}
            for _, r in s.iterrows()}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run")
    ap.add_argument("--out", help="write headline JSON here instead of results/headline_numbers.json (quick checks)")
    a = ap.parse_args()
    run = Path(a.run) if a.run else max((ROOT / "results" / "experiments").glob("main_*/kpis.parquet"),
                                        key=lambda p: p.stat().st_mtime).parent
    df = pd.read_parquet(run / "kpis.parquet")
    meta = json.loads((run / "meta.json").read_text())
    head = "B1_TUNED" if "B1_TUNED" in set(df.arm) else "B1"       # ADR-009: headline = validation-tuned baseline
    sums = {base: summarise_experiment(df, base=base) for base in dict.fromkeys([head, "B1"])}
    s = sums[head]
    if not a.out:
        pd.concat(sums.values(), ignore_index=True).round(4).to_csv(ROOT / "results" / "experiment_summary.csv",
                                                                    index=False)
    rep = df[df.layer == "replay"].set_index("arm")
    level_cols = ("expired_pct", "fill_rate", "lost_cases", "changeover_hours", "allergen_clean_hours", "utilisation")
    replay = {**{k: round(float(v), 4) for k, v in replay_compare(rep, head).items()},
              **{arm: {c: round(float(rep.loc[arm, c]), 4) for c in level_cols} for arm in rep.index}}
    mcd = df[df.layer == "mc"]
    arm_means = {arm: {c: round(float(g[c].mean()), 4) for c in level_cols} for arm, g in mcd.groupby("arm")}
    for arm in arm_means:
        arm_means[arm]["changeover_hours_per_week"] = round(arm_means[arm]["changeover_hours"] / 52, 2)
    mc = mc_dict(s)
    fc_ma4, fc_sn = forecast_improvement("ma4"), forecast_improvement("seasonal_naive")
    out = {
        "label": LABEL,
        "note": "Generated by scripts/analyze_experiment.py. The ONLY source for README/resume numbers. "
                "Estimates are means with 95% percentile-bootstrap CIs over paired demand paths (Monte Carlo) "
                "or over forecast origins (forecast accuracy). Reductions: positive = optimiser better. "
                "Headline baseline = B1 tuned on the validation year (ADR-009); *_vs_b1_default = ADR-006 rule.",
        "baseline_headline": head,
        "b1_tuned_cover_weeks": X.tuned_b1_cover() if head == "B1_TUNED" else None,
        "experiment_run_id": meta["run_id"], "n_paths": meta["n_paths"], "seed": meta["seed"],
        "kpi_sha256": meta["kpi_sha256"], "git_hash": meta.get("git_hash"), "source_sha256": meta["source_sha256"],
        "monte_carlo": mc,
        "expired_waste_reduction_pct": mc["expired_waste_reduction_pct"],
        "fill_rate_delta_pts": mc["fill_rate_delta_pts"],
        "changeover_hours_reduction_pct": mc["changeover_hours_reduction_pct"],
        "monte_carlo_arm_means": arm_means,
        "forecast_wape_improvement_pct": {**fc_ma4, "note": "vs 4-week moving average (strongest benchmark; "
                                                           "B1's own forecast), test year"},
        "forecast_wape_improvement_vs_seasonal_naive_pct": fc_sn,
        "replay_layer_a": replay,
        "forecast_interval_coverage": {f"{int(100 * r.level)}": round(float(r.empirical), 4) for r in
                                       pd.read_csv(FC / "interval_coverage.csv").itertuples()},
        "replay_runtime_s": float(pd.read_csv(ROOT / "results" / "optimized_replay.csv").runtime_s.iloc[0]),
        "checker_violations_total": meta["checker_violations_total"],
        "fallback_weeks_total": meta["fallback_weeks_total"],
    }
    if head != "B1":
        out["monte_carlo_vs_b1_default"] = mc_dict(sums["B1"])
        out["replay_vs_b1_default"] = {k: round(float(v), 4) for k, v in replay_compare(rep, "B1").items()}
    old = Path(a.out) if a.out else ROOT / "results" / "headline_numbers.json"
    if old.exists():   # keep sections other scripts own (e.g. sensitivity, T5.2.2)
        prev = json.loads(old.read_text())
        for key in ("sensitivity_min_waste_reduction_pct", "share_of_cells_improved", "sensitivity"):
            if key in prev:
                out[key] = prev[key]
    old.write_text(json.dumps(out, indent=2), encoding="utf-8")
    if not a.out:
        plot(sums, ROOT / "results" / "figures" / "kpi_comparison.png", int(meta["n_paths"]))
    for base, sm in sums.items():
        print(f"--- OPT vs {base}")
        print(sm[["metric", "estimate", "ci_lo", "ci_hi", "effect_size_dz"]].round(3).to_string(index=False))
    print("arm means:", json.dumps(arm_means, indent=1))
    print("forecast vs MA4:", {k: round(v, 2) for k, v in fc_ma4.items() if isinstance(v, float)})
    print("replay:", json.dumps(out["replay_layer_a"]), json.dumps(out.get("replay_vs_b1_default")))


if __name__ == "__main__":
    main()
