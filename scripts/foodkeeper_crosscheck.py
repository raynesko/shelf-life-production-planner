"""Cross-check plant.yaml shelf lives against USDA FSIS FoodKeeper (CC0). Part of T1.1.1 / T2.2.1.

Input : data/raw/foodkeeper/foodkeeper.json (Wayback snapshot 2025-07-02 of
        https://www.fsis.usda.gov/shared/data/EN/foodkeeper.json; FSIS URL returned 403 / empty in 2026).
Output: data/processed/foodkeeper_crosscheck.csv (small, CC0, committed).
Run   : python scripts/foodkeeper_crosscheck.py
"""
from __future__ import annotations

import gzip
import json
from pathlib import Path

import pandas as pd

from shelflife.plant.config import load

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "foodkeeper" / "foodkeeper.json"
OUT = ROOT / "data" / "processed" / "foodkeeper_crosscheck.csv"
DAYS = {"Days": 1, "Weeks": 7, "Months": 30}

# SKU -> closest FoodKeeper product IDs (manual mapping; rationale: docs/research/foodkeeper_crosscheck.md)
MAPPING = {
    "SKU-01": [33], "SKU-02": [33], "SKU-03": [10], "SKU-04": [28], "SKU-05": [181, 183],
    "SKU-06": [16], "SKU-07": [354], "SKU-08": [180], "SKU-09": [420], "SKU-10": [190],
    "SKU-11": [417], "SKU-12": [193],
}


def read_foodkeeper(path: Path = RAW) -> pd.DataFrame:
    raw = path.read_bytes()
    txt = (gzip.decompress(raw) if raw[:2] == b"\x1f\x8b" else raw).decode("utf-8-sig")
    sheets = {s["name"]: s["data"] for s in json.loads(txt)["sheets"]}
    rows = [{k: v for cell in r for k, v in cell.items()} for r in sheets["Product"]]
    return pd.DataFrame(rows).set_index("ID")


def to_days(lo, hi, metric) -> tuple[float | None, float | None]:
    if metric in DAYS and pd.notna(lo):
        return lo * DAYS[metric], (hi if pd.notna(hi) else lo) * DAYS[metric]
    return None, None


def main() -> None:
    fk, cfg = read_foodkeeper(), load()
    out = []
    for s in cfg.skus:
        for pid in MAPPING[s.id]:
            r = fk.loc[float(pid)]
            dop = to_days(r.DOP_Refrigerate_Min, r.DOP_Refrigerate_Max, r.DOP_Refrigerate_Metric)
            ref = to_days(r.Refrigerate_Min, r.Refrigerate_Max, r.Refrigerate_Metric)
            basis, (lo, hi) = ("from date of purchase", dop) if dop[0] is not None else \
                ("refrigerator storage (prepared/opened)", ref)
            out.append({
                "sku_id": s.id, "sku_name": s.name, "model_shelf_life_days": s.shelf_life_days,
                "fk_id": int(pid), "fk_name": f"{r.Name} {r.Name_subtitle or ''}".strip(),
                "fk_basis": basis if lo is not None else f"text: {r.Refrigerate_Metric}",
                "fk_min_days": lo, "fk_max_days": hi,
            })
    df = pd.DataFrame(out)
    df.to_csv(OUT, index=False)
    print(df.to_string(index=False))
    print(f"\nwrote {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
