"""Plant configuration schema (T2.2.1). Run: python -m shelflife.plant.config --report"""
from __future__ import annotations

import argparse
from pathlib import Path

import yaml
from pydantic import BaseModel, field_validator, model_validator

BIG9 = {"milk", "egg", "fish", "crustacean_shellfish", "tree_nuts", "peanuts", "wheat", "soy",
        "sesame"}
DEFAULT_PATH = Path(__file__).resolve().parents[3] / "configs" / "plant.yaml"


class Param(BaseModel):
    value: float
    source: str
    range: tuple[float, float]

    @field_validator("source")
    @classmethod
    def _source_nonempty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("every parameter needs a non-empty source")
        return v

    @model_validator(mode="after")
    def _in_range(self) -> Param:
        lo, hi = self.range
        if not lo <= self.value <= hi:
            raise ValueError(f"value {self.value} outside range {self.range}")
        return self


class Line(BaseModel):
    weekly_available_hours: Param
    min_remaining_shelf_life_at_ship: Param
    horizon_weeks: Param


class Changeover(BaseModel):
    base: Param
    routine_clean: Param
    allergen_clean: Param


class SkuDefaults(BaseModel):
    rate_cases_per_hour: Param
    unit_cost_per_case: Param
    min_run_hours: Param
    max_run_hours: Param


class Sku(BaseModel):
    id: str
    name: str
    family: str
    allergens: list[str]
    shelf_life_days: int
    rate: float
    allergen_rationale: str

    @field_validator("allergens")
    @classmethod
    def _big9_only(cls, v: list[str]) -> list[str]:
        bad = set(v) - BIG9
        if bad:
            raise ValueError(f"not FDA major allergens: {sorted(bad)}")
        return v

    @field_validator("shelf_life_days")
    @classmethod
    def _weekly_valid(cls, v: int) -> int:
        if not 14 <= v <= 56:
            raise ValueError("shelf life must be 14-56 days (weekly-bucket model validity)")
        return v


class PlantConfig(BaseModel):
    line: Line
    changeover_hours: Changeover
    sku_defaults: SkuDefaults
    skus: list[Sku]
    sku_param_sources: dict[str, dict[str, str]]

    @model_validator(mode="after")
    def _checks(self) -> PlantConfig:
        ids = [s.id for s in self.skus]
        if len(set(ids)) != len(ids):
            raise ValueError("duplicate SKU ids")
        for k in ("shelf_life_days", "rate", "allergens"):
            if not self.sku_param_sources.get(k, {}).get("source", "").strip():
                raise ValueError(f"missing source for per-SKU parameter '{k}'")
        return self


def load(path: Path | str = DEFAULT_PATH) -> PlantConfig:
    with open(path, encoding="utf-8") as f:
        return PlantConfig.model_validate(yaml.safe_load(f))


def report(cfg: PlantConfig) -> str:
    params = {}
    for grp in (cfg.line, cfg.changeover_hours, cfg.sku_defaults):
        params.update(grp.model_dump())
    n_assump = sum(1 for p in params.values() if p["source"].startswith("assumption"))
    return "\n".join([
        f"SKUs: {len(cfg.skus)}  families: {sorted({s.family for s in cfg.skus})}",
        f"scalar parameters: {len(params)}  with source starting 'assumption': {n_assump}",
        f"per-SKU parameter classes with sources: {len(cfg.sku_param_sources)}"
        " (all assumption-based; shelf-life FoodKeeper cross-check pending)",
    ])


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--path", default=str(DEFAULT_PATH))
    a = ap.parse_args()
    c = load(a.path)
    print(report(c) if a.report else "OK")
