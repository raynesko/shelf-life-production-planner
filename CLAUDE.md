# CLAUDE.md - Shelf-Life-Aware Production Planner

Portfolio project: forecast weekly demand for perishable SKUs, then optimise production quantity, sequence and safety stock (MIP, OR-Tools) under line capacity, allergen changeover rules and shelf-life limits; compare to a fair baseline in simulation. Target audience: operations / supply chain / demand-planning hiring managers in food and pharma. The builder is a solo ISE grad student, ~9-10 h/week for 8 weeks.

## How to work here (agents)
1. **Find work:** `python tools/backlog.py next` -> open `backlog/tickets/<ID>.md`. Work only on one ticket at a time, in dependency order. Full plan: `docs/planning/` (read `01_charter.md` and `04_milestone_plan.md` once).
2. **Mark progress:** `python tools/backlog.py set <ID> in_progress` when starting, `done` only after every acceptance-criteria box is verified by running something or inspecting the artifact.
3. **Change the plan** only by editing `backlog/source/tickets.py` then `python tools/backlog.py build` and `check`. Never hand-edit `backlog/BACKLOG.md`, `backlog.csv`, or `backlog/tickets/*.md` (generated; status lives in `backlog/status.json`).
4. **Respect the time box** on Spike tickets; record the outcome in an ADR (`docs/decisions/ADR-NNN-*.md`) even when inconclusive.
5. Commit messages start with the ticket ID (`T4.2.2: ...`) once the repo is initialised (T1.2.1).

## Non-negotiable rules
- **Integrity of numbers:** every target is a *target*, not a result. Resume/README numbers come only from `results/headline_numbers.json`. If a target is missed, report the real value. Never fabricate, tune-to-hit, or hand-type results.
- **Label everything** "simulation on a synthetic plant model". No claim of real savings; no dollar figures.
- **No invented datasets.** Use Favorita (Kaggle), M5 (fallback), USDA FSIS FoodKeeper (CC0), or documented synthetic data. Every assumption lives in `docs/assumptions.md` with a source or `assumption` + range. Flag uncertainty instead of guessing (domain facts tagged UNVERIFIED if not checked).
- **No raw data, API tokens or secrets in git.** `data/raw` and `data/interim` are ignored; Kaggle terms forbid redistribution.
- **No test-set leakage:** model selection and error sigma use the validation year only; the test year is for reporting. Tests enforce this.
- **Independence of checking:** `shelflife.checks` must not import `shelflife.opt`.
- **Fair baseline:** B1 must stay a good-practice planner (see `docs/methods/baseline.md`); changes need an ADR.
- Prefer rigor over breadth; do not add scope (multi-line, BOMs, OEE, daily scheduling) without the builder's approval.

## Domain guardrails (use correct terminology)
- Allergens: FDA Big 9 (milk, egg, fish, crustacean shellfish, tree nuts, peanuts, wheat, soy, sesame - sesame since 1 Jan 2023, FASTER Act). Changeover i->j needs an allergen clean iff i has an allergen not declared on j.
- Shelf life: date of manufacture, best-by/use-by, FEFO, minimum remaining shelf life at shipment (assumption 50%). FoodKeeper = consumer storage guidance; use as ranges only.
- Weekly buckets; shelf life must stay within 14-56 days.
- Metrics: expired waste, fill rate, lost cases, changeover hours (allergen-clean hours separately), WAPE/bias/MASE. Definitions: `docs/research/kpi_definitions.md` (once T1.1.2 is done).

## Tech
- Python 3.12 (Windows 11; shell is PowerShell/Git Bash). Stdlib-only for `tools/`. Libraries (final list after T1.2.2): pandas, numpy, pyarrow, scipy, statsmodels, statsforecast, prophet (optional), ortools, pydantic, pyyaml, plotly, streamlit.
- Solvers: OR-Tools SCIP/CP-SAT (primary), HiGHS (alternative). Always set solver time limits and log status/gap.
- Seeds: every stochastic function takes an explicit `seed`; experiments save config + git hash.
- Tests: `pytest`; lint: `ruff check .`. Key tests: simulator conservation invariant, toy-MIP brute-force match, zero-changeover regression, plan-checker mutation tests, leakage tests.
- Charts: use the `dataviz` skill; colour-blind-safe, legible in greyscale.

## Layout (details: `docs/planning/06_repo_structure.md`)
`backlog/` plan and tickets | `docs/` planning, research, decisions (ADRs), methods, results, portfolio | `configs/` YAML parameters | `src/shelflife/{data,plant,forecast,sim,opt,checks,analysis}` | `scripts/` CLIs | `notebooks/` | `tests/` | `results/` | `app/` Streamlit | `tools/backlog.py`.

## Definition of Done
See `docs/planning/07_definition_of_done.md`. Short form: every AC box verified, tests + ruff pass, assumptions/ADRs recorded, status set to done.

## Current state
Venv `.venv` (use `./.venv/Scripts/python`). Data in: Favorita via Kaggle API (token at ~/.kaggle/access_token, outside repo) -> `python -m shelflife.data.favorita` builds `data/processed/demand_weekly.parquet` (git-ignored; 12 SKUs x 221 weeks, ADR-005 cutoff, demand unconstraining A-22). FoodKeeper from an Internet Archive snapshot.
Pipeline so far: `scripts/calibrate.py` (k = cases per Favorita unit, windows.yaml) -> `scripts/run_benchmarks.py` -> `scripts/run_baseline_replay.py`. Built modules: plant config/changeover, simulator (ADR-004), baseline B1 with reorder point (ADR-006), backtest harness, MIP (ADR-003: decomposition default), independent checker. 75 tests pass.
Key fact: seasonal naive is the WEAKEST benchmark here (test WAPE 17.6% vs MA4 11.5%); compare forecasts against the best benchmark (open question O-09 in docs/planning/09).
Code written, run order to resume (forecasting tickets still in_progress/todo in backlog):
1. wait for/redo `python scripts/run_stat_models.py --models arima52` (was running in background)
2. `python scripts/run_stat_models.py --models prophet prophet_hol`  (T3.2.2; keep holidays only if validation WAPE improves)
3. `python scripts/select_forecasts.py` (T3.2.3)  4. `python scripts/build_uncertainty.py` (T3.3.1)
5. `python scripts/run_rolling_replay.py` (T4.3.2; asserts baseline reproduces results/baseline_replay.csv)
So far: ETS test WAPE 11.11% vs MA4 11.48% (3% better); ARIMA worse than MA4. Safety stock (T4.3.1) and rolling driver built + tested.
