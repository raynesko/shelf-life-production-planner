import copy

import pytest
import yaml
from pydantic import ValidationError

from shelflife.plant import config as C


def raw():
    return yaml.safe_load(C.DEFAULT_PATH.read_text(encoding="utf-8"))


def test_loads_12_skus():
    cfg = C.load()
    assert len(cfg.skus) == 12
    assert all(14 <= s.shelf_life_days <= 56 for s in cfg.skus)


def test_allergens_big9_only():
    d = copy.deepcopy(raw())
    d["skus"][0]["allergens"] = ["gluten"]
    with pytest.raises(ValidationError):
        C.PlantConfig.model_validate(d)


def test_missing_source_rejected():
    d = copy.deepcopy(raw())
    d["line"]["weekly_available_hours"]["source"] = " "
    with pytest.raises(ValidationError):
        C.PlantConfig.model_validate(d)


def test_shelf_life_outside_weekly_validity_rejected():
    d = copy.deepcopy(raw())
    d["skus"][0]["shelf_life_days"] = 7
    with pytest.raises(ValidationError):
        C.PlantConfig.model_validate(d)


def test_value_must_be_in_range():
    d = copy.deepcopy(raw())
    d["changeover_hours"]["base"]["value"] = 5
    with pytest.raises(ValidationError):
        C.PlantConfig.model_validate(d)
