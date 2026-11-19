"""Single source of truth for the backlog.

Edit THIS file (not the generated files), then run:  python tools/backlog.py build
Status is tracked separately in backlog/status.json (never overwritten by build).
"""

EPIC = {
    "id": "EPIC-1",
    "title": "Shelf-Life-Aware Production Planner",
    "goal": (
        "Forecast weekly demand for perishable SKUs, then optimise production quantities, sequencing "
        "and safety stock (MIP) under line capacity, allergen changeover rules, shelf-life limits and "
        "demand uncertainty; quantify the improvement over a fair naive baseline in expired waste, "
        "stockouts and changeover hours."
    ),
}

SUBEPICS = {
    "SE1": "Domain Research & Problem Framing",
    "SE2": "Data Acquisition & Synthetic Plant Model",
    "SE3": "Demand Forecasting",
    "SE4": "Baseline Planner & Optimisation Model",
    "SE5": "Experiment, Validation & Sensitivity Study",
    "SE6": "Interface / Dashboard",
    "SE7": "Documentation & Portfolio Packaging",
}

# story id -> (sub-epic, title, as_a, i_want, so_that)
STORIES = {
    "S1.1": ("SE1", "Domain brief and KPI specification",
             "operations analyst", "a short domain brief and exact KPI definitions",
             "every model assumption is defensible to a plant or quality manager"),
    "S1.2": ("SE1", "Reproducible environment",
             "solo builder", "a scaffolded repo and a proven solver/forecasting toolchain on Windows",
             "later work is not blocked by setup surprises"),
    "S2.1": ("SE2", "Weekly demand panel",
             "demand planner", "a clean weekly demand panel for 12 perishable SKUs from real retail data",
             "forecasts reflect real seasonality, noise and intermittency"),
    "S2.2": ("SE2", "Documented synthetic plant",
             "plant planner", "a documented plant (line, rates, shelf lives, allergens, changeovers, costs)",
             "the optimiser solves a realistic, citable constrained problem"),
    "S3.1": ("SE3", "Forecast evaluation harness",
             "demand planner", "a leak-free rolling-origin backtest with standard metrics",
             "model comparisons are trustworthy"),
    "S3.2": ("SE3", "Statistical forecasting models",
             "demand planner", "ARIMA/ETS and Prophet compared against naive benchmarks",
             "I can justify which forecast feeds the planner"),
    "S3.3": ("SE3", "Forecast uncertainty",
             "supply chain analyst", "calibrated forecast-error distributions and demand scenarios",
             "safety stock and stress tests reflect real forecast error"),
    "S4.1": ("SE4", "Simulator and naive baseline",
             "operations analyst", "a trusted plant simulator and a defensible baseline plan",
             "improvements are measured against a fair comparator, not a strawman"),
    "S4.2": ("SE4", "Core MIP with allergen sequencing",
             "production planner", "an optimiser that sizes and sequences runs under capacity, shelf life and allergen rules",
             "plans cut waste and changeover time without violating food-safety rules"),
    "S4.3": ("SE4", "Service level, rolling horizon and independent checking",
             "production planner", "safety-stock logic, weekly re-planning and an independent plan checker",
             "plans are realistic, re-plannable and provably feasible"),
    "S5.1": ("SE5", "Quantified comparison vs baseline",
             "plant manager reviewing results", "paired, statistically sound KPI comparisons with confidence intervals",
             "I can trust the claimed improvement"),
    "S5.2": ("SE5", "Sensitivity and trade-off analysis",
             "plant manager reviewing results", "to see where the advantage holds, shrinks or vanishes",
             "I understand the limits of the result"),
    "S6.1": ("SE6", "Core dashboard",
             "non-technical reviewer", "a dashboard showing KPIs, forecasts and weekly plans",
             "I can grasp the result in two minutes without reading code"),
    "S6.2": ("SE6", "Explorer and run guide",
             "non-technical reviewer", "to explore scenarios and launch the app easily",
             "I can test my own what-ifs"),
    "S7.1": ("SE7", "Project documentation",
             "hiring manager or interviewer", "a README, assumptions register and limitations section",
             "I can judge rigor and reproduce the work"),
    "S7.2": ("SE7", "Portfolio packaging and QA",
             "the builder", "resume bullets, pitch and a clean-clone reproducibility check",
             "the project is interview-ready and every claim traces to an artifact"),
}

# Ticket fields: id, title, type, story, est (hours), prio, week, deps, desc, ac (list), deliverable
T = []
def t(**kw):
    T.append(kw)

