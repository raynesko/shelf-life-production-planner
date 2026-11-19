"""Weekly plant simulator with age cohorts, FEFO and KPI accounting (T4.1.1).

Timing within week t (ADR-004):
  1. Execute the run sequence: production enters inventory as an age-0 cohort (usable this week).
     Changeover hours are charged for each SKU switch, including from last week's final SKU.
  2. Ship FEFO (oldest first), only from cohorts whose age a (weeks) satisfies a <= A_p, where
     A_p = floor((1 - MSL) * shelf_life_days / 7) is the oldest age that still leaves the minimum
     remaining shelf life at shipment. Unmet demand is lost (no backorders).
  3. Cohorts with a >= A_p that were not shipped can never ship again -> written off as expired
     (unsaleable) waste.
  4. Remaining cohorts age by one week.
Demand is rounded to whole cases; production quantities are used as given.
"""
from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from shelflife.plant.changeover import ChangeoverMatrix
from shelflife.plant.config import PlantConfig

# One week's plan: run order of (sku_index, cases). Zero/negative quantities are ignored.
WeekPlan = Sequence[tuple[int, float]]

SKU_WEEK_COLS = ["week", "sku_id", "demand", "produced", "shipped", "lost", "expired",
                 "end_inventory", "ship_age_weighted"]
SHIP_COLS = ["week", "sku_id", "age", "qty"]
AGE_COLS = ["week", "sku_id", "age", "qty"]          # end-of-week stock by age (weeks) after ageing
PLAN_COLS = ["week", "position", "sku_id", "qty", "changeover_hours_before", "clean_type"]
WEEK_COLS = ["week", "run_hours", "changeover_hours", "allergen_clean_hours", "n_changeovers",
             "available_hours", "utilisation", "capacity_breach", "last_sku"]


@dataclass(frozen=True)
class SimPlant:
    sku_ids: list[str]
    shelf_life_days: np.ndarray
    rate: np.ndarray                 # cases per run hour
    available_hours: float
    msl: float                       # min remaining shelf life at shipment (fraction)
    changeover_hours: np.ndarray     # [i, j]
    allergen_clean: np.ndarray       # [i, j] bool

    @property
    def n(self) -> int:
        return len(self.sku_ids)

    @property
    def max_ship_age(self) -> np.ndarray:
        return np.floor((1 - self.msl) * self.shelf_life_days / 7 + 1e-9).astype(int)

    @classmethod
    def from_config(cls, cfg: PlantConfig, matrix: ChangeoverMatrix, *,
                    msl: float | None = None, available_hours: float | None = None,
                    shelf_life_scale: float = 1.0) -> SimPlant:
        assert matrix.sku_ids == [s.id for s in cfg.skus], "matrix/config SKU order mismatch"
        return cls(
            sku_ids=[s.id for s in cfg.skus],
            shelf_life_days=np.array([s.shelf_life_days for s in cfg.skus], float) * shelf_life_scale,
            rate=np.array([s.rate for s in cfg.skus], float),
            available_hours=available_hours or cfg.line.weekly_available_hours.value,
            msl=cfg.line.min_remaining_shelf_life_at_ship.value if msl is None else msl,
            changeover_hours=matrix.hours,
            allergen_clean=matrix.needs_allergen_clean,
        )


@dataclass
class SimResult:
    sku_week: pd.DataFrame
    week: pd.DataFrame
    initial_inventory: float
    ending_cohorts: list[dict[int, float]]
    shipments: pd.DataFrame = field(default_factory=lambda: pd.DataFrame(columns=SHIP_COLS))
    inventory_age: pd.DataFrame = field(default_factory=lambda: pd.DataFrame(columns=AGE_COLS))


