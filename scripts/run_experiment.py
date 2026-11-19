"""T5.1.1: run an experiment from a YAML config (Layer A replay + Layer B Monte Carlo, paired, CRN).

Writes results/experiments/<run_id>/{kpis.parquet, config.yaml, meta.json}; run_id = <name>_<config hash>.
Run: python scripts/run_experiment.py --config configs/experiment_main.yaml [--n-paths N] [--workers W]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import pandas as pd
import yaml

from shelflife.analysis import experiment as X

ROOT = Path(__file__).resolve().parents[1]
_CTX: dict[str, X.Context] = {}
_PATHS: dict[str, object] = {}


def _ctx(ov: X.Overrides) -> X.Context:
    if ov.key() not in _CTX:
        _CTX[ov.key()] = X.build_context(ov)
    return _CTX[ov.key()]


def _task(args) -> dict:
    ov, layer, path_id, arm, n_paths, seed = args
    ctx = _ctx(ov)
    if layer == "replay":
        demand = ctx.actual
    else:
        key = f"{ov.key()}|{n_paths}|{seed}"
        if key not in _PATHS:
            _PATHS[key] = X.scenario_paths(ctx, n_paths, seed)
        demand = _PATHS[key][path_id]
    t0 = time.perf_counter()
    row = X.run_one(ctx, arm, demand)
    return {"layer": layer, "path_id": path_id, "seed": seed if layer == "mc" else None, "arm": arm, **row,
            "runtime_s": time.perf_counter() - t0}


def run(cfg: dict, out_root: Path = ROOT / "results" / "experiments") -> tuple[Path, pd.DataFrame]:
    ov = X.Overrides(**cfg.get("overrides", {}))
    mc = cfg.get("monte_carlo") or {}
    n, seed = int(mc.get("n_paths", 0)), int(mc.get("seed", 0))
    tasks = []
    if cfg.get("replay", True):
        tasks += [(ov, "replay", 0, a, n, seed) for a in cfg["arms"]]
    tasks += [(ov, "mc", i, a, n, seed) for i in range(n) for a in cfg["arms"]]
    t0 = time.perf_counter()
    workers = int(cfg.get("workers", 1))
    if workers > 1:
        with ProcessPoolExecutor(max_workers=workers) as ex:
            rows = list(ex.map(_task, tasks, chunksize=max(1, len(tasks) // (workers * 4))))
    else:
        rows = [_task(t) for t in tasks]
    df = pd.DataFrame(rows)
    snap = {**cfg, "overrides_resolved": json.loads(ov.key()), "planner": X.planner_settings(), "b1_tuned_cover": X.tuned_b1_cover(),
            "scenario_center": "actual (ADR-008)"}
    version = X.code_version()
    # run id = config + source code, so a code change can never reuse an old run's id
    chash = hashlib.sha256((json.dumps(snap, sort_keys=True, default=str) + version["source_sha256"]).encode()
                           ).hexdigest()[:10]
    out = out_root / f"{cfg['name']}_{chash}"
    out.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out / "kpis.parquet", index=False)
    (out / "config.yaml").write_text(yaml.safe_dump(snap, sort_keys=False), encoding="utf-8")
    meta = {"run_id": out.name, "rows": len(df), "n_paths": n, "seed": seed, "arms": cfg["arms"],
            "kpi_sha256": X.kpi_hash(df), "wall_s": round(time.perf_counter() - t0, 1), "workers": workers,
            "checker_violations_total": int(df.get("checker_violations", pd.Series([0])).sum()),
            "fallback_weeks_total": int(df.get("fallback_weeks", pd.Series([0])).fillna(0).sum()),
            "label": "simulation on a synthetic plant model", **version}
    (out / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return out, df


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--n-paths", type=int)
    ap.add_argument("--workers", type=int)
    a = ap.parse_args()
    cfg = yaml.safe_load(Path(a.config).read_text(encoding="utf-8"))
    if a.n_paths is not None:
        cfg["monte_carlo"]["n_paths"] = a.n_paths
    if a.workers is not None:
        cfg["workers"] = a.workers
    out, df = run(cfg)
    meta = json.loads((out / "meta.json").read_text())
    print(out)
    print({k: meta[k] for k in ("rows", "kpi_sha256", "wall_s", "checker_violations_total", "fallback_weeks_total")})
    cols = ["expired_cases", "lost_cases", "fill_rate", "changeover_hours", "evaluated_cost"]
    print(df.groupby(["layer", "arm"])[cols].mean().round(3).to_string())


if __name__ == "__main__":
    main()