# ---------------------------------------------------------------- SE1
t(id="T1.1.1", title="Spike: verify public data sources and access", type="Spike", story="S1.1",
  est=1.5, prio="P0", week=1, deps=[],
  desc=("TIME BOX 1.5h. Confirm that the candidate public datasets exist, can be downloaded by a free account, "
        "and what their terms are. Candidates: Corporacion Favorita Grocery Sales Forecasting (Kaggle; train.csv, "
        "items.csv with `perishable` flag), M5 Forecasting (Walmart, Kaggle; FOODS department) as fallback, "
        "USDA FSIS FoodKeeper (CC0 JSON on data.gov) for shelf-life anchors. Actually open the files; do not rely on descriptions."),
  ac=["docs/research/data_sources.md has a table: dataset, URL, licence/terms, access method, files, date range, row counts - each confirmed by opening the file",
      "Favorita items.csv confirmed to contain item_nbr, family, class, perishable; train.csv date range recorded",
      "FoodKeeper JSON downloaded and the fields used for shelf life (product name, min/max, metric) listed",
      "docs/decisions/ADR-001-data-source.md records primary source and fallback (M5 FOODS, or fully synthetic demand calibrated to published retail patterns) and the trigger for fallback",
      "If Kaggle access fails inside the time box the fallback is invoked and recorded; spike is closed either way"],
  deliverable="docs/research/data_sources.md, docs/decisions/ADR-001-data-source.md")

t(id="T1.1.2", title="Write domain brief and KPI definitions", type="Task", story="S1.1",
  est=3, prio="P0", week=1, deps=[],
  desc=("Write a <=4-page brief the builder can defend in an interview. Cover: FDA major food allergens (9, incl. sesame "
        "since 1 Jan 2023 under the FASTER Act); FSMA Preventive Controls for Human Food (21 CFR Part 117) allergen "
        "cross-contact controls and sanitation; why allergen changeovers need cleaning (residue of allergen X must not "
        "reach a product not declaring X) and typical verification (swab/ATP/allergen test kits); shelf-life vocabulary "
        "(date of manufacture, best-by/use-by, FEFO vs FIFO, customer minimum remaining shelf life at receipt); lot sizing, "
        "changeovers, safety stock; OEE context (this project does not model OEE losses explicitly - say so). "
        "Then write the KPI spec."),
  ac=["docs/research/domain_brief.md exists, <=4 pages, each factual claim has a citation link or is tagged UNVERIFIED",
      "docs/research/kpi_definitions.md defines, with formula, unit and denominator: expired waste (cases and % of produced), fill rate, lost cases, stockout-SKU-weeks, changeover hours, line utilisation, weeks of cover, WAPE, bias, MASE",
      "Each KPI lists the future code function name (placeholder) and the results column it will populate",
      "A glossary of >=15 terms is included (e.g. FEFO, cross-contact, CIP/wet clean, MSL, WAPE, lot sizing)",
      "A list of 'things I am unsure about' is included and copied to docs/assumptions.md as OPEN items"],
  deliverable="docs/research/domain_brief.md, docs/research/kpi_definitions.md")

t(id="T1.2.1", title="Scaffold repo, environment, lint and test tooling", type="Task", story="S1.2",
  est=1.5, prio="P0", week=1, deps=[],
  desc=("Create pyproject.toml, requirements.txt (pinned runtime), requirements-dev.txt (pytest, ruff, jupyter), "
        ".gitignore (data/raw, data/interim, large results), pytest config, ruff config and a smoke test. "
        "Follow docs/planning/06_repo_structure.md. `git init` and make the first commit."),
  ac=["Fresh venv: `pip install -r requirements.txt -r requirements-dev.txt` succeeds",
      "`pytest` passes (>=1 smoke test) and `ruff check .` is clean",
      "Folder tree matches docs/planning/06_repo_structure.md",
      "data/raw and data/interim are git-ignored; `git status` shows no data files",
      "`python tools/backlog.py check` still passes"],
  deliverable="pyproject.toml, requirements*.txt, .gitignore, tests/test_smoke.py")

t(id="T1.2.2", title="Spike: smoke-test OR-Tools, statsforecast and Prophet on Windows", type="Spike", story="S1.2",
  est=1.5, prio="P0", week=1, deps=["T1.2.1"],
  desc=("TIME BOX 1.5h. Prove the toolchain works before depending on it. scripts/smoke_solvers.py solves a 5-variable MILP "
        "with OR-Tools (SCIP via pywraplp and CP-SAT) and, if feasible, HiGHS via scipy.optimize.milp; fits Prophet and "
        "statsforecast AutoARIMA on a toy weekly series. Prophet on Windows is a known install risk (cmdstan)."),
  ac=["scripts/smoke_solvers.py runs end to end and prints solver names, objective values and elapsed time",
      "docs/decisions/ADR-002-toolchain.md states final library choices and versions",
      "If Prophet cannot be installed inside the time box, ADR-002 records the fallback (statsforecast + statsmodels only) and T3.2.2 is moved to the P2 cut list",
      "requirements.txt updated with verified pinned versions"],
  deliverable="scripts/smoke_solvers.py, docs/decisions/ADR-002-toolchain.md")

