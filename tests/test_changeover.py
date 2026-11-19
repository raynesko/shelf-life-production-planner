import numpy as np
import pytest

from shelflife.plant.changeover import ALLERGEN, ROUTINE, build_matrix, needs_allergen_clean
from shelflife.plant.config import load

# 10 hand-written pairs: (from allergens, to allergens, expected allergen clean?)
PAIRS = [
    (["milk"], ["milk", "soy"], False),          # subset -> superset: residue is declared
    (["milk", "soy"], ["milk"], True),           # soy residue undeclared on j
    ([], ["milk"], False),                       # allergen-free -> anything
    ([], [], False),
    (["milk"], [], True),
    (["sesame"], ["milk"], True),
    (["egg"], ["wheat", "egg"], False),
    (["fish", "egg"], ["egg"], True),
    (["milk", "tree_nuts"], ["milk", "tree_nuts"], False),  # identical profile
    (["wheat", "egg"], ["fish", "egg"], True),   # wheat residue undeclared
]


@pytest.mark.parametrize("a,b,expected", PAIRS)
def test_rule_pairs(a, b, expected):
    assert needs_allergen_clean(a, b) is expected


@pytest.fixture(scope="module")
def setup():
    cfg = load()
    return cfg, build_matrix(cfg)


def test_diagonal_zero(setup):
    _, m = setup
    assert np.all(np.diag(m.hours) == 0)


def test_matrix_matches_rule_and_times(setup):
    cfg, m = setup
    co = cfg.changeover_hours
    for i, a in enumerate(cfg.skus):
        for j, b in enumerate(cfg.skus):
            if i == j:
                continue
            if needs_allergen_clean(a.allergens, b.allergens):
                assert m.clean_type[i, j] == ALLERGEN
                assert m.hours[i, j] == pytest.approx(co.base.value + co.allergen_clean.value)
            else:
                assert m.clean_type[i, j] == ROUTINE
                assert m.hours[i, j] == pytest.approx(co.base.value + co.routine_clean.value)


def test_asymmetric_where_rule_says(setup):
    _, m = setup
    i, j = m.index("SKU-01"), m.index("SKU-04")   # milk -> milk+egg: no allergen clean
    assert not m.needs_allergen_clean[i, j]
    assert m.needs_allergen_clean[j, i]            # milk+egg -> milk: egg residue
    assert m.hours[i, j] < m.hours[j, i]


def test_scale(setup):
    cfg, m = setup
    assert np.allclose(build_matrix(cfg, scale=2.0).hours, 2 * m.hours)
