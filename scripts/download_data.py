"""Download raw data (T2.1.1). Raw files stay in data/raw (git-ignored; Kaggle terms forbid redistribution).

Favorita (Kaggle) prerequisites, done once by a human:
  1. Free Kaggle account; accept the rules at
     https://www.kaggle.com/competitions/favorita-grocery-sales-forecasting/rules
  2. API token from https://www.kaggle.com/settings/api saved as ~/.kaggle/access_token
     (or legacy ~/.kaggle/kaggle.json). Never commit it.
  3. 7-Zip installed (Windows default path C:\\Program Files\\7-Zip\\7z.exe) to read the .7z archives.

FoodKeeper (USDA FSIS, CC0): the original FSIS URL now returns 403/empty, so the Internet Archive snapshot
of that exact URL (2025-07-02) is used; see docs/research/data_sources.md.

Run: python scripts/download_data.py [--skip-favorita] [--skip-foodkeeper]
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FAV_DIR = ROOT / "data" / "raw" / "favorita"
FK_DIR = ROOT / "data" / "raw" / "foodkeeper"
COMPETITION = "favorita-grocery-sales-forecasting"
FAV_FILES = ["items.csv.7z", "stores.csv.7z", "holidays_events.csv.7z", "train.csv.7z"]
SEVEN_ZIP = Path(r"C:\Program Files\7-Zip\7z.exe")
FK_URL = ("https://web.archive.org/web/20250702182320id_/"
          "https://www.fsis.usda.gov/shared/data/EN/foodkeeper.json")


def favorita() -> None:
    FAV_DIR.mkdir(parents=True, exist_ok=True)
    kaggle = Path(sys.executable).with_name("kaggle.exe" if sys.platform == "win32" else "kaggle")
    for f in FAV_FILES:
        if (FAV_DIR / f).exists():
            print(f"have {f}")
            continue
        print(f"downloading {f} ...", flush=True)
        subprocess.run([str(kaggle), "competitions", "download", "-c", COMPETITION, "-f", f,
                        "-p", str(FAV_DIR), "-q"], check=True)
    for f in FAV_FILES[:-1]:      # small files extracted; train.csv is streamed, never extracted
        if not (FAV_DIR / f.removesuffix(".7z")).exists():
            subprocess.run([str(SEVEN_ZIP), "x", "-y", f"-o{FAV_DIR}", str(FAV_DIR / f)], check=True,
                           stdout=subprocess.DEVNULL)
    print("favorita ok")


def foodkeeper() -> None:
    FK_DIR.mkdir(parents=True, exist_ok=True)
    out = FK_DIR / "foodkeeper.json"
    if out.exists():
        print("have foodkeeper.json")
        return
    with urllib.request.urlopen(FK_URL, timeout=120) as r:      # noqa: S310 (fixed https URL)
        out.write_bytes(r.read())
    print(f"foodkeeper ok ({out.stat().st_size} bytes; may be gzip-encoded, scripts handle both)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-favorita", action="store_true")
    ap.add_argument("--skip-foodkeeper", action="store_true")
    a = ap.parse_args()
    if not a.skip_foodkeeper:
        foodkeeper()
    if not a.skip_favorita:
        favorita()