# ---------------------------------------------------------------- SE2
t(id="T2.1.1", title="Build weekly demand panel for 12 perishable SKUs", type="Task", story="S2.1",
  est=4.5, prio="P0", week=2, deps=["T1.1.1", "T1.2.1"],
  desc=("Implement scripts/download_data.py (Kaggle API, or printed manual instructions) and src/shelflife/data/favorita.py. "
        "Select 12 SKUs with perishable=1 across 4-5 families (e.g. DAIRY, DELI, PREPARED FOODS, BREAD/BAKERY, EGGS) using a "
        "written rule (e.g. top volume among items non-zero in >=95% of weeks). Aggregate daily to weekly (Mon-Sun) and across "
        "all stores (a DC-level proxy). Handle: missing calendar days (e.g. 25 Dec absent in the source), negative sales "
        "(returns: clip to 0 and log count), fractional units (weighed items), partial first/last weeks (drop). "
        "Do not commit raw data. Include a short EDA notebook."),
  ac=["data/processed/demand_weekly.parquet has columns sku_id, item_nbr, family, week_start, units; exactly 12 SKUs; no NaN; contiguous weeks per SKU; >=200 weeks per SKU",
      "SKU selection rule is written in the notebook and reproduced by code; selected item_nbr list saved to configs/skus.yaml",
      "pytest checks: schema, contiguity, non-negativity; rebuild is deterministic (file hash equal on two runs)",
      "notebooks/01_demand_eda.ipynb shows per-SKU time plot, seasonality (week-of-year) and CV / zero-share table",
      "`git status` shows no raw data committed; docs/assumptions.md records the 'retail sales as DC demand proxy' assumption"],
  deliverable="data/processed/demand_weekly.parquet, src/shelflife/data/favorita.py, notebooks/01_demand_eda.ipynb")

t(id="T2.2.1", title="Define synthetic plant parameters with sources", type="Task", story="S2.2",
  est=2.5, prio="P0", week=1, deps=["T1.1.2", "T1.2.1"],
  desc=("Create configs/plant.yaml for a hypothetical refrigerated prepared-foods plant: one filling/packing line (the single "
        "bottleneck), weekly buckets. For each of 12 SKUs: family, allergen set (subset of the Big 9, assigned by family with "
        "rationale), shelf life at manufacture (days; anchored to USDA FoodKeeper ranges for comparable products where one exists, "
        "otherwise flagged ASSUMPTION), line rate (cases/h), minimum and maximum run size, unit cost. Line: weekly available "
        "hours (e.g. 2 shifts x 5 days x 8h less planned sanitation/maintenance), minimum remaining shelf life at shipment (%). "
        "Every parameter carries a `source:` field = citation URL | 'assumption' + plausible range."),
  ac=["configs/plant.yaml loads through a pydantic (or dataclass) schema in src/shelflife/plant/config.py with validation errors on missing source",
      "Every parameter has a non-empty source; count of 'assumption' parameters is printed by `python -m shelflife.plant.config --report`",
      "Allergen sets only use the 9 FDA major allergens (validated in code)",
      "Shelf lives are 14-56 days for all SKUs (weekly-bucket model is invalid outside this; documented)",
      "docs/assumptions.md created with one row per assumption: ID, value, range, source, sensitivity-tested (Y/N, link)"],
  deliverable="configs/plant.yaml, src/shelflife/plant/config.py, docs/assumptions.md")

t(id="T2.2.2", title="Allergen changeover matrix and capacity calibration", type="Task", story="S2.2",
  est=3, prio="P0", week=2, deps=["T2.1.1", "T2.2.1"],
  desc=("Implement src/shelflife/plant/changeover.py. Rule: changeover i->j = base time (label/format) + allergen clean time if "
        "SKU i carries any allergen NOT declared on SKU j (residue would be an undeclared allergen); smaller clean/flavour-change "
        "time otherwise; allergen-free to anything is cheap. Times come from config ranges (assumptions; no public per-line dataset "
        "exists - flag it). Also calibrate a demand scale factor so that the baseline-style weekly load (production hours + "
        "changeovers) averages ~85% of available hours (a TARGET calibration assumption) and save to configs/calibration.yaml."),
  ac=["pytest: for 10 hand-written SKU pairs, the matrix matches the expected clean/no-clean decision (incl. subset case: i={milk}, j={milk,soy} needs no allergen clean; i={milk,soy}, j={milk} does)",
      "Matrix is asymmetric where the rule says it should be; diagonal is 0",
      "docs/figures/changeover_heatmap.png exists",
      "configs/calibration.yaml contains scale_factor and the achieved mean utilisation (printed by scripts/calibrate.py)",
      "Changeover time ranges are listed in docs/assumptions.md as ASSUMPTION with low/base/high values"],
  deliverable="src/shelflife/plant/changeover.py, configs/calibration.yaml, docs/figures/changeover_heatmap.png")

