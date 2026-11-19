"""T1.2.2 smoke test: solvers and forecasting libraries. Run: python scripts/smoke_solvers.py"""
import importlib.metadata as md
import time

import numpy as np
import pandas as pd


def ver(pkg):
    try:
        return md.version(pkg)
    except md.PackageNotFoundError:
        return "NOT INSTALLED"


def timed(label, fn):
    t0 = time.perf_counter()
    try:
        out = fn()
        print(f"[OK]   {label}: {out}  ({time.perf_counter() - t0:.2f}s)")
        return True
    except Exception as e:  # smoke test: report any failure
        print(f"[FAIL] {label}: {type(e).__name__}: {str(e)[:200]}")
        return False


# max 3x + 2y + 4z  s.t. x+y+z<=10, 2x+z<=8, y+2z<=9, x,y,z integer in [0,10]  (optimum found by brute force)
best = max((3*x + 2*y + 4*z, (x, y, z)) for x in range(11) for y in range(11) for z in range(11)
           if x + y + z <= 10 and 2*x + z <= 8 and y + 2*z <= 9)


def scip():
    from ortools.linear_solver import pywraplp
    s = pywraplp.Solver.CreateSolver("SCIP")
    v = [s.IntVar(0, 10, n) for n in "xyz"]
    s.Add(sum(v) <= 10); s.Add(2*v[0] + v[2] <= 8); s.Add(v[1] + 2*v[2] <= 9)
    s.Maximize(3*v[0] + 2*v[1] + 4*v[2])
    assert s.Solve() == pywraplp.Solver.OPTIMAL
    assert round(s.Objective().Value()) == best[0]
    return f"obj={s.Objective().Value():.0f} (brute force {best[0]})"


def cpsat():
    from ortools.sat.python import cp_model
    m = cp_model.CpModel()
    x, y, z = (m.NewIntVar(0, 10, n) for n in "xyz")
    m.Add(x + y + z <= 10); m.Add(2*x + z <= 8); m.Add(y + 2*z <= 9)
    m.Maximize(3*x + 2*y + 4*z)
    s = cp_model.CpSolver()
    assert s.Solve(m) == cp_model.OPTIMAL
    assert round(s.ObjectiveValue()) == best[0]
    return f"obj={s.ObjectiveValue():.0f}"


def highs():
    from scipy.optimize import LinearConstraint, milp
    r = milp(c=[-3, -2, -4], integrality=np.ones(3), bounds=(0, 10),
             constraints=LinearConstraint([[1, 1, 1], [2, 0, 1], [0, 1, 2]], ub=[10, 8, 9]))
    assert r.success and round(-r.fun) == best[0]
    return f"obj={-r.fun:.0f}"


def toy_series():
    idx = pd.date_range("2018-01-01", periods=156, freq="W-MON")
    y = 100 + 10*np.sin(2*np.pi*np.arange(156)/52) + np.random.default_rng(0).normal(0, 3, 156)
    return pd.DataFrame({"unique_id": "s1", "ds": idx, "y": y})


def sf():
    from statsforecast import StatsForecast
    from statsforecast.models import AutoARIMA, AutoETS
    f = StatsForecast(models=[AutoARIMA(season_length=52), AutoETS(season_length=52)], freq="W-MON")
    out = f.forecast(df=toy_series(), h=13)
    assert out.shape[0] == 13 and out.drop(columns=["unique_id", "ds"]).notna().all().all()
    return f"13-step forecast, cols={list(out.columns[2:])}"


def prophet():
    from prophet import Prophet
    d = toy_series().rename(columns={"unique_id": "id"}).drop(columns="id")
    m = Prophet(yearly_seasonality=True, weekly_seasonality=False, daily_seasonality=False).fit(d)
    fc = m.predict(m.make_future_dataframe(13, freq="W-MON"))
    return f"{len(fc)} rows, yhat tail={fc['yhat'].iloc[-1]:.1f}"


if __name__ == "__main__":
    for p in ["ortools", "scipy", "statsforecast", "statsmodels", "prophet", "pandas", "numpy", "streamlit"]:
        print(f"{p:14} {ver(p)}")
    r = [timed("OR-Tools SCIP (pywraplp)", scip), timed("OR-Tools CP-SAT", cpsat),
         timed("HiGHS via scipy.milp", highs), timed("statsforecast AutoARIMA+AutoETS", sf),
         timed("Prophet", prophet)]
    print(f"{sum(r)}/{len(r)} passed")
