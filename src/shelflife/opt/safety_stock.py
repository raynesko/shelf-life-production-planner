"""Safety-stock targets from forecast error, capped by the shelf-life window (T4.3.1).

For a plan built at an origin, week t (0-based) is forecast horizon h = t + 1. Stock left at the end of
week t protects week t + 1 (horizon t + 2), so
    SS[p, t] = z(alpha) * sigma[p, min(t + 2, H_max)]
capped at the forecast demand that stock could still meet before it becomes unsaleable:
    cap[p, t] = sum of forecast[p, t+1 .. t+A_p]   (A_p = max ship age in weeks; 0 if A_p = 0)
Carrying more than the cap only creates expired waste. The optimiser treats SS as a SOFT floor
(shortfall penalty), so it is never infeasible because of SS. alpha is a TARGET service parameter (A-24).
"""
from __future__ import annotations

import numpy as np
from scipy.stats import norm


def safety_stock(sigma: np.ndarray, forecast: np.ndarray, max_ship_age: np.ndarray,
                 alpha: float = 0.95) -> np.ndarray:
    """sigma: (n, H_max) by horizon 1..H_max; forecast: (n, H) planning forecast; returns (n, H)."""
    if not 0.5 <= alpha < 1:
        raise ValueError("alpha must be in [0.5, 1)")
    n, H = forecast.shape
    z = norm.ppf(alpha)
    hmax = sigma.shape[1]
    ss = np.zeros((n, H))
    for t in range(H):
        h = min(t + 2, hmax)
        raw = z * sigma[:, h - 1]
        cap = np.array([forecast[p, t + 1:t + 1 + max_ship_age[p]].sum() if max_ship_age[p] > 0 else 0.0
                        for p in range(n)])
        ss[:, t] = np.minimum(raw, cap)
    return np.clip(ss, 0, None)