# ---------------------------------------------------------------- SE3
t(id="T3.1.1", title="Rolling-origin backtest harness and naive benchmarks", type="Task", story="S3.1",
  est=2.5, prio="P0", week=2, deps=["T2.1.1"],
  desc=("src/shelflife/forecast/backtest.py. Windows: train >=104 weeks; VALIDATION year (52 weekly origins) used for model "
        "selection and error calibration; TEST year (final 52 weeks) used only for reporting. Expanding window, horizons 1-13. "
        "Metrics: WAPE, bias (signed % error), MASE. Benchmarks: naive, seasonal naive (52w), 4-week moving average. "
        "Standard output schema: sku_id, origin, horizon, target_week, y, yhat, model, window."),
  ac=["Output parquet follows the schema above for each benchmark model",
      "pytest leakage test: for every row, all training data < origin <= target_week",
      "results/forecast/benchmark_metrics.csv has WAPE/bias/MASE per SKU and aggregate for validation and test windows",
      "Window boundaries (dates) are written to configs/windows.yaml and asserted in tests",
      "Re-running with the same inputs gives identical metrics"],
  deliverable="src/shelflife/forecast/backtest.py, results/forecast/benchmark_metrics.csv, configs/windows.yaml")

t(id="T3.2.1", title="ARIMA and ETS forecasts via the harness", type="Task", story="S3.2",
  est=2.5, prio="P0", week=3, deps=["T3.1.1", "T1.2.2"],
  desc=("Run statsforecast AutoARIMA and AutoETS (consider log1p transform for positivity) for all 12 SKUs x validation+test "
        "origins x horizons 1-13 through the harness. Log runtime. Produce residual diagnostics."),
  ac=["Forecast parquet for both models in the harness schema, no missing (sku, origin, horizon) combinations",
      "Metrics appended to results/forecast/model_metrics.csv (validation and test windows)",
      "ACF plot of residuals for 2 SKUs saved to results/figures/",
      "Total runtime recorded in results/logs/forecast_runtime.txt (<30 min target)",
      "Forecasts are non-negative after post-processing (assertion)"],
  deliverable="src/shelflife/forecast/arima_ets.py, results/forecast/model_metrics.csv")

t(id="T3.2.2", title="Prophet forecasts via the harness", type="Task", story="S3.2",
  est=2.5, prio="P1", week=3, deps=["T3.1.1", "T1.2.2"],
  desc=("Weekly Prophet with yearly seasonality (and Ecuadorian holiday effects only if they improve validation WAPE); same "
        "harness and schema. Cache fits. If T1.2.2 showed Prophet cannot be installed, mark this ticket cut and record it."),
  ac=["Prophet forecast parquet in the harness schema, same coverage as T3.2.1",
      "Metrics appended to results/forecast/model_metrics.csv",
      "Decision on holidays (kept/dropped) recorded with validation WAPE evidence in docs/methods/forecasting.md",
      "Fits are cached (second run < 10% of first-run time)"],
  deliverable="src/shelflife/forecast/prophet_model.py, docs/methods/forecasting.md")

t(id="T3.2.3", title="Model selection on validation year; report test accuracy", type="Task", story="S3.2",
  est=1.5, prio="P0", week=3, deps=["T3.2.1"],
  desc=("Select the forecast model per SKU (or a single global model if differences are small) using VALIDATION-window WAPE "
        "only. Report test-year accuracy for all models and the selected one vs seasonal naive. Export the test-year forecast "
        "table (all origins, horizons 1-13) consumed by the planner."),
  ac=["configs/forecast_selection.yaml lists model per SKU; a test asserts selection code never reads the test window",
      "results/forecast/headline_forecast.csv: aggregate test WAPE of selected model vs seasonal naive and vs 4-wk MA, with relative improvement",
      "results/forecast/forecasts_test.parquet contains selected-model forecasts for all test origins and horizons 1-13",
      "If improvement over seasonal naive is below the 10% target, this is stated plainly in docs/methods/forecasting.md (no spin)"],
  deliverable="configs/forecast_selection.yaml, results/forecast/headline_forecast.csv, results/forecast/forecasts_test.parquet")

t(id="T3.3.1", title="Forecast-error sigma table and demand-scenario generator", type="Task", story="S3.3",
  est=2.5, prio="P0", week=3, deps=["T3.2.3"],
  desc=("From VALIDATION-year residuals of the selected models, build per-SKU, per-horizon error standard deviations "
        "(results/forecast/error_sigma.csv) used for safety stock, and a block-bootstrap scenario generator (block length "
        "4 weeks, standardised errors) producing N demand paths around the test-origin forecasts. Check calibration of "
        "80% and 95% intervals on the TEST year."),
  ac=["results/forecast/error_sigma.csv has sku_id x horizon rows, all sigma > 0",
      "src/shelflife/forecast/scenarios.py: generate(n_paths, seed) is reproducible and yields non-negative demand with shape (n_paths, 12, 52)",
      "Empirical coverage of 80% and 95% intervals on test year is reported; within +/-5 points is the target, deviations are documented",
      "Test asserts that sigma uses only validation-window residuals",
      "Plot of 20 sample paths vs actuals for 1 SKU saved to results/figures/"],
  deliverable="src/shelflife/forecast/scenarios.py, results/forecast/error_sigma.csv")

