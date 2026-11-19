"""T2.1.1 logic on small synthetic inputs; real-panel checks run only when the processed file exists."""
import hashlib

import numpy as np
import pandas as pd
import pytest

from shelflife.data import favorita as F


def tiny_daily():
    # Source calendar: Tue 2013-01-01 .. Tue 2013-01-29, with 2013-01-25 missing (closure).
    days = [d for d in pd.date_range("2013-01-01", "2013-01-29") if d != pd.Timestamp("2013-01-25")]
    rows = []
    for d in days:
        rows.append((d, 1, 2.0))                 # item 1 sells every day
        if d.day % 2 == 0:
            rows.append((d, 2, 1.5))             # item 2 sells on even days (fractional units)
    df = pd.DataFrame(rows, columns=["date", "item_nbr", "unit_sales"])
    return df, [d.strftime("%Y-%m-%d") for d in days]


def test_weekly_drops_partial_weeks_and_fills_zeros():
    daily, cal = tiny_daily()
    wk = F.to_weekly(daily, cal)
    weeks = sorted(wk.week_start.unique())
    # Full Mon-Sun weeks inside Tue 1 Jan .. Tue 29 Jan: 7, 14, 21 Jan (28 Jan week is partial)
    assert [pd.Timestamp(w).date().isoformat() for w in weeks] == ["2013-01-07", "2013-01-14", "2013-01-21"]
    w1 = wk[(wk.item_nbr == 1)].set_index("week_start").units
    assert w1.tolist() == [14.0, 14.0, 12.0]        # closure day on 25 Jan not imputed
    assert wk.set_index(["item_nbr", "week_start"]).n_days.xs(1).tolist() == [7, 7, 6]
    assert len(wk) == 2 * 3                          # full grid, zeros filled


def test_select_rule_and_shortfall_error():
    weeks = pd.date_range("2013-01-07", periods=20, freq="W-MON")
    rng = np.random.default_rng(0)
    items, rows = [], []
    for fam_i, fam in enumerate(F.FAMILIES):
        for k in range(6):
            nbr = 1000 * (fam_i + 1) + k
            items.append((nbr, fam, 1, 1))
            u = rng.uniform(10, 20, 20) * (k + 1)
            if k == 5:
                u[:3] = 0                            # only 85% non-zero -> ineligible even though largest
            rows += [(nbr, w, x) for w, x in zip(weeks, u, strict=True)]
    wk = pd.DataFrame(rows, columns=["item_nbr", "week_start", "units"])
    it = pd.DataFrame(items, columns=["item_nbr", "family", "class", "perishable"])
    ch = F.select_skus(wk, it)
    assert len(ch) == 12
    for fam_i, _ in enumerate(F.FAMILIES):
        assert sorted(ch[ch.item_nbr // 1000 == fam_i + 1].item_nbr % 1000) == [1, 2, 3, 4]
    with pytest.raises(ValueError):
        F.select_skus(wk[wk.item_nbr % 1000 < 3], it)


def test_validate_panel_catches_gaps():
    weeks = pd.date_range("2013-01-07", periods=210, freq="W-MON")
    p = pd.concat([pd.DataFrame({"sku_id": f"S{i}", "item_nbr": i, "week_start": weeks, "units": 1.0})
                   for i in range(12)])
    F.validate_panel(p)
    with pytest.raises(AssertionError):
        F.validate_panel(p.drop(index=p.index[5]))


@pytest.mark.skipif(not F.PROCESSED.exists(), reason="processed panel not built")
def test_real_panel_schema_and_rebuild_deterministic():
    p = pd.read_parquet(F.PROCESSED)
    assert list(p.columns) == F.PANEL_COLS
    assert p.gap_imputed.sum() <= 0.02 * len(p)            # cleaning touches few weeks
    assert (p.loc[~p.gap_imputed, "units"] == p.loc[~p.gap_imputed, "units_raw"]).all()
    F.validate_panel(p)
    h1 = hashlib.sha256(pd.util.hash_pandas_object(p, index=False).values.tobytes()).hexdigest()
    p2 = F.run()                                 # rebuild from the cached daily aggregate
    h2 = hashlib.sha256(pd.util.hash_pandas_object(p2, index=False).values.tobytes()).hexdigest()
    assert h1 == h2


def test_unconstrain_is_past_only_and_flags_gaps():
    weeks = pd.date_range("2014-01-06", periods=20, freq="W-MON")
    u = np.full(20, 100.0)
    u[12] = 3.0                                   # one-week outage
    p = pd.DataFrame({"sku_id": "S", "item_nbr": 1, "family": "DAIRY", "week_start": weeks, "units": u,
                      "n_days": 7})
    out = F.unconstrain(p)
    assert out.gap_imputed.tolist() == [i == 12 for i in range(20)]
    assert out.units.iloc[12] == 100.0 and out.units_raw.iloc[12] == 3.0
    # changing FUTURE values must not change the imputed value (no look-ahead)
    p2 = p.copy()
    p2.loc[13:, "units"] = 500.0
    assert F.unconstrain(p2).units.iloc[12] == 100.0


def test_select_excludes_items_phasing_out():
    weeks = pd.date_range("2013-01-07", periods=60, freq="W-MON")
    items, rows = [], []
    for fam_i, fam in enumerate(F.FAMILIES):
        for k in range(5):
            nbr = 1000 * (fam_i + 1) + k
            items.append((nbr, fam, 1, 1))
            u = np.full(60, 10.0 * (k + 1))
            if k == 4:
                u[-2:] = 0                         # biggest item, 97% coverage, but stops at the end
            rows += [(nbr, w, x) for w, x in zip(weeks, u, strict=True)]
    wk = pd.DataFrame(rows, columns=["item_nbr", "week_start", "units"])
    it = pd.DataFrame(items, columns=["item_nbr", "family", "class", "perishable"])
    ch = F.select_skus(wk, it)
    assert not (ch.item_nbr % 1000 == 4).any()
