"""T5.2.1: one-at-a-time sensitivity sweeps and the waste-vs-service frontier.

Every cell is a paired Monte Carlo experiment (B1 vs OPT on identical paths, same seed in every cell = common
random numbers). Outputs, each with the config used:
  results/sensitivity/<parameter>.parquet   one row per (value, path, arm)
  results/sensitivity/frontier.parquet      B1 swept over cover, OPT over alpha
  results/sensitivity/config_used.yaml
Run: python scripts/run_sensitivity.py [--only shelf_life_scale ...] [--n-paths 50]
     python scripts/run_sensitivity.py --append-arms B1_TUNED   (adds an arm to the existing sweep files; same seed,
     so the new rows pair path-by-path with the arms already there; the frontier is left as it is)
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import pandas as pd
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from run_experiment import run  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "sensitivity"


def overrides_for(param: str, value) -> dict:
    if param.startswith("costs."):
        return {"costs": {param.split(".", 1)[1]: float(value)}}
    return {param: value}


def cell(cfg: dict, name: str, arms: list[str], ov: dict) -> pd.DataFrame:
    c = {"name": f"sens_{name}", "arms": arms, "replay": False, "workers": cfg["workers"],
         "monte_carlo": {"n_paths": cfg["n_paths"], "seed": cfg["seed"]}, "overrides": ov}
    _, df = run(c, OUT / "runs")
    return df


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=str(ROOT / "configs" / "sensitivity.yaml"))
    ap.add_argument("--only", nargs="*")
    ap.add_argument("--n-paths", type=int)
    ap.add_argument("--append-arms", nargs="*")
    a = ap.parse_args()
    cfg = yaml.safe_load(Path(a.config).read_text(encoding="utf-8"))
    if a.n_paths:
        cfg["n_paths"] = a.n_paths
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "config_used.yaml").write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")
    t_all = time.perf_counter()
    for param, values in cfg["sweeps"].items():
        if a.only and param not in a.only:
            continue
        parts = []
        arms = a.append_arms or cfg["arms"]
        for v in values:
            t0 = time.perf_counter()
            df = cell(cfg, f"{param}_{v}", arms, overrides_for(param, v))
            parts.append(df.assign(parameter=param, value=float(v)))
            print(f"{param}={v}: {time.perf_counter() - t0:.0f}s", flush=True)
        f = OUT / f"{param.replace('.', '_')}.parquet"
        new = pd.concat(parts, ignore_index=True)
        if a.append_arms:
            old = pd.read_parquet(f)
            new = pd.concat([old[~old.arm.isin(a.append_arms)], new], ignore_index=True)
        new.to_parquet(f, index=False)
    if not a.append_arms and (not a.only or "frontier" in a.only):
        parts = []
        for arm, sweep in cfg["frontier"].items():
            (lever, values), = sweep.items()
            for v in values:
                df = cell(cfg, f"frontier_{arm}_{lever}_{v}", [arm], {lever: v})
                parts.append(df.assign(lever=lever, value=float(v)))
                print(f"frontier {arm} {lever}={v}", flush=True)
        pd.concat(parts, ignore_index=True).to_parquet(OUT / "frontier.parquet", index=False)
    print(f"total {time.perf_counter() - t_all:.0f}s")


if __name__ == "__main__":
    main()