# ---------------------------------------------------------------- SE4
t(id="T4.1.1", title="Plant simulator with age cohorts, FEFO and KPI accounting", type="Task", story="S4.1",
  est=4, prio="P0", week=4, deps=["T2.2.2"],
  desc=("src/shelflife/sim/engine.py. Weekly loop given a production plan (quantity and sequence per week) and a demand path: "
        "add production as a new age-0 cohort; ship FEFO only units that satisfy minimum remaining shelf life; expire units "
        "older than shelf life (integer weeks); record lost sales on shortfall; compute changeover hours from the sequence "
        "(including carry-over from last week's final SKU) and flag capacity breaches. Output weekly KPI table per kpi_definitions.md."),
  ac=["pytest invariant over 1000 random plans: produced = shipped + expired + ending inventory (+ initial inventory) for every SKU",
      "A hand-computed 3-SKU x 4-week example (committed as tests/fixtures/handcalc.md and .json) matches simulator output exactly",
      "Simulator is deterministic (same inputs -> identical KPI frame)",
      "KPI column names match docs/research/kpi_definitions.md",
      "52-week x 12-SKU simulation runs in < 5 seconds"],
  deliverable="src/shelflife/sim/engine.py, tests/test_sim_invariants.py, tests/fixtures/handcalc.md")

t(id="T4.1.2", title="Naive baseline planner (B1) with documented rationale", type="Task", story="S4.1",
  est=2.5, prio="P0", week=4, deps=["T4.1.1", "T3.1.1", "T2.2.2"],
  desc=("Implement baseline B1, a realistic good-practice spreadsheet planner, NOT a strawman: forecast = 4-week moving average; "
        "weekly production = forecast demand + fixed 1-week cover top-up, scaled pro-rata if capacity is exceeded; sequence = "
        "fixed static 'allergen ladder' (fewest allergens first, most last, wet clean at end of cycle); FEFO. Document why this "
        "is fair and what it deliberately does not do (no shelf-life awareness, no dynamic sequencing)."),
  ac=["docs/methods/baseline.md defines B1 rules numerically and gives a 'why this is not a strawman' paragraph",
      "Baseline plan is capacity-feasible for all 52 test weeks (checked by simulator flag)",
      "52-week test replay runs in < 1 minute and writes results/baseline_replay.csv with all KPIs",
      "Baseline KPI values are plausible: expired waste > 0 and fill rate < 100% (else baseline is miscalibrated; recalibrate T2.2.2 or document)",
      "Unit test: with zero demand the baseline produces zero (no phantom production)"],
  deliverable="src/shelflife/sim/baseline.py, docs/methods/baseline.md, results/baseline_replay.csv")

t(id="T4.2.1", title="Spike: choose MIP formulation (single model vs decomposition)", type="Spike", story="S4.2",
  est=2.5, prio="P0", week=4, deps=["T1.2.2", "T2.2.2"],
  desc=("TIME BOX 2.5h. Compare (A) one MIP with arc-based sequencing within each week (carry-over from prior week) against "
        "(B) decomposition: lot-sizing MIP with setup binaries and allergen-class setup estimates, then a CP-SAT circuit/TSP "
        "sequencing per week. Test on a 4-SKU x 8-week toy and a 12-SKU x 13-week instance. Also choose solver "
        "(OR-Tools SCIP / CP-SAT vs HiGHS). Record solve times and optimality gaps."),
  ac=["notebooks/02_formulation_spike.ipynb contains both approaches on the toy instance with results table (solve time, gap, objective)",
      "docs/decisions/ADR-003-formulation.md states the choice, the evidence and the decision criterion: 12x13 instance reaches <=2% gap or a 120s time limit with a feasible incumbent",
      "Known limitations of the chosen approach (e.g. decomposition may be suboptimal) are listed",
      "Time box respected; if no approach hits the criterion, ADR records the fallback (decomposition + heuristic sequencing)"],
  deliverable="notebooks/02_formulation_spike.ipynb, docs/decisions/ADR-003-formulation.md")

t(id="T4.2.2", title="Core lot-sizing MIP with age cohorts and shelf life", type="Task", story="S4.2",
  est=4, prio="P0", week=5, deps=["T4.2.1", "T4.1.1"],
  desc=("src/shelflife/opt/model.py. Variables: production x[p,t], run indicator y[p,t], inventory by age cohort I[p,a,t], shipments, "
        "lost sales, expiry. Constraints: capacity (run hours + placeholder average changeover), min/max run size, cohort balance, "
        "ageing, minimum remaining shelf life at shipment. Soft demand satisfaction with lost-sales penalty. Objective weights from "
        "configs/costs.yaml (production, holding, expiry, lost sale, changeover). Document full math in docs/methods/optimization.md."),
  ac=["docs/methods/optimization.md has sets, parameters, variables, objective and every constraint in math notation",
      "A 2-SKU x 4-week toy instance is solved by hand/brute force and matches the solver objective exactly (tests/test_model_toy.py)",
      "12-SKU x 13-week model builds in < 10 s and solves with status logged (results/logs/)",
      "Infeasible/over-capacity input returns a clear status, not an exception (tested)",
      "LP file of the toy instance committed for inspection (tests/fixtures/toy.lp)"],
  deliverable="src/shelflife/opt/model.py, docs/methods/optimization.md, tests/test_model_toy.py")

