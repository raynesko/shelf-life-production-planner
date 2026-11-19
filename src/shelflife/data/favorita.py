"""Favorita -> weekly demand panel for 12 perishable SKUs (T2.1.1).

Pipeline
1. `aggregate_daily`: stream train.csv (via `7z e -so`, never fully extracted) in chunks, keep perishable
   items of the target families, clip negative unit_sales (returns) to 0 and count them, sum over all
   54 stores -> chain-wide daily units per item (a DC-level demand proxy; docs/assumptions.md A-01).
   Saved to data/interim/favorita_daily_perishable.parquet (git-ignored).
2. `to_weekly`: Monday-start weeks; item-days with no row are zero sales (the source omits zeros);
   partial first/last weeks dropped; days absent from the whole source calendar (store closures such as
   25 Dec) are NOT imputed - the closure is real lost selling time - and are flagged via n_days.
3. `select_skus`: written rule (below), deterministic.
4. `build_panel`: map selected items onto plant SKUs in configs/plant.yaml (same family) and write
   data/processed/demand_weekly.parquet.

Selection rule: within each plant family (DAIRY, DELI, PREPARED FOODS), keep items with non-zero sales in
>= 95% of full weeks AND in each of the final 13 weeks (still active, not being phased out), rank by
total units, take the top 4.

Demand unconstraining (`unconstrain`): a week selling < 20% of the trailing 8-week median is treated as a
supply or data gap (sales != demand) and replaced by that trailing median. Past-only, so no look-ahead;
raw value kept in `units_raw`, flagged in `gap_imputed`. Favorita items are anonymous, so each plant
SKU borrows the demand pattern of a real perishable item from the same family (a proxy, not identity).
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[3]
RAW = ROOT / "data" / "raw" / "favorita"
INTERIM = ROOT / "data" / "interim" / "favorita_daily_perishable.parquet"
PROCESSED = ROOT / "data" / "processed" / "demand_weekly.parquet"
SKUS_YAML = ROOT / "configs" / "skus.yaml"
SEVEN_ZIP = Path(r"C:\Program Files\7-Zip\7z.exe")
FAMILIES = ("DAIRY", "DELI", "PREPARED FOODS")
PER_FAMILY = 4
MIN_NONZERO_SHARE = 0.95
# ADR-005: from week 2017-04-03 the long-running PREPARED FOODS items stop selling and new item numbers
# take over (assortment change). The panel ends at the last week before the switch, for all SKUs.
PANEL_COLS = ["sku_id", "item_nbr", "family", "week_start", "units", "units_raw", "gap_imputed", "n_days"]
LAST_WEEK = pd.Timestamp("2017-03-27")
ACTIVE_WEEKS = 13          # item must sell in each of the final 13 weeks (excludes phase-outs)
GAP_RATIO, GAP_LOOKBACK = 0.2, 8   # unconstraining: week < 20% of trailing 8-week median = supply/data gap


def target_items(items: pd.DataFrame, families=FAMILIES) -> pd.DataFrame:
    return items[(items.perishable == 1) & items.family.isin(families)].copy()


def aggregate_daily(train_7z: Path = RAW / "train.csv.7z", items_csv: Path = RAW / "items.csv",
                    chunksize: int = 5_000_000) -> tuple[pd.DataFrame, dict]:
    items = target_items(pd.read_csv(items_csv))
    keep = set(items.item_nbr)
    proc = subprocess.Popen([str(SEVEN_ZIP), "e", "-so", str(train_7z)], stdout=subprocess.PIPE,
                            stderr=subprocess.DEVNULL)
    parts, stats = [], {"rows_read": 0, "rows_kept": 0, "negative_rows_clipped": 0, "dates": set()}
    for ch in pd.read_csv(proc.stdout, usecols=["date", "item_nbr", "unit_sales"], chunksize=chunksize,
                          dtype={"item_nbr": "int32", "unit_sales": "float64"}):
        stats["rows_read"] += len(ch)
        stats["dates"].update(ch["date"].unique())
        ch = ch[ch.item_nbr.isin(keep)]
        stats["rows_kept"] += len(ch)
        neg = ch.unit_sales < 0
        stats["negative_rows_clipped"] += int(neg.sum())
        ch = ch.assign(unit_sales=ch.unit_sales.clip(lower=0))
        parts.append(ch.groupby(["date", "item_nbr"], as_index=False)["unit_sales"].sum())
    proc.wait()
    daily = (pd.concat(parts).groupby(["date", "item_nbr"], as_index=False)["unit_sales"].sum())
    daily["date"] = pd.to_datetime(daily["date"])
    stats["source_calendar_days"] = sorted(stats.pop("dates"))
    return daily, stats


def to_weekly(daily: pd.DataFrame, source_days: list[str]) -> pd.DataFrame:
    days = pd.DatetimeIndex(pd.to_datetime(source_days))
    full = pd.date_range(days.min(), days.max(), freq="D")
    first_monday = full[full.dayofweek == 0][0]
    last_sunday = full[full.dayofweek == 6][-1]
    d = daily[(daily.date >= first_monday) & (daily.date <= last_sunday)].copy()
    d["week_start"] = d.date - pd.to_timedelta(d.date.dt.dayofweek, unit="D")
    wk = d.groupby(["item_nbr", "week_start"], as_index=False)["unit_sales"].sum()
    weeks = pd.date_range(first_monday, last_sunday - pd.to_timedelta(6, unit="D"), freq="W-MON")
    grid = pd.MultiIndex.from_product([sorted(d.item_nbr.unique()), weeks], names=["item_nbr", "week_start"])
    wk = wk.set_index(["item_nbr", "week_start"]).reindex(grid, fill_value=0.0).reset_index()
    present = pd.Series(1, index=days[(days >= first_monday) & (days <= last_sunday)])
    n_days = present.groupby(present.index - pd.to_timedelta(present.index.dayofweek, unit="D")).sum()
    wk["n_days"] = wk.week_start.map(n_days).fillna(0).astype(int)
    return wk.rename(columns={"unit_sales": "units"})


def select_skus(weekly: pd.DataFrame, items: pd.DataFrame) -> pd.DataFrame:
    w = weekly.sort_values("week_start")
    s = w.groupby("item_nbr").agg(total=("units", "sum"), nonzero=("units", lambda x: (x > 0).mean()),
                                  active_end=("units", lambda x: bool((x.iloc[-ACTIVE_WEEKS:] > 0).all())))
    s = s.join(items.set_index("item_nbr")[["family", "class"]])
    s = s[(s.nonzero >= MIN_NONZERO_SHARE) & s.active_end]
    out = (s.sort_values(["family", "total", "item_nbr"], ascending=[True, False, True])
             .groupby("family").head(PER_FAMILY).reset_index())
    short = {f: int((out.family == f).sum()) for f in FAMILIES if (out.family == f).sum() < PER_FAMILY}
    if short:
        raise ValueError(f"not enough eligible items per family: {short}")
    return out


def unconstrain(panel: pd.DataFrame) -> pd.DataFrame:
    out = []
    for _, g in panel.sort_values("week_start").groupby("sku_id", sort=True):
        g = g.copy()
        raw = g["units"].to_numpy(float)
        clean = raw.copy()
        flag = np.zeros(len(raw), bool)
        for i in range(len(raw)):
            hist = clean[max(0, i - GAP_LOOKBACK):i]
            if len(hist) >= GAP_LOOKBACK // 2:
                med = float(np.median(hist))
                if med > 0 and raw[i] < GAP_RATIO * med:
                    clean[i], flag[i] = med, True
        g["units_raw"], g["units"], g["gap_imputed"] = raw, clean, flag
        out.append(g)
    return pd.concat(out, ignore_index=True)


def build_panel(weekly: pd.DataFrame, chosen: pd.DataFrame, plant_skus: list[dict]) -> pd.DataFrame:
    rows = []
    for fam in FAMILIES:
        plant_ids = [s["id"] for s in plant_skus if s["family"] == fam]
        items_f = chosen[chosen.family == fam].sort_values(["total", "item_nbr"], ascending=[False, True])
        if len(plant_ids) != len(items_f):
            raise ValueError(f"{fam}: {len(plant_ids)} plant SKUs vs {len(items_f)} items")
        for sku_id, item in zip(sorted(plant_ids), items_f.item_nbr, strict=True):
            g = weekly[weekly.item_nbr == item]
            rows.append(g.assign(sku_id=sku_id, family=fam)[
                ["sku_id", "item_nbr", "family", "week_start", "units", "n_days"]])
    panel = pd.concat(rows, ignore_index=True)
    panel = unconstrain(panel)[PANEL_COLS]
    return panel.sort_values(["sku_id", "week_start"]).reset_index(drop=True)


def validate_panel(panel: pd.DataFrame, n_skus: int = 12, min_weeks: int = 200) -> None:
    assert panel.sku_id.nunique() == n_skus, "wrong SKU count"
    assert not panel[["sku_id", "item_nbr", "week_start", "units"]].isna().any().any(), "NaN in panel"
    assert (panel.units >= 0).all(), "negative units"
    for _, g in panel.groupby("sku_id"):
        w = g.week_start.sort_values()
        assert (w.diff().dropna() == np.timedelta64(7, "D")).all(), "non-contiguous weeks"
        assert len(w) >= min_weeks, "too few weeks"


def run(force_daily: bool = False) -> pd.DataFrame:
    items = pd.read_csv(RAW / "items.csv")
    if INTERIM.exists() and not force_daily:
        daily = pd.read_parquet(INTERIM)
        meta = yaml.safe_load(INTERIM.with_suffix(".yaml").read_text())
    else:
        daily, meta = aggregate_daily()
        INTERIM.parent.mkdir(parents=True, exist_ok=True)
        daily.to_parquet(INTERIM, index=False)
        INTERIM.with_suffix(".yaml").write_text(yaml.safe_dump(meta))
    weekly = to_weekly(daily, meta["source_calendar_days"])
    weekly = weekly[weekly.week_start <= LAST_WEEK].reset_index(drop=True)
    chosen = select_skus(weekly, items)
    plant = yaml.safe_load((ROOT / "configs" / "plant.yaml").read_text(encoding="utf-8"))["skus"]
    panel = build_panel(weekly, chosen, plant)
    validate_panel(panel)
    PROCESSED.parent.mkdir(parents=True, exist_ok=True)
    panel.to_parquet(PROCESSED, index=False)
    mapping = (panel.drop_duplicates("sku_id")[["sku_id", "item_nbr", "family"]]
               .merge(chosen[["item_nbr", "class", "total", "nonzero"]], on="item_nbr"))
    SKUS_YAML.write_text(yaml.safe_dump({
        "rule": f"perishable=1, families {list(FAMILIES)}, non-zero in >= {MIN_NONZERO_SHARE:.0%} of full "
                f"weeks up to {LAST_WEEK.date()} (ADR-005) and in each of the last {ACTIVE_WEEKS} weeks, "
                f"top {PER_FAMILY} by total units per family; "
                f"mapped to plant SKUs in family order",
        "source_stats": {k: v for k, v in meta.items() if k != "source_calendar_days"},
        "gap_weeks_imputed": {k: int(v) for k, v in panel.groupby("sku_id").gap_imputed.sum().items() if v},
        "skus": [{"sku_id": r.sku_id, "item_nbr": int(r.item_nbr), "family": r.family, "class": int(r["class"]),
                  "total_units": round(float(r.total), 1), "nonzero_week_share": round(float(r.nonzero), 4)}
                 for _, r in mapping.iterrows()],
    }, sort_keys=False), encoding="utf-8")
    return panel


if __name__ == "__main__":
    p = run()
    print(p.groupby("sku_id").agg(item=("item_nbr", "first"), fam=("family", "first"), weeks=("units", "size"),
                                  mean=("units", "mean"), cv=("units", lambda x: x.std() / x.mean())))
    print(f"weeks {p.week_start.min().date()} .. {p.week_start.max().date()}; wrote {PROCESSED}")
