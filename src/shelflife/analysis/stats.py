"""Paired statistics for baseline-vs-optimised experiments (T5.1.2).

Primary: effect estimates with percentile-bootstrap 95% CIs (paths resampled with replacement, the SAME
resampled paths for both arms, so pairing is kept). Secondary: Wilcoxon signed-rank p-value (N is a
computing choice, so p-values say little on their own) and the paired standardised effect size
d_z = mean(diff) / sd(diff).

Relative reduction = 100 * (1 - mean_new / mean_base), a ratio of means (not a mean of per-path ratios, which
explodes when a path's baseline is near 0). Point deltas for rates are in percentage points.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import wilcoxon


def paired(df: pd.DataFrame, kpi: str, base: str = "B1", new: str = "OPT") -> pd.DataFrame:
    """Rows: one per path_id, columns base/new values of `kpi` (MC layer rows only)."""
    w = df.pivot(index="path_id", columns="arm", values=kpi)[[base, new]].dropna()
    if len(w) < 2:
        raise ValueError("need >= 2 paired paths")
    return w


def bootstrap(base: np.ndarray, new: np.ndarray, kind: str, n_boot: int = 10_000, seed: int = 0,
              level: float = 0.95) -> dict[str, float]:
    """kind: 'reduction_pct' (100 * (1 - mean new / mean base)), 'delta' (mean new - base),
    'delta_pts' (100 * (mean new - mean base), for rates in [0, 1])."""
    base, new = np.asarray(base, float), np.asarray(new, float)
    n = len(base)

    def stat(b, x):
        if kind == "reduction_pct":
            return 100 * (1 - x.mean(axis=-1) / b.mean(axis=-1))
        if kind == "delta":
            return (x - b).mean(axis=-1)
        if kind == "delta_pts":
            return 100 * (x - b).mean(axis=-1)
        raise ValueError(kind)

    rng = np.random.default_rng(seed)
    idx = rng.integers(0, n, size=(n_boot, n))
    boots = stat(base[idx], new[idx])
    a = (1 - level) / 2
    est = float(stat(base, new))
    lo, hi = np.quantile(boots, [a, 1 - a])
    d = new - base
    sd = d.std(ddof=1)
    try:
        p = float(wilcoxon(new, base).pvalue) if np.any(d != 0) else 1.0
    except ValueError:
        p = float("nan")
    return {"estimate": est, "ci_lo": float(lo), "ci_hi": float(hi), "half_width": float((hi - lo) / 2),
            "n": int(n), "mean_base": float(base.mean()), "mean_new": float(new.mean()),
            "effect_size_dz": float(d.mean() / sd) if sd > 0 else float("nan"), "wilcoxon_p": p}


# KPI -> (column, kind, headline name). Reductions are positive when the optimiser is better.
HEADLINE_KPIS = {
    "expired_waste_reduction_pct": ("expired_cases", "reduction_pct"),
    "lost_cases_reduction_pct": ("lost_cases", "reduction_pct"),
    "fill_rate_delta_pts": ("fill_rate", "delta_pts"),
    "changeover_hours_reduction_pct": ("changeover_hours", "reduction_pct"),
    "allergen_clean_hours_reduction_pct": ("allergen_clean_hours", "reduction_pct"),
    "evaluated_cost_reduction_pct": ("evaluated_cost", "reduction_pct"),
}


def summarise_experiment(df: pd.DataFrame, base: str = "B1", new: str = "OPT", n_boot: int = 10_000,
                         seed: int = 0) -> pd.DataFrame:
    mc = df[df.layer == "mc"]
    rows = []
    for name, (col, kind) in HEADLINE_KPIS.items():
        w = paired(mc, col, base, new)
        rows.append({"metric": name, "kpi": col, "kind": kind, "base": base, "new": new,
                     **bootstrap(w[base].to_numpy(), w[new].to_numpy(), kind, n_boot, seed)})
    return pd.DataFrame(rows)


def n_for_half_width(pilot_half_width: float, pilot_n: int, target: float) -> int:
    """CI half-width shrinks like 1/sqrt(N): N = pilot_n * (hw / target)^2."""
    return int(np.ceil(pilot_n * (pilot_half_width / target) ** 2))