t(id="T4.2.3", title="Allergen-aware changeover and sequencing in the optimiser", type="Task", story="S4.2",
  est=4, prio="P0", week=5, deps=["T4.2.2", "T4.2.1"],
  desc=("Add sequencing per ADR-003, including carry-over of the last SKU run in the previous week. Changeover hours come from the "
        "T2.2.2 matrix and consume capacity. The result must output an explicit run order per week."),
  ac=["Regression test: with all changeover times set to 0 the objective equals the T4.2.2 result",
      "Hand example where the allergen matrix forces a unique cheapest order; solver returns that order (test)",
      "Recomputed changeover hours from the output sequence equal the solver's changeover variable (assert on 5 instances)",
      "Output plan schema documented (week, line position, sku_id, qty, changeover_hours_before, clean_type)",
      "docs/methods/optimization.md updated with sequencing constraints"],
  deliverable="src/shelflife/opt/sequencing.py, tests/test_sequencing.py")

t(id="T4.3.1", title="Safety-stock constraints from forecast error", type="Task", story="S4.3",
  est=2.5, prio="P0", week=6, deps=["T4.2.2", "T3.3.1"],
  desc=("Add soft lower bounds on projected end-of-week usable inventory: SS[p,t] = z(alpha) * sigma[p,h] (sigma from T3.3.1), "
        "with a shortfall variable and penalty, capped by what the shelf-life window allows. alpha is a parameter (default 95%, a "
        "TARGET service level assumption)."),
  ac=["Unit test: raising alpha from 0.80 to 0.99 raises mean safety stock monotonically",
      "SS cap by shelf-life window is implemented and tested on a slow-moving, short-shelf-life toy SKU",
      "Shortfall variable and penalty appear in docs/methods/optimization.md",
      "Model with SS builds and solves on the 12x13 instance within the time limit"],
  deliverable="src/shelflife/opt/safety_stock.py, tests/test_safety_stock.py")

t(id="T4.3.2", title="Rolling-horizon driver with logging and fallback", type="Task", story="S4.3",
  est=2, prio="P0", week=6, deps=["T4.2.3", "T4.3.1", "T3.2.3", "T4.1.1", "T4.3.3"],
  desc=("src/shelflife/opt/rolling.py. Each week: take that origin's 13-week forecast, solve with a 60s limit, freeze week 1, "
        "advance the simulator with actual demand, carry inventory, log solve status/gap/time. If no feasible incumbent, fall back "
        "to the B1 plan for that week and count it."),
  ac=["52-week test replay completes and writes results/optimized_replay.csv with the same KPI columns as the baseline",
      "results/logs/solves.csv has one row per week: status, gap, solve_seconds, fallback_used",
      "Number of fallback weeks is reported (target: 0; investigate if > 2)",
      "Every executed plan passes the independent checker (T4.3.3) - replay aborts otherwise",
      "Total replay runtime recorded (target < 90 min)"],
  deliverable="src/shelflife/opt/rolling.py, results/optimized_replay.csv, results/logs/solves.csv")

t(id="T4.3.3", title="Independent plan feasibility checker", type="Task", story="S4.3",
  est=2, prio="P0", week=5, deps=["T4.2.2"],
  desc=("src/shelflife/checks/plan_checker.py re-validates any plan (baseline or optimised) against capacity, run-size limits, "
        "shelf-life/min-remaining rules and allergen/changeover accounting. It must not import the optimiser module, so it is an "
        "independent check."),
  ac=["Checker module has no import from shelflife.opt (verified by a test that scans imports)",
      "5 mutation tests: deliberately corrupted plans (over capacity, below min run, wrong changeover accounting, expired shipment, missing clean) are all rejected with specific messages",
      "Baseline and optimised toy plans both pass",
      "CLI: `python -m shelflife.checks.plan_checker <plan.parquet>` prints PASS/FAIL list"],
  deliverable="src/shelflife/checks/plan_checker.py, tests/test_plan_checker.py")

# ---------------------------------------------------------------- SE5
t(id="T5.1.1", title="Experiment runner: historical replay and Monte Carlo", type="Task", story="S5.1",
  est=3.5, prio="P0", week=6, deps=["T4.3.2", "T4.1.2", "T3.3.1"],
  desc=("scripts/run_experiment.py with a YAML config. Layer A: historical replay (real demand, real out-of-sample forecasts), "
        "baseline vs optimised, 52 weeks. Layer B: Monte Carlo with N demand paths (pilot to pick N; target 200) using common "
        "random numbers: baseline and optimised see identical paths. Save per-run KPI tables, config snapshot and git hash."),
  ac=["`python scripts/run_experiment.py --config configs/experiment_main.yaml` runs from a clean state and writes results/experiments/<run_id>/{kpis.parquet,config.yaml,meta.json}",
      "Paired structure verified: same scenario ids and seeds for both arms (test)",
      "Re-running with the same seed reproduces identical KPIs (hash comparison)",
      "Pilot (N=30) used to choose N so the bootstrap CI half-width on % waste reduction is <= 3 points (target); pilot output recorded",
      "Limitation recorded: in Monte Carlo layer, later-origin forecasts are not refit to simulated paths"],
  deliverable="scripts/run_experiment.py, configs/experiment_main.yaml, results/experiments/")

