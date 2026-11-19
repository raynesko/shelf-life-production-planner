# 04 - Milestone Plan

Hours per week are derived from `backlog/source/tickets.py`; run `python tools/backlog.py check` to confirm weekly load <= 10 h. Total scheduled P0/P1 = 75.5 h, stretch P2 = 5.5 h. **This is tight** against 8-10 h x 8 weeks (64-80 h): at 8 h/week apply the cut order below.

| Week | Tickets | Hours | End-of-week demo-able checkpoint |
|---|---|---|---|
| 1 | T1.1.1, T1.1.2, T1.2.1, T1.2.2, T2.2.1 | 10.0 | `pytest` green in fresh venv; `data_sources.md` with verified sources; domain brief + KPI spec; `plant.yaml` loads; solver/forecast smoke test prints results |
| 2 | T2.1.1, T2.2.2, T3.1.1 | 10.0 | Weekly demand plots for 12 SKUs; changeover heatmap; benchmark WAPE table |
| 3 | T3.2.1, T3.2.2, T3.2.3, T3.3.1 | 9.0 | Forecast model comparison chart; selected-model test WAPE vs seasonal naive; scenario fan chart |
| 4 | T4.1.1, T4.1.2, T4.2.1 | 9.0 | Simulator invariant tests green; **baseline KPI table (expired waste, fill rate, changeover hrs)**; ADR-003 formulation decision |
| 5 | T4.2.2, T4.2.3, T4.3.3 | 10.0 | Optimiser solves a 13-week plan with allergen sequencing; checker rejects mutated plans; first Gantt (notebook) |
| 6 | T4.3.1, T4.3.2, T5.1.1 | 8.0 | 52-week rolling replay baseline vs optimised (first look at the real gap); experiment runner CLI |
| 7 | T5.1.2, T5.2.1, T5.2.2, T6.1.1 | 9.5 | `headline_numbers.json` with CIs; tornado + frontier; Streamlit overview page live |
| 8 | T6.1.2, T6.2.2, T7.1.1, T7.2.1, T7.2.2 | 10.0 | Full app, README, resume pack with real numbers, clean-clone reproduction |

Stretch (unscheduled, only if ahead): T5.1.3 ablation (2 h), T6.2.1 scenario explorer (2 h), T7.1.2 plant memo (1.5 h).

## Critical path
```
T1.1.1 -> T2.1.1 -> T3.1.1 -> T3.2.1 -> T3.2.3 -> T3.3.1 -> T4.3.1 -+
T1.2.1 -> T1.2.2 -> T4.2.1 -> T4.2.2 -> T4.2.3 ----------------------+-> T4.3.2 -> T5.1.1 -> T5.1.2 -> T7.1.1 -> T7.2.1 -> T7.2.2
T2.2.1 -> T2.2.2 -> T4.1.1 -> T4.1.2 --------------------------------+
```
The MIP chain (T4.2.1 -> T4.2.2 -> T4.2.3) is the highest-risk path: if the T4.2.1 spike is inconclusive by the end of week 4, adopt the decomposition fallback immediately.

## Cut order if time runs short
1. **P2 stretch (never scheduled):** T5.1.3 ablation, T6.2.1 scenario explorer, T7.1.2 memo (-5.5 h).
2. **T3.2.2 Prophet** (P1, 2.5 h): downgrade to cut; ARIMA/ETS alone still meets the brief's "Prophet/ARIMA" spirit; state this in README.
3. **T5.2.1 reduced grid:** drop cost-weight ratio and min-remaining-shelf-life sweeps (keep shelf life, changeover, forecast error, utilisation, frontier) (-0.5 h).
4. **T6.1.2 plan viewer:** replace the interactive Gantt with two static PNGs in the README (-1.5 h).
5. **Never cut:** T4.1.x baseline, T4.3.3 checker, T5.1.2 CIs, T5.2.2 robustness statement, T7.1.1 limitations. They are what make the project credible.

## Weekly ritual (15 min)
Update status via `python tools/backlog.py set <id> <status>`; re-run `check`; if slipped > 2 h, apply next cut.
