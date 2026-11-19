"""KPI functions; definitions are binding: docs/research/kpi_definitions.md."""
from __future__ import annotations

import numpy as np

from shelflife.sim.engine import SimResult


def expired_cases(r: SimResult) -> float:
    return float(r.sku_week["expired"].sum())


def expired_pct_produced(r: SimResult) -> float:
    prod = r.sku_week["produced"].sum()
    return float(100 * r.sku_week["expired"].sum() / prod) if prod > 0 else float("nan")


def fill_rate(r: SimResult) -> float:
    d = r.sku_week["demand"].sum()
    return float(r.sku_week["shipped"].sum() / d) if d > 0 else float("nan")


def lost_cases(r: SimResult) -> float:
    return float(r.sku_week["lost"].sum())


def stockout_sku_weeks(r: SimResult) -> int:
    return int((r.sku_week["lost"] > 1e-9).sum())


def changeover_hours(r: SimResult) -> float:
    return float(r.week["changeover_hours"].sum())


def allergen_clean_hours(r: SimResult) -> float:
    return float(r.week["allergen_clean_hours"].sum())


def utilisation(r: SimResult) -> float:
    return float(r.week["utilisation"].mean())


def weeks_of_cover(r: SimResult) -> float:
    sw = r.sku_week
    mean_d = sw.groupby("sku_id")["demand"].transform("mean")
    ok = mean_d > 0
    return float((sw.loc[ok, "end_inventory"] / mean_d[ok]).mean())


def mean_age_at_ship(r: SimResult) -> float:
    s = r.sku_week["shipped"].sum()
    return float(r.sku_week["ship_age_weighted"].sum() / s) if s > 0 else float("nan")


def summarise(r: SimResult) -> dict[str, float]:
    return {
        "expired_cases": expired_cases(r),
        "expired_pct": expired_pct_produced(r),
        "fill_rate": fill_rate(r),
        "lost_cases": lost_cases(r),
        "stockout_sku_weeks": stockout_sku_weeks(r),
        "changeover_hours": changeover_hours(r),
        "allergen_clean_hours": allergen_clean_hours(r),
        "utilisation": utilisation(r),
        "weeks_of_cover": weeks_of_cover(r),
        "mean_age_ship": mean_age_at_ship(r),
        "end_inventory_cases": float(r.sku_week.groupby("sku_id")["end_inventory"].last().sum()),
        "capacity_breach_weeks": int(np.sum(r.week["capacity_breach"])),
    }


def evaluated_cost(r: SimResult, costs: dict[str, float]) -> float:
    """Simulator-evaluated objective with the optimiser's own weights (configs/costs.yaml; relative units, never
    reported as money). Used to choose planner variants on the VALIDATION year (ADR-007)."""
    sw, wk = r.sku_week, r.week
    return float(costs["production_per_case"] * sw.produced.sum() + costs["lost_sale_per_case"] * sw.lost.sum()
                 + costs["expiry_per_case"] * sw.expired.sum()
                 + costs["holding_per_case_week"] * sw.end_inventory.sum()
                 + costs["changeover_per_hour"] * wk.changeover_hours.sum())