t(id="T5.1.2", title="Statistical analysis and headline numbers", type="Task", story="S5.1",
  est=2.5, prio="P0", week=7, deps=["T5.1.1"],
  desc=("src/shelflife/analysis/stats.py. For each KPI: paired differences, percentile-bootstrap 95% CI (10,000 resamples) on mean "
        "difference and on relative reduction (1 - mean_opt/mean_base), Wilcoxon signed-rank as a secondary check, effect sizes. "
        "Write the single source of truth for resume numbers: results/headline_numbers.json."),
  ac=["results/headline_numbers.json contains estimate, ci_lo, ci_hi for: expired_waste_reduction_pct, fill_rate_delta_pts, changeover_hours_reduction_pct, forecast_wape_improvement_pct, plus the replay (Layer A) point values and N",
      "Test on synthetic data with a known true effect: bootstrap CI covers the truth in >=90% of 100 trials",
      "Figure results/figures/kpi_comparison.png (paired differences with CIs)",
      "Report states effect sizes and CIs as primary; p-values secondary (N is a computing choice)",
      "A 'result is not what I hoped' section exists in docs/results/summary.md if any target is missed"],
  deliverable="src/shelflife/analysis/stats.py, results/headline_numbers.json, docs/results/summary.md")

t(id="T5.1.3", title="Ablation: forecasting vs optimisation contribution", type="Task", story="S5.1",
  est=2, prio="P2", week=None, deps=["T5.1.1", "T3.2.3"],
  desc=("Four arms: B1; B1 with the selected forecast; optimiser with the 4-week MA forecast; full system. Attribute improvement to "
        "better forecasts vs better optimisation."),
  ac=["Config configs/experiment_ablation.yaml and results table results/ablation.csv with the 4 arms and KPIs",
      "Stacked/grouped bar chart results/figures/ablation.png",
      "Two-sentence interpretation added to docs/results/summary.md"],
  deliverable="results/ablation.csv, results/figures/ablation.png")

t(id="T5.2.1", title="Sensitivity sweeps and waste-vs-service frontier", type="Task", story="S5.2",
  est=3, prio="P1", week=7, deps=["T5.1.1"],
  desc=("Grid in configs/sensitivity.yaml, one-at-a-time: shelf life (-50/-25/0/+25%), changeover times (x0.5/1/1.5/2), forecast "
        "error scale (x0.5/1/1.5/2), utilisation (70/80/85/90/95%), minimum remaining shelf life (30/50/70%), cost weight ratios. "
        "Frontier: sweep baseline weeks-of-cover (0.5-3) and optimiser alpha (80-99%), plotting expired waste vs fill rate so that "
        "improvements are compared at matched service level. Use reduced N (e.g. 50) per cell and say so."),
  ac=["results/sensitivity/*.parquet exist for each swept parameter with the config used",
      "All cells reuse common random numbers and are paired baseline-vs-optimised",
      "Frontier data file includes both arms across the full cover/alpha range",
      "Runtime budget and reduced N documented in docs/methods/sensitivity.md"],
  deliverable="configs/sensitivity.yaml, results/sensitivity/")

t(id="T5.2.2", title="Sensitivity charts and honest robustness statement", type="Task", story="S5.2",
  est=1.5, prio="P1", week=7, deps=["T5.2.1"],
  desc=("Tornado chart of % waste reduction vs each parameter, the frontier chart, and a break-even analysis: where does the advantage "
        "shrink or vanish (e.g. low utilisation, very low forecast error)? Write the findings."),
  ac=["results/figures/tornado.png and results/figures/frontier.png exist and are legible in grayscale",
      "docs/results/sensitivity_findings.md has >=3 findings, each citing a figure, plus a 'where it does NOT help' paragraph",
      "headline_numbers.json extended with share_of_cells_improved and a sensitivity section against the headline baseline "
      "(ADR-009: a % waste reduction is unbounded when the tuned baseline's waste is near zero, so cost, waste in points of "
      "production and fill-rate change are reported per cell)"],
  deliverable="results/figures/tornado.png, results/figures/frontier.png, docs/results/sensitivity_findings.md")

# ---------------------------------------------------------------- SE6
t(id="T6.1.1", title="Streamlit KPI overview and forecast pages", type="Task", story="S6.1",
  est=2.5, prio="P0", week=7, deps=["T5.1.2", "T3.2.3"],
  desc=("app/streamlit_app.py multipage. Overview: KPI cards (baseline vs optimised with CI) read from headline_numbers.json, "
        "waste and fill-rate by SKU, weekly trend. Forecast page: actual vs forecast with interval for a chosen SKU. Reads only "
        "small committed files in results/app_data/ (<=20 MB total)."),
  ac=["`streamlit run app/streamlit_app.py` starts on a clean clone with no raw data and no code edits",
      "Every KPI card shows value, CI and the label 'simulation on a synthetic plant model'",
      "Numbers on the page equal headline_numbers.json (test reads both)",
      "Page loads in < 5 s locally; layout works at laptop width (screenshot committed)",
      "results/app_data/ total size <= 20 MB (checked by a test)"],
  deliverable="app/streamlit_app.py, app/pages/, results/app_data/")

