# 06 - Repository & Documentation Structure

## Folder tree
```
shelf-life-production-planner/
|-- CLAUDE.md                  # agent instructions (read first)
|-- README.md                  # public-facing project page (finished in T7.1.1)
|-- pyproject.toml, requirements.txt, requirements-dev.txt   # created in T1.2.1
|-- backlog/
|   |-- source/tickets.py      # single source of truth (edit this)
|   |-- tickets/T*.md          # one file per ticket (generated; agents read these)
|   |-- BACKLOG.md             # generated full backlog
|   |-- backlog.csv            # generated, import to Jira/Linear/Notion/GitHub Projects
|   `-- status.json            # durable ticket status
|-- docs/
|   |-- planning/              # 01-09 planning docs (this folder)
|   |-- research/              # data_sources.md, domain_brief.md, kpi_definitions.md
|   |-- decisions/             # ADR-NNN-*.md
|   |-- methods/               # baseline.md, optimization.md, forecasting.md, sensitivity.md
|   |-- results/               # summary.md, sensitivity_findings.md, plan_memo.pdf, reproducibility_log.md
|   |-- portfolio/             # portfolio_pack.md, summary_slides.pdf
|   |-- figures/               # images used in docs/README
|   `-- assumptions.md         # assumption register
|-- configs/                   # plant.yaml, costs.yaml, skus.yaml, windows.yaml, calibration.yaml, experiment_*.yaml, sensitivity.yaml
|-- data/                      # raw/ interim/ (git-ignored) ; processed/ (small, committed if < 5 MB)
|-- src/shelflife/             # data/ plant/ forecast/ sim/ opt/ checks/ analysis/
|-- scripts/                   # download_data.py, calibrate.py, run_experiment.py, run_all.py, smoke_solvers.py
|-- notebooks/                 # 01_demand_eda, 02_formulation_spike, 05_results ...
|-- tests/                     # pytest; fixtures/
|-- results/                   # forecast/ experiments/ sensitivity/ figures/ app_data/ logs/ ; headline_numbers.json
|-- app/                       # streamlit_app.py, pages/
`-- tools/backlog.py           # backlog CLI
```

## Naming conventions
- Python: `snake_case` modules/functions, `PascalCase` classes; package `shelflife`.
- IDs: `EPIC-1`, `SEn`, `Sn.m`, `Tn.m.k`; ADRs `ADR-001-short-slug.md`; notebooks `NN_topic.ipynb`.
- Columns: `sku_id`, `week_start` (Monday, ISO date), `origin`, `horizon`, `units`/`cases`; hours as `*_hours`.
- Results: `results/experiments/<YYYYMMDD-HHMM>_<label>/` with `kpis.parquet`, `config.yaml`, `meta.json` (git hash, seeds).
- Figures: `results/figures/<topic>.png`, greyscale-legible, titled with units and the label "synthetic plant model".
- Commits: `T4.2.2: add cohort balance constraints` (ticket ID prefix).

## Requirements file plan
- `requirements.txt` (runtime, pinned after T1.2.2): pandas, numpy, pyarrow, scipy, statsmodels, statsforecast, prophet (optional), ortools, pydantic, pyyaml, plotly, streamlit, kaggle (download script only).
- `requirements-dev.txt`: pytest, hypothesis (optional), ruff, jupyter, nbformat.
- Python 3.12 (verified available on the builder's machine). Pin exact versions only after T1.2.2 proves them.

## README outline (T7.1.1)
1. **Problem** - one paragraph + one figure (waste/stockout/changeover trade-off).
2. **Method** - data, forecasting, baseline B1, MIP (one diagram), simulation and statistics.
3. **Results** - table from `headline_numbers.json` with CIs; frontier and tornado figures; the honest "where it does not help".
4. **How to run** - venv, `python scripts/run_all.py --quick`, `streamlit run app/streamlit_app.py`.
5. **Assumptions** - top 8 with link to `docs/assumptions.md`.
6. **Limitations** - >= 6, each with direction of bias.
Plus: data sources and licences, repo map, status badge (backlog done/total).
