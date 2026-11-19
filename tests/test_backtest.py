from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from shelflife.forecast import backtest as B


def synth_panel(n_weeks=260, skus=("S1", "S2"), seed=0):
    rng = np.random.default_rng(seed)
    weeks = pd.date_range("2013-01-07", periods=n_weeks, freq="W-MON")
    rows = []
    for k, s in enumerate(skus):
        y = 200 + 50 * np.sin(2 * np.pi * np.arange(n_weeks) / 52 + k) + rng.normal(0, 10, n_weeks)
        rows.append(pd.DataFrame({"sku_id": s, "week_start": weeks, "units": y.clip(0)}))
    return pd.concat(rows, ignore_index=True)


@pytest.fixture(scope="module")
def panel():
    return synth_panel()


@pytest.fixture(scope="module")
def windows(panel):
    return B.make_windows(panel.week_start)


def test_windows_layout(panel, windows):
    weeks = pd.DatetimeIndex(sorted(panel.week_start.unique()))
    assert windows.test_end == weeks[-1]
    assert windows.test_start == weeks[-52]
    assert windows.val_end == weeks[-53]
    assert windows.val_start == weeks[-104]
    assert (weeks < windows.val_start).sum() >= 104


def test_windows_reject_short_or_gappy():
    with pytest.raises(ValueError):
        B.make_windows(pd.date_range("2020-01-06", periods=150, freq="W-MON"))
    w = pd.date_range("2013-01-07", periods=260, freq="W-MON").delete(100)
    with pytest.raises(ValueError):
        B.make_windows(w)


def test_schema_and_no_leakage(panel, windows):
    seen = []

    def spy(hist, h):
        seen.append(hist.index.max())
        return B.naive(hist, h)

    fc = B.run_backtest(panel, spy, "spy", windows)
    assert list(fc.columns) == B.SCHEMA
    # every training set ends strictly before its origin
    origins = fc.drop_duplicates(["sku_id", "origin"]).origin.sort_values().tolist()
    assert all(m < o for m, o in zip(sorted(seen), sorted(origins * 1), strict=False))
    assert (fc.origin <= fc.target_week).all()
    # targets stay inside their own window (validation never reads test actuals)
    for win in ("validation", "test"):
        lo, hi = windows.bounds(win)
        g = fc[fc.window == win]
        assert g.target_week.between(lo, hi).all()
        assert g.origin.nunique() == 52


def test_leakage_strict_per_call(panel, windows):
    def strict(hist, h):
        strict.calls.append(hist.index.max())
        return B.naive(hist, h)
    strict.calls = []
    one = panel[panel.sku_id == "S1"]
    B.run_backtest(one, strict, "x", windows, which=("validation",))
    lo, hi = windows.bounds("validation")
    origins = pd.date_range(lo, hi, freq="W-MON")
    assert [c + np.timedelta64(7, "D") for c in strict.calls] == list(origins)


def test_horizons_complete_where_window_allows(panel, windows):
    fc = B.run_backtest(panel, B.naive, "naive", windows)
    first = fc[(fc.window == "test") & (fc.origin == windows.test_start) & (fc.sku_id == "S1")]
    assert sorted(first.horizon) == list(range(1, 14))
    last = fc[(fc.window == "test") & (fc.origin == windows.test_end) & (fc.sku_id == "S1")]
    assert sorted(last.horizon) == [1]


def test_benchmarks_values():
    hist = pd.Series(np.arange(1.0, 61.0), index=pd.date_range("2020-01-06", periods=60, freq="W-MON"))
    assert B.naive(hist, 3).tolist() == [60, 60, 60]
    assert B.moving_average(hist, 2).tolist() == [58.5, 58.5]
    assert B.seasonal_naive(hist, 3).tolist() == [9, 10, 11]   # value 52 weeks before each target


def test_metrics_known_values():
    y, yhat = np.array([10.0, 20.0, 30.0]), np.array([12.0, 18.0, 33.0])
    assert B.wape(y, yhat) == pytest.approx(100 * 7 / 60)
    assert B.bias(y, yhat) == pytest.approx(100 * 3 / 60)


def test_seasonal_naive_beats_naive_on_seasonal_data(panel, windows):
    scales = B.mase_scales(panel, windows.val_start)
    fc = pd.concat([B.run_backtest(panel, f, n, windows) for n, f in B.BENCHMARKS.items()])
    m = B.metrics(fc, scales).query("sku_id == 'ALL' and window == 'test'").set_index("model")
    assert m.loc["seasonal_naive", "wape"] < m.loc["naive", "wape"]
    assert (m["mase"] > 0).all()


def test_deterministic(panel, windows):
    a = B.run_backtest(panel, B.moving_average, "ma4", windows)
    b = B.run_backtest(panel, B.moving_average, "ma4", windows)
    pd.testing.assert_frame_equal(a, b)


PANEL = Path(__file__).resolve().parents[1] / "data" / "processed" / "demand_weekly.parquet"
WINDOWS = Path(__file__).resolve().parents[1] / "configs" / "windows.yaml"


@pytest.mark.skipif(not (PANEL.exists() and WINDOWS.exists()), reason="real panel/windows not built")
def test_committed_windows_match_panel():
    import yaml
    panel = pd.read_parquet(PANEL)
    w = B.make_windows(panel.week_start).to_dict()
    saved = yaml.safe_load(WINDOWS.read_text(encoding="utf-8"))
    assert {k: saved[k] for k in w} == w
    assert saved["train_weeks"] >= 104
