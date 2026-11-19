# ADR-002: Toolchain

- **Status:** ACCEPTED (T1.2.2, verified by `scripts/smoke_solvers.py`, Python 3.12.10, Windows 11, fresh venv)
- **Result:** 5/5 smoke checks pass: OR-Tools SCIP, OR-Tools CP-SAT, HiGHS (scipy.optimize.milp) each solve a 3-variable integer program to the brute-force optimum (27); statsforecast AutoARIMA+AutoETS and Prophet each produce a 13-step weekly forecast.
- **Decision:** Primary solver OR-Tools (SCIP via pywraplp for the lot-sizing MIP; CP-SAT for sequencing if ADR-003 chooses decomposition). HiGHS remains an alternative. Forecasting: statsforecast (ARIMA/ETS) + Prophet. Prophet installed from `requirements-optional.txt` (install took ~23 s; no cmdstan problems observed), so T3.2.2 stays P1, not cut.
- **Versions:** pinned in `requirements.txt` / `requirements-optional.txt`.
- **Caveats:** the smoke problem is trivial; solver *performance* on the 12-SKU x 13-week model is tested in T4.2.1. statsforecast fit took ~13 s for one short series including JIT warm-up; budget real runtime in T3.2.1. Gurobi not used so reviewers can reproduce without a licence.
