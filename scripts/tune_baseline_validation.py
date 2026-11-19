"""ADR-009: tune baseline B1's cover on the VALIDATION year with the same rule the optimiser got (ADR-007).

Why: the optimiser's changeover estimate was chosen on the validation year (ADR-007), while B1 kept the cover fixed in
ADR-006. The T5.2.1 frontier then showed that a shorter B1 cover sits on a different point of the trade-off. A fair
comparison gives both planners the same tuning budget, so B1's cover is chosen here, test year not read.

Selection rule (identical to ADR-007, fixed before this run): lowest simulator-evaluated cost with configs/costs.yaml
weights; ties within 0.5% -> fewer expired cases. reorder_weeks stays 1 (ADR-006).

Outputs: results/baseline_tuning_validation.csv, configs/baseline.yaml
Run: python scripts/tune_baseline_validation.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from run_rolling_replay import setup, summarise  # noqa: E402
from shelflife.opt.model import load_costs  # noqa: E402
from shelflife.opt.rolling import run_arm  # noqa: E402
from shelflife.sim.baseline import BaselineB1  # noqa: E402
from shelflife.sim.kpis import evaluated_cost  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
GRID = [0.5, 0.75, 1.0, 1.5, 2.0, 2.5, 3.0]


def main() -> None:
    cfg, plant, k, win, d, hist, weeks, start_inv, start_last, _ = setup("validation")
    assert weeks[0] == win.val_start and weeks[-1] == win.val_end
    costs = load_costs()
    rows = []
    for cover in GRID:
        b1 = BaselineB1.from_config(cfg, plant, cover_weeks=cover)
        r, plans = run_arm(plant, b1, d, hist, start_inv, start_last)
        row, _, v = summarise(f"B1_cover_{cover:g}", r, plans, plant, cfg, start_last)
        if v:
            raise SystemExit(f"ABORT: cover {cover} failed the checker: {v[:5]}")
        row["cover_weeks"] = cover
        row["evaluated_cost"] = evaluated_cost(r, costs)
        rows.append(row)
    t = pd.DataFrame(rows)
    t["evaluated_cost_index_vs_cover1"] = 100 * t.evaluated_cost / t.loc[t.cover_weeks == 1.0, "evaluated_cost"].iloc[0]
    t.round(4).to_csv(ROOT / "results" / "baseline_tuning_validation.csv", index=False)
    cand = t.sort_values("evaluated_cost")
    near = cand[cand.evaluated_cost <= cand.evaluated_cost.iloc[0] * 1.005].sort_values("expired_cases")
    chosen = float(near.cover_weeks.iloc[0])
    (ROOT / "configs" / "baseline.yaml").write_text(yaml.safe_dump({
        "note": "B1 cover chosen on the VALIDATION year by scripts/tune_baseline_validation.py (ADR-009).",
        "cover_weeks": chosen, "reorder_weeks": 1.0}, sort_keys=False), encoding="utf-8")
    print(t[["arm", "evaluated_cost_index_vs_cover1", "expired_pct", "fill_rate", "lost_cases", "changeover_hours",
             "utilisation"]].round(4).to_string(index=False))
    print("chosen cover_weeks:", chosen)


if __name__ == "__main__":
    main()
