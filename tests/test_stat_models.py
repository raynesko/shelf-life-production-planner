"""T3.2.1/T3.2.2: statistical model wrappers (fast checks on synthetic series)."""
import numpy as np
import pandas as pd
import pytest

from shelflife.forecast import arima_ets as AE


@pytest.fixture(scope="module")
def hist():
    rng = np.random.default_rng(0)
    idx = pd.date_range("2014-01-06", periods=160, freq="W-MON")
    y = 200 + 30 * np.sin(2 * np.pi * np.arange(160) / 52) + rng.normal(0, 5, 160)
    return pd.Series(y, index=idx)


@pytest.mark.parametrize("name", ["arima", "ets"])
def test_models_return_h_nonnegative(hist, name):
    f = AE.MODELS[name](hist, 13)
    assert f.shape == (13,) and np.all(f >= 0) and np.isfinite(f).all()


def test_forecasts_are_clipped_at_zero():
    idx = pd.date_range("2014-01-06", periods=120, freq="W-MON")
    falling = pd.Series(np.linspace(500, 5, 120), index=idx)      # trend heads below zero
    assert np.all(AE.arima(falling, 13) >= 0)


def test_fallback_wrapper_counts_failures(hist):
    def broken(h_, h):
        return np.full(h, np.nan)
    w = AE.with_fallback(broken)
    out = w(hist, 5)
    assert w.failures == 1
    assert np.allclose(out, hist.iloc[-4:].mean())


def test_prophet_cache_hit_is_identical(hist, tmp_path, monkeypatch):
    pytest.importorskip("prophet")
    from shelflife.forecast import prophet_model as PM
    monkeypatch.setattr(PM, "CACHE", tmp_path)
    a = PM.prophet(hist, 4)
    assert len(list(tmp_path.glob("*.npy"))) == 1
    b = PM.prophet(hist, 4)
    assert np.array_equal(a, b) and np.all(a >= 0)


def _rows(window, model, sku, err):
    return pd.DataFrame({"sku_id": sku, "origin": pd.Timestamp("2016-01-04"), "horizon": [1, 2],
                         "target_week": pd.Timestamp("2016-01-04"), "y": [100.0, 100.0],
                         "yhat": [100.0 + err, 100.0 - err], "model": model, "window": window})


def test_selection_never_reads_test_window():
    from shelflife.forecast.selection import select
    val = pd.concat([_rows("validation", "ma4", "A", 10), _rows("validation", "ets", "A", 5),
                     _rows("validation", "ma4", "B", 2), _rows("validation", "ets", "B", 8)])
    per_sku, glob, _ = select(val)
    assert per_sku == {"A": "ets", "B": "ma4"}
    with pytest.raises(ValueError):
        select(pd.concat([val, _rows("test", "ma4", "A", 0)]))


def test_selection_tie_prefers_simpler_model():
    from shelflife.forecast.selection import select
    val = pd.concat([_rows("validation", "prophet", "A", 5), _rows("validation", "ma4", "A", 5)])
    assert select(val)[0] == {"A": "ma4"}


def _synthetic_sel(window, weeks, rng, skus=("A", "B"), sd=10.0):
    rows = []
    for s in skus:
        for o in weeks:
            for h in (1, 2):
                tw = o + pd.to_timedelta(7 * (h - 1), unit="D")
                y = 100.0 + rng.normal(0, sd)
                rows.append((s, o, h, tw, y, 100.0, "selected", window))
    cols = ["sku_id", "origin", "horizon", "target_week", "y", "yhat", "model", "window"]
    return pd.DataFrame(rows, columns=cols)


def test_sigma_validation_only_and_scenarios_reproducible():
    from shelflife.forecast.scenarios import ScenarioGenerator, coverage, sigma_table
    rng = np.random.default_rng(1)
    vw = pd.date_range("2015-01-05", periods=52, freq="W-MON")
    tw = pd.date_range("2016-01-04", periods=52, freq="W-MON")
    val, test = _synthetic_sel("validation", vw, rng), _synthetic_sel("test", tw, rng)
    with pytest.raises(ValueError):
        sigma_table(pd.concat([val, test]))
    sig = sigma_table(val)
    assert (sig.sigma > 0).all()
    assert sig[sig.horizon == 1].sigma.between(7, 13).all()      # true sd 10
    cov = coverage(test, sig).set_index("level").empirical
    assert abs(cov[0.8] - 0.8) < 0.08 and abs(cov[0.95] - 0.95) < 0.05
    g = ScenarioGenerator.from_frames(val, test, sig)
    a, b = g.generate(20, seed=7), g.generate(20, seed=7)
    assert a.shape == (20, 2, 52) and np.array_equal(a, b) and (a >= 0).all()
    assert not np.array_equal(a, g.generate(20, seed=8))
    assert abs((a - g.center[None]).std() - 10) < 3               # spread around the centre = error scale
    t1 = test[test.horizon == 1].pivot(index="sku_id", columns="target_week", values="y").to_numpy()
    assert np.allclose(g.center, t1)                              # default centre = actual demand (ADR-008)
    gf = ScenarioGenerator.from_frames(val, test, sig, center="forecast")
    assert np.allclose(gf.center, 100.0)
