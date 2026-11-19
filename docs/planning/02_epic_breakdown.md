# 02 - Epic Breakdown

**EPIC-1: Shelf-Life-Aware Production Planner**

Full stories and tickets: `backlog/BACKLOG.md` (human-readable), `backlog/tickets/*.md` (one file per ticket, for agents), `backlog/backlog.csv` (tracker import).

| Order | Sub-epic | Weeks | Stories | Tickets | Hours | Exit criterion |
|---|---|---|---|---|---|---|
| 1 | **SE1** Domain Research & Problem Framing | 1 | S1.1, S1.2 | T1.1.1, T1.1.2, T1.2.1, T1.2.2 | 7.5 | Domain brief + KPI spec reviewed; data sources verified; toolchain proven |
| 2 | **SE2** Data Acquisition & Synthetic Plant Model | 1-2 | S2.1, S2.2 | T2.1.1, T2.2.1, T2.2.2 | 10 | 12-SKU weekly panel; plant.yaml with sources; changeover matrix tested |
| 3 | **SE3** Demand Forecasting | 2-3 | S3.1, S3.2, S3.3 | T3.1.1, T3.2.1-3, T3.3.1 | 11.5 | Leak-free backtest; selected model; sigma table + scenarios |
| 4 | **SE4** Baseline Planner & Optimisation Model | 4-6 | S4.1, S4.2, S4.3 | T4.1.1-2, T4.2.1-3, T4.3.1-3 | 23.5 | Simulator verified; B1 replay; MIP with allergen sequencing; rolling replay passes checker |
| 5 | **SE5** Experiment, Validation & Sensitivity | 6-7 (+stretch) | S5.1, S5.2 | T5.1.1-3, T5.2.1-2 | 12.5 | headline_numbers.json with CIs; tornado + frontier |
| 6 | **SE6** Interface / Dashboard | 7-8 (+stretch) | S6.1, S6.2 | T6.1.1-2, T6.2.1-2 | 8 | Streamlit app runs on clean clone |
| 7 | **SE7** Documentation & Portfolio Packaging | 8 (+stretch) | S7.1, S7.2 | T7.1.1-2, T7.2.1-2 | 9 | README, resume pack, clean-clone QA |

Build order rationale: data and the plant model must exist before forecasts and the simulator; the simulator and baseline must exist *before* the optimiser so that every optimisation result has a trusted comparator; the dashboard is built last on frozen results.
