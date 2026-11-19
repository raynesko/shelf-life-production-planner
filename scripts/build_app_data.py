"""T6.1.1/T6.1.2: export the small files the Streamlit app reads (results/app_data/, committed, <= 20 MB).

Re-runs the test-year replay (Layer A) for tuned B1 (headline baseline, ADR-009), rule-of-thumb B1 and OPT
with the experiment engine and saves:
  plans.csv            week, position, sku_id, qty, changeover_hours_before, clean_type, arm
  inventory_age.csv    end-of-week stock by age (weeks) per SKU, arm
  sku_kpis.csv         per SKU and arm: produced, expired, lost, fill rate, expired % of produced
  weekly_kpis.csv      per week and arm: expired, lost, changeover and allergen-clean hours, utilisation
  sku_info.csv         SKU master (name, family, allergens, shelf life, max ship age)
  forecast_<SKU>.png   rendered actual-vs-forecast chart per SKU (test year, 80% band)
Weekly demand itself is NOT exported as a table (Favorita redistribution rule, see .gitignore).
Run: python scripts/build_app_data.py
"""
from __future__ import annotations

import shutil
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import norm

from shelflife import viz
from shelflife.analysis import experiment as X
from shelflife.opt.rolling import run_arm
from shelflife.sim.engine import plan_to_frame

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "app_data"


def forecast_pngs(ctx: X.Context) -> None:
    fc = pd.read_parquet(X.FC / "forecasts_test.parquet")
    sig = pd.read_csv(X.FC / "error_sigma.csv")
    z = norm.ppf(0.9)
    viz.apply_style()
    for sku in ctx.plant.sku_ids:
        g = fc[(fc.sku_id == sku) & (fc.horizon == 1)].sort_values("target_week")
        s1 = float(sig[(sig.sku_id == sku) & (sig.horizon == 1)].sigma.iloc[0])
        k = ctx.k / 1000
        fig, ax = plt.subplots(figsize=(8, 3.2))
        ax.fill_between(g.target_week, (g.yhat - z * s1).clip(lower=0) * k, (g.yhat + z * s1) * k,
                        color=viz.FAMILY_COLOR["DAIRY"], alpha=0.18, lw=0, label="80% interval (validation sigma)")
        ax.plot(g.target_week, g.yhat * k, color=viz.FAMILY_COLOR["DAIRY"], lw=1.6,
                label=f"one-week-ahead forecast ({g.source_model.iloc[0]})")
        ax.plot(g.target_week, g.y * k, color=viz.INK, lw=1.6, label="actual demand")
        ax.set_ylim(bottom=0)
        ax.set_ylabel("thousand cases / week")
        ax.legend(loc="lower left", ncol=3, fontsize=7.5)
        ax.set_title(f"{sku}: test-year demand vs forecast", loc="left")
        viz.source_note(fig, "Demand: Corporacion Favorita (Kaggle), scaled to plant cases. Simulation on a "
                             "synthetic plant model.")
        fig.tight_layout(rect=(0, 0.05, 1, 1))
        fig.savefig(OUT / f"forecast_{sku}.png", dpi=110)
        plt.close(fig)


def main() -> None:
    if OUT.exists():
        for f in OUT.iterdir():
            if f.name != ".gitkeep":
                f.unlink() if f.is_file() else shutil.rmtree(f)
    OUT.mkdir(parents=True, exist_ok=True)
    ctx = X.build_context()
    plans, ages, sku_rows, week_rows = [], [], [], []
    for arm in ("B1_TUNED", "B1", "OPT"):
        policy, _ = X._policy(ctx, arm, ctx.actual)
        r, wp = run_arm(ctx.plant, policy, ctx.actual, ctx.hist, ctx.start_inv, ctx.start_last)
        plans.append(plan_to_frame(wp, ctx.plant, ctx.start_last).assign(arm=arm))
        ages.append(r.inventory_age.assign(arm=arm))
        sw = r.sku_week.groupby("sku_id")[["demand", "produced", "shipped", "lost", "expired"]].sum()
        sw["fill_rate"] = sw.shipped / sw.demand
        sw["expired_pct_of_produced"] = 100 * sw.expired / sw.produced.where(sw.produced > 0)
        sku_rows.append(sw.drop(columns=["demand", "shipped"]).reset_index().assign(arm=arm))
        wk = r.sku_week.groupby("week")[["lost", "expired"]].sum().join(
            r.week.set_index("week")[["changeover_hours", "allergen_clean_hours", "utilisation"]])
        week_rows.append(wk.reset_index().assign(arm=arm))
    weeks = pd.Series(ctx.weeks.strftime("%Y-%m-%d"), name="week_start")
    pd.concat(plans).assign(week_start=lambda d: weeks.iloc[d.week].to_numpy()).round(2).to_csv(
        OUT / "plans.csv", index=False)
    pd.concat(ages).round(1).to_csv(OUT / "inventory_age.csv", index=False)
    pd.concat(sku_rows).round(4).to_csv(OUT / "sku_kpis.csv", index=False)
    pd.concat(week_rows).assign(week_start=lambda d: weeks.iloc[d.week].to_numpy()).round(3).to_csv(
        OUT / "weekly_kpis.csv", index=False)
    info = pd.DataFrame([{"sku_id": s.id, "name": s.name, "family": s.family, "allergens": ", ".join(s.allergens)
                          or "none", "shelf_life_days": s.shelf_life_days} for s in ctx.cfg.skus])
    info["max_ship_age_weeks"] = ctx.plant.max_ship_age
    info["rate_cases_per_hour"] = ctx.plant.rate
    info["available_hours"] = ctx.plant.available_hours
    info.to_csv(OUT / "sku_info.csv", index=False)
    forecast_pngs(ctx)
    total = sum(f.stat().st_size for f in OUT.iterdir())
    print(f"app_data: {len(list(OUT.iterdir()))} files, {total / 1e6:.2f} MB")
    assert np.isfinite(total) and total <= 20e6


if __name__ == "__main__":
    main()
