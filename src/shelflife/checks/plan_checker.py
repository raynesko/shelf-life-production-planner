"""Independent plan feasibility checker (T4.3.3).

Re-validates ANY plan (baseline or optimised) from the plant config alone. Deliberately imports nothing
from shelflife.opt, shelflife.sim or shelflife.plant.changeover; the allergen rule and changeover times
are re-derived here so a bug in those modules cannot hide a bad plan.

Plan table columns: week, position, sku_id, qty, changeover_hours_before, clean_type
Optional shipments table: week, sku_id, age, qty (age in weeks at shipment)

CLI: python -m shelflife.checks.plan_checker <plan.parquet|csv> [--shipments file] [--last SKU-ID]
"""
from __future__ import annotations

import argparse
import math
import sys
from dataclasses import dataclass

import pandas as pd

from shelflife.plant.config import PlantConfig, load

TOL = 1e-6


@dataclass
class Violation:
    rule: str
    week: int | None
    sku_id: str | None
    message: str

    def __str__(self) -> str:
        return f"[{self.rule}] week={self.week} sku={self.sku_id}: {self.message}"


def _expected_switch(cfg: PlantConfig, frm: str | None, to: str) -> tuple[float, str]:
    if frm is None or frm == to:
        return 0.0, "none"
    sk = {s.id: s for s in cfg.skus}
    co = cfg.changeover_hours
    if set(sk[frm].allergens) - set(sk[to].allergens):
        return co.base.value + co.allergen_clean.value, "allergen"
    return co.base.value + co.routine_clean.value, "routine"


def check(plan: pd.DataFrame, cfg: PlantConfig | None = None, *, initial_last_sku: str | None = None,
          shipments: pd.DataFrame | None = None, available_hours: float | None = None,
          msl: float | None = None, changeover_scale: float = 1.0,
          shelf_life_scale: float = 1.0) -> list[Violation]:
    cfg = cfg or load()
    sk = {s.id: s for s in cfg.skus}
    K = available_hours if available_hours is not None else cfg.line.weekly_available_hours.value
    msl = msl if msl is not None else cfg.line.min_remaining_shelf_life_at_ship.value
    d = cfg.sku_defaults
    out: list[Violation] = []

    unknown = set(plan.sku_id) - set(sk)
    if unknown:
        return [Violation("unknown_sku", None, s, "SKU not in plant config") for s in sorted(unknown)]

    last = initial_last_sku
    for week, g in plan.sort_values(["week", "position"]).groupby("week"):
        if list(g.position) != list(range(len(g))):
            out.append(Violation("positions", int(week), None, f"positions not 0..n-1: {list(g.position)}"))
        run_h = co_h = 0.0
        for r in g.itertuples():
            s = sk[r.sku_id]
            if r.qty <= 0:
                out.append(Violation("non_positive_qty", int(week), r.sku_id, f"qty={r.qty}"))
                continue
            hours = r.qty / s.rate
            if hours < d.min_run_hours.value - TOL:
                out.append(Violation("min_run", int(week), r.sku_id,
                                     f"run {hours:.2f} h < minimum {d.min_run_hours.value} h"))
            if hours > d.max_run_hours.value + TOL:
                out.append(Violation("max_run", int(week), r.sku_id,
                                     f"run {hours:.2f} h > maximum {d.max_run_hours.value} h"))
            exp_h, exp_kind = _expected_switch(cfg, last, r.sku_id)
            exp_h *= changeover_scale
            if exp_kind != r.clean_type:
                rule = "missing_allergen_clean" if exp_kind == "allergen" else "clean_type"
                out.append(Violation(rule, int(week), r.sku_id,
                                     f"switch {last}->{r.sku_id} requires '{exp_kind}', "
                                     f"plan says '{r.clean_type}'"))
            if abs(exp_h - r.changeover_hours_before) > TOL:
                out.append(Violation("changeover_accounting", int(week), r.sku_id,
                                     f"switch {last}->{r.sku_id} is {exp_h:.2f} h, plan says "
                                     f"{r.changeover_hours_before:.2f} h"))
            run_h += hours
            co_h += exp_h
            last = r.sku_id
        if run_h + co_h > K + TOL:
            out.append(Violation("capacity", int(week), None,
                                 f"run {run_h:.2f} h + changeover {co_h:.2f} h > available {K} h"))
        dup = g.sku_id[g.sku_id.duplicated()].unique()
        for s_id in dup:
            out.append(Violation("duplicate_run", int(week), s_id, "SKU run more than once in a week"))

    if shipments is not None and len(shipments):
        for r in shipments.itertuples():
            L = sk[r.sku_id].shelf_life_days * shelf_life_scale
            max_age = math.floor((1 - msl) * L / 7 + 1e-9)
            if r.age > max_age:
                out.append(Violation("shelf_life_at_ship", int(r.week), r.sku_id,
                                     f"shipped at age {r.age} wk; remaining life {L - 7 * r.age} d < "
                                     f"{msl:.0%} of {L} d (max age {max_age} wk)"))
    return out


def _read(path: str) -> pd.DataFrame:
    return pd.read_parquet(path) if path.endswith(".parquet") else pd.read_csv(path)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Independent plan feasibility checker")
    ap.add_argument("plan")
    ap.add_argument("--shipments")
    ap.add_argument("--last", help="SKU id last run before the plan starts")
    a = ap.parse_args(argv)
    v = check(_read(a.plan), initial_last_sku=a.last,
              shipments=_read(a.shipments) if a.shipments else None)
    print("PASS" if not v else f"FAIL ({len(v)} violations)")
    for x in v:
        print(" ", x)
    return 0 if not v else 1


if __name__ == "__main__":
    sys.exit(main())