t(id="T6.1.2", title="Weekly plan viewer: sequence Gantt and inventory age", type="Task", story="S6.1",
  est=2.5, prio="P0", week=8, deps=["T5.1.1", "T6.1.1"],
  desc=("Page showing, for a selected week and arm (baseline/optimised): a Gantt of the line sequence coloured by allergen profile with "
        "changeovers marked and the cleaning reason on hover; stacked bars of inventory by age against shelf-life limit per SKU."),
  ac=["Selecting week and arm updates the Gantt and age chart",
      "Hover shows SKU, quantity, allergen set, changeover hours and clean type",
      "Optimised and baseline views for the same week can be compared side by side",
      "Chart palette is colour-blind safe and passes the `dataviz` skill checks"],
  deliverable="app/pages/2_Weekly_Plan.py")

t(id="T6.2.1", title="Scenario explorer from precomputed sensitivity grid", type="Task", story="S6.2",
  est=2, prio="P2", week=None, deps=["T5.2.1", "T6.1.1"],
  desc="Sliders for shelf life, changeover multiplier and forecast-error scale that look up the precomputed grid (no live solving).",
  ac=["Moving a slider shows the matching precomputed result within 1 s",
      "Out-of-grid values snap to the nearest grid point and say so",
      "Page notes N used per cell"],
  deliverable="app/pages/3_Scenario_Explorer.py")

t(id="T6.2.2", title="Run guide, screenshots and optional free hosting", type="Task", story="S6.2",
  est=1, prio="P1", week=8, deps=["T6.1.1", "T6.1.2"],
  desc="docs/app_guide.md with 3-line launch instructions, 3 screenshots, and (optional) a Streamlit Community Cloud link.",
  ac=["Instructions tested in a fresh venv", "3 screenshots in docs/figures/", "If hosted, URL recorded in README; otherwise README says 'run locally'"],
  deliverable="docs/app_guide.md, docs/figures/app_*.png")

# ---------------------------------------------------------------- SE7
t(id="T7.1.1", title="README, assumptions register and limitations", type="Task", story="S7.1",
  est=3, prio="P0", week=8, deps=["T5.1.2", "T5.2.2"],
  desc=("Write README.md per docs/planning/06_repo_structure.md outline (problem, method, results, how to run, assumptions, "
        "limitations). Complete docs/assumptions.md and write >=6 limitations (e.g. synthetic plant, retail demand as DC proxy, "
        "weekly buckets, single line, no OEE loss model, Monte Carlo forecast non-refit)."),
  ac=["README has all 6 sections; results table pulls numbers from headline_numbers.json (no hand-typed numbers)",
      "Every assumption in docs/assumptions.md has source or 'assumption' tag and a link to its sensitivity result",
      "Limitations section has >=6 items and each states its likely direction of bias",
      "All relative links resolve (link check)"],
  deliverable="README.md, docs/assumptions.md")

t(id="T7.1.2", title="Two-page plant-manager memo (PDF)", type="Task", story="S7.1",
  est=1.5, prio="P2", week=None, deps=["T5.1.2"],
  desc="Two-page memo: situation, what changed in the plan, KPI results with CIs, risks, recommended rollout steps (pilot on 3 SKUs).",
  ac=["docs/results/plan_memo.pdf exists, 2 pages", "Every number matches headline_numbers.json", "Contains a 'what I would validate on real plant data' list"],
  deliverable="docs/results/plan_memo.pdf")

t(id="T7.2.1", title="Finalise resume bullets, pitch, slides and Q&A with real numbers", type="Task", story="S7.2",
  est=2, prio="P0", week=8, deps=["T5.1.2", "T5.2.2", "T7.1.1"],
  desc="Fill the placeholders in docs/portfolio/portfolio_pack.md with numbers from headline_numbers.json; build the 5-slide summary.",
  ac=["Each resume number appears verbatim in headline_numbers.json (manual check list in the doc)",
      "Every resume claim is qualified as 'simulated' or 'on a synthetic plant model'",
      "5-slide outline realised as docs/portfolio/summary_slides.pdf or .pptx",
      "Interview Q&A answers revised to match actual results, including any missed target"],
  deliverable="docs/portfolio/portfolio_pack.md, docs/portfolio/summary_slides.pdf")

t(id="T7.2.2", title="Clean-clone reproducibility and link QA", type="Task", story="S7.2",
  est=1.5, prio="P0", week=8, deps=["T7.1.1", "T6.2.2"],
  desc="Clone to a fresh directory, create a venv, run the quick pipeline, tests and app; fix breakages.",
  ac=["`python scripts/run_all.py --quick` reproduces headline numbers within the documented tolerance",
      "`pytest` passes; `ruff check .` clean", "App starts", "No secrets, Kaggle tokens or raw data in git history"],
  deliverable="docs/results/reproducibility_log.md")