class PlantState:
    """Mutable week-by-week simulator state; `step` executes one week (see module docstring)."""

    def __init__(self, plant: SimPlant, initial_inventory: list[dict[int, float]] | None = None,
                 initial_last_sku: int | None = None):
        self.plant = plant
        self.inv: list[dict[int, float]] = (
            [dict(c) for c in initial_inventory] if initial_inventory else [{} for _ in range(plant.n)])
        self.initial_total = sum(sum(c.values()) for c in self.inv)
        self.last_sku = initial_last_sku
        self.t = 0
        self.rows: list[list] = []
        self.wrows: list[list] = []
        self.ship_log: list[list] = []
        self.age_log: list[list] = []

    def usable_on_hand(self) -> np.ndarray:
        """Cases per SKU that may still ship this week (age <= max ship age)."""
        A = self.plant.max_ship_age
        return np.array([sum(q for a, q in c.items() if a <= A[p]) for p, c in enumerate(self.inv)])

    def step(self, week_plan: WeekPlan, demand_t: np.ndarray) -> None:
        plant, A, t = self.plant, self.plant.max_ship_age, self.t
        demand_t = np.rint(np.asarray(demand_t, float)).clip(min=0)
        produced = np.zeros(plant.n)
        run_h = co_h = ac_h = 0.0
        n_co = 0
        last = self.last_sku
        for p, q in week_plan:
            if q <= 0:
                continue
            if last is not None and last != p:
                co_h += plant.changeover_hours[last, p]
                n_co += 1
                if plant.allergen_clean[last, p]:
                    ac_h += plant.changeover_hours[last, p]
            run_h += q / plant.rate[p]
            produced[p] += q
            last = p
        self.last_sku = last
        used = run_h + co_h
        self.wrows.append([t, run_h, co_h, ac_h, n_co, plant.available_hours,
                           used / plant.available_hours, used > plant.available_hours + 1e-9,
                           plant.sku_ids[last] if last is not None else None])

        for p in range(plant.n):
            coh = self.inv[p]
            if produced[p] > 0:
                coh[0] = coh.get(0, 0.0) + produced[p]
            need, shipped, age_w = demand_t[p], 0.0, 0.0
            for a in sorted(coh, reverse=True):          # FEFO: oldest first
                if a > A[p] or need <= 0:
                    continue
                take = min(coh[a], need)
                coh[a] -= take
                need -= take
                shipped += take
                age_w += take * a
                if take > 0:
                    self.ship_log.append([t, plant.sku_ids[p], a, take])
            expired = sum(q for a, q in coh.items() if a >= A[p])
            self.inv[p] = {a + 1: q for a, q in coh.items() if a < A[p] and q > 1e-9}
            self.age_log.extend([t, plant.sku_ids[p], a, q] for a, q in sorted(self.inv[p].items()))
            self.rows.append([t, plant.sku_ids[p], demand_t[p], produced[p], shipped,
                              demand_t[p] - shipped, expired, sum(self.inv[p].values()), age_w])
        self.t += 1

    def result(self) -> SimResult:
        return SimResult(pd.DataFrame(self.rows, columns=SKU_WEEK_COLS),
                         pd.DataFrame(self.wrows, columns=WEEK_COLS), self.initial_total,
                         [dict(c) for c in self.inv], pd.DataFrame(self.ship_log, columns=SHIP_COLS),
                         pd.DataFrame(self.age_log, columns=AGE_COLS))


def simulate(plant: SimPlant, plan: Sequence[WeekPlan], demand: np.ndarray, *,
             initial_inventory: list[dict[int, float]] | None = None,
             initial_last_sku: int | None = None) -> SimResult:
    """Replay a fixed plan. demand: array (n_sku, n_weeks); plan: one WeekPlan per week."""
    demand = np.asarray(demand, float)
    if demand.shape[0] != plant.n or len(plan) != demand.shape[1]:
        raise ValueError(f"shape mismatch: demand {demand.shape}, plan weeks {len(plan)}, skus {plant.n}")
    st = PlantState(plant, initial_inventory, initial_last_sku)
    for t in range(demand.shape[1]):
        st.step(plan[t], demand[:, t])
    return st.result()


# A policy sees the state *before* week t and the demand observed in weeks < t only.
Policy = Callable[[PlantState, np.ndarray], WeekPlan]


def simulate_policy(plant: SimPlant, policy: Policy, demand: np.ndarray, history: np.ndarray, *,
                    initial_inventory: list[dict[int, float]] | None = None,
                    initial_last_sku: int | None = None) -> tuple[SimResult, list[WeekPlan]]:
    """Run a reactive policy. `history` (n_sku, k) is demand before week 0; the policy at week t
    receives history plus demand of weeks 0..t-1 (never week t or later)."""
    demand = np.asarray(demand, float)
    st = PlantState(plant, initial_inventory, initial_last_sku)
    plans: list[WeekPlan] = []
    for t in range(demand.shape[1]):
        observed = np.concatenate([np.asarray(history, float), demand[:, :t]], axis=1)
        wp = list(policy(st, observed))
        plans.append(wp)
        st.step(wp, demand[:, t])
    return st.result(), plans


def plan_from_frame(df: pd.DataFrame, sku_ids: list[str], n_weeks: int) -> list[list[tuple[int, float]]]:
    """Convert a plan table (week, position, sku_id, qty) to the simulator's list form."""
    idx = {s: i for i, s in enumerate(sku_ids)}
    out: list[list[tuple[int, float]]] = [[] for _ in range(n_weeks)]
    for r in df.sort_values(["week", "position"]).itertuples():
        out[int(r.week)].append((idx[r.sku_id], float(r.qty)))
    return out


def plan_to_frame(plans: Sequence[WeekPlan], plant: SimPlant,
                  initial_last_sku: int | None = None) -> pd.DataFrame:
    """Standard plan table (PLAN_COLS) used by baseline, optimiser, checker and dashboard.
    changeover_hours_before / clean_type describe the switch into each run, incl. carry-over."""
    rows, last = [], initial_last_sku
    for t, wp in enumerate(plans):
        pos = 0
        for p, q in wp:
            if q <= 0:
                continue
            if last is None or last == p:
                h, kind = 0.0, "none"
            else:
                h = float(plant.changeover_hours[last, p])
                kind = "allergen" if plant.allergen_clean[last, p] else "routine"
            rows.append([t, pos, plant.sku_ids[p], float(q), h, kind])
            pos += 1
            last = p
    return pd.DataFrame(rows, columns=PLAN_COLS)
