# Baseline planner B1

Code: `src/shelflife/sim/baseline.py`. Tests: `tests/test_baseline.py`.

## Rules (numeric)
| Element | Rule | Default |
|---|---|---|
| Forecast | Moving average of the last 4 weeks of observed demand (no future data; enforced by test) | 4 weeks |
| Reorder point (s) | Produce only if usable on-hand < forecast x reorder_weeks (ADR-006) | 1 week |
| Production quantity (S) | Order up to forecast x (1 + cover) - usable on-hand | rule-of-thumb B1: cover = 1 week (2 weeks in total); headline B1_TUNED: cover chosen on the validation year (ADR-009, `configs/baseline.yaml`) |
| Run size | Raise to the minimum run, cap at the maximum run | 1.5 h / 24 h x line rate |
| Sequence | Static allergen ladder: fewest allergens first, most last (ties: allergen set, then SKU id); wet clean at end of the weekly cycle | fixed |
| Capacity | If run + changeover hours > available, scale runs pro rata; if that would push a run below its minimum, defer the SKU with the most cover to next week and repeat (ADR-010) | 72 h/week |
| Issue | FEFO with minimum remaining shelf life at shipment (simulator) | MSL 50% |

## Why this is not a strawman
B1 is what a competent planner builds in a spreadsheet: a reorder-point (s, S) policy that nets on-hand inventory (it is not "make the forecast"), runs each SKU on a natural two-week cycle instead of cleaning for all 12 every week (ADR-006: a weekly wheel would spend 29.5 of 72 h on changeovers), holds explicit cover, respects minimum and maximum runs and capacity, and sequences by the allergen-ladder practice (fewest allergens first). Note: a ladder only reduces cleans to one per cycle when allergen sets are nested; this SKU set's are not (e.g. sesame, fish, wheat, tree nuts each appear on one SKU), so the full ladder still needs 7 allergen cleans per cycle. That is a property of the product mix, and it applies equally to the optimiser. Its weaknesses are the real ones the optimiser targets: (1) cover is the same for a 14-day salad and a 56-day spread, so short-life SKUs over-produce while long-life SKUs carry no extra buffer; (2) the fixed ladder cannot skip or merge runs to avoid cleans; (3) the moving average lags seasonality. As a fairness guard, the frontier study (T5.2.1) sweeps cover (0.5 to 3 weeks) and the reorder point, so the comparison does not hinge on the default of 1 week.

## Deliberately not done
No shelf-life-aware sizing, no dynamic sequencing, no forecast-error-based safety stock, no multi-week look-ahead.

## Test-year replay (2016-04-04 .. 2017-03-27; `python scripts/run_baseline_replay.py`)
Results: `results/baseline_replay.csv` (KPIs), `results/baseline_plan_test.csv` (plan), `results/baseline_replay_weeks.parquet`.
B1 runs continuously from 2013 so the test year starts from a realistic state; demand = Favorita units x 0.198 (calibration).
Independent checker: 0 violations over 52 weeks. Expired waste is above zero and fill rate below 100% (plausibility check met).
Read the numbers from the CSV, not this page, so they never drift.
