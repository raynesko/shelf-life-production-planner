"""Baseline planner B1: a competent spreadsheet planner, not a strawman (T4.1.2; docs/methods/baseline.md).

Each week t, for every SKU p:
  forecast_p   = mean of the last 4 observed weeks of demand (4-week moving average)
  reorder test : produce only if usable on-hand_p < forecast_p x reorder_weeks   (reorder point s; ADR-006)
  target_p     = forecast_p * (1 + cover_weeks)            (order-up-to level S: this week + fixed cover)
  produce_p    = target_p - usable on-hand_p               (nets inventory)
  run rules    : raise to the minimum run, cap at the maximum run.
With reorder_weeks = cover_weeks = 1 this settles into a natural two-week cycle per SKU, the way a
competent planner avoids running (and cleaning for) every SKU every week.
Sequence: fixed static allergen ladder (fewest allergens first, most last; ties by allergen set
then SKU id), so the wet clean falls at the end of the weekly cycle.
Capacity (ADR-010, run-out priority): if run + changeover hours exceed available hours, scale the planned runs
pro rata; if that would push any run below its minimum run, defer the SKU with the most usable cover (weeks of
forecast on hand) to next week instead, and repeat. This is how a planner sheds load: SKUs that can wait,
wait; the most urgent keep their runs. (The pre-ADR-010 rule cut every run pro rata at once, which could
drop all runs together and starve the line when changeovers were long.)
Deliberately NOT done: shelf-life-aware sizing, dynamic sequencing, safety stock from forecast error.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from shelflife.plant.config import PlantConfig
from shelflife.sim.engine import PlantState, SimPlant, WeekPlan


def allergen_ladder(cfg: PlantConfig) -> list[int]:
    keyed = [(len(s.allergens), tuple(sorted(s.allergens)), s.id, i) for i, s in enumerate(cfg.skus)]
    return [k[-1] for k in sorted(keyed)]


def sequence_hours(plant: SimPlant, order: list[int], last: int | None) -> float:
    h, prev = 0.0, last
    for p in order:
        if prev is not None and prev != p:
            h += plant.changeover_hours[prev, p]
        prev = p
    return h


@dataclass
class BaselineB1:
    plant: SimPlant
    ladder: list[int]
    min_run_cases: np.ndarray
    max_run_cases: np.ndarray
    cover_weeks: float = 1.0
    ma_weeks: int = 4
    reorder_weeks: float = 1.0

    @classmethod
    def from_config(cls, cfg: PlantConfig, plant: SimPlant, cover_weeks: float = 1.0) -> BaselineB1:
        d = cfg.sku_defaults
        return cls(plant, allergen_ladder(cfg), plant.rate * d.min_run_hours.value,
                   plant.rate * d.max_run_hours.value, cover_weeks)

    def forecast(self, observed: np.ndarray) -> np.ndarray:
        if observed.shape[1] == 0:
            return np.zeros(self.plant.n)
        return observed[:, -self.ma_weeks:].mean(axis=1)

    def quantities(self, state: PlantState, observed: np.ndarray) -> np.ndarray:
        f = self.forecast(observed)
        on_hand = state.usable_on_hand()
        q = np.where(on_hand < f * self.reorder_weeks - 1e-9,
                     np.maximum(0.0, f * (1 + self.cover_weeks) - on_hand), 0.0)
        q = np.where(q > 0, np.clip(q, self.min_run_cases, self.max_run_cases), 0.0)
        return q

    def fit_capacity(self, q: np.ndarray, last: int | None, cover: np.ndarray | None = None) -> np.ndarray:
        """Fit the week into line hours; `cover` = usable on-hand / forecast, highest deferred first."""
        plant = self.plant
        q = q.copy()
        cover = np.zeros(plant.n) if cover is None else cover
        while q.any():
            order = [p for p in self.ladder if q[p] > 0]
            co = sequence_hours(plant, order, last)
            run = float(np.sum(q / plant.rate))
            if run + co <= plant.available_hours + 1e-9:
                return q
            scaled = q * max(plant.available_hours - co, 0.0) / run
            on = q > 0
            if np.all(scaled[on] + 1e-9 >= self.min_run_cases[on]):
                return scaled
            q[int(np.argmax(np.where(on, cover, -np.inf)))] = 0.0      # defer the SKU that can wait longest
        return q

    def __call__(self, state: PlantState, observed: np.ndarray) -> WeekPlan:
        f = self.forecast(observed)
        cover = state.usable_on_hand() / np.maximum(f, 1e-9)
        q = self.fit_capacity(self.quantities(state, observed), state.last_sku, cover)
        return [(p, float(q[p])) for p in self.ladder if q[p] > 0]
