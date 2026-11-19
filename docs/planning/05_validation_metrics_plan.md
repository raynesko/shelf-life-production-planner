# 05 - Validation & Metrics Plan

All thresholds are targets. All results are **simulation on a synthetic plant model driven by real retail demand patterns**.

## 1. Baseline definition (B1)
A realistic good-practice spreadsheet planner, not a strawman (details in `docs/methods/baseline.md`, ticket T4.1.2):
- Forecast: 4-week moving average.
- Production: forecast demand + fixed 1-week cover top-up; scaled pro-rata if capacity is exceeded.
- Sequence: fixed static "allergen ladder" (fewest allergens first, most last, wet clean at end of cycle).
- Issue: FEFO. No shelf-life awareness in sizing, no dynamic sequencing.

Fairness guard: the **frontier** (T5.2.1) sweeps B1's weeks of cover (0.5-3) and the optimiser's service level alpha (80-99%). Improvement claims are made at **matched fill rate**, not only at default settings.

## 2. Evaluation design
| Layer | What | Purpose |
|---|---|---|
| A. Historical replay | Test year (52 weeks), real demand, real out-of-sample forecasts, weekly re-plan | Realism: single path, no assumptions about error distribution |
| B. Monte Carlo | N demand paths (pilot-chosen, target 200) from block-bootstrapped standardised forecast errors; paired, common random numbers | Statistical inference: distribution of KPI differences |
| C. Sensitivity | One-at-a-time sweeps, reduced N (~50) per cell | Robustness and break-even |

Data windows (T3.1.1): train >= 104 weeks -> **validation year** (model selection, sigma calibration) -> **test year** (reporting only). A test asserts selection and sigma never read the test window.

## 3. Metrics (formal definitions in `docs/research/kpi_definitions.md`)
- **Expired waste:** cases expired; % of cases produced.
- **Service:** fill rate = shipped / demand; lost cases; stockout SKU-weeks.
- **Changeover hours:** from the executed sequence, including week carry-over; allergen-clean hours reported separately.
- **Utilisation:** (run hours + changeover hours) / available hours.
- **Inventory:** average weeks of cover; average age at shipment.
- **Forecast:** WAPE, bias, MASE vs seasonal naive.
- **Feasibility:** violations count by independent checker (must be 0).

## 4. Comparison method
- Paired difference per scenario: d_s = KPI_base,s - KPI_opt,s.
- Point estimate: mean d_s. **Relative reduction** = 1 - mean(KPI_opt) / mean(KPI_base).
- **95% percentile bootstrap CI**, 10,000 resamples of scenarios (resampling the pair), for both mean difference and relative reduction.
- Secondary: Wilcoxon signed-rank. Because N is a compute choice, p-values will be tiny; **effect sizes and CIs are primary**.
- Pilot (N=30) to choose N so the CI half-width of % waste reduction <= 3 points (target).
- Tool validation: bootstrap code recovers a known injected effect with CI coverage >= 90% over 100 trials (T5.1.2).

## 5. Sensitivity analysis (T5.2.1 / T5.2.2)
| Parameter | Grid |
|---|---|
| Shelf life | -50 / -25 / 0 / +25% |
| Changeover times | x0.5 / x1 / x1.5 / x2 |
| Forecast error scale | x0.5 / x1 / x1.5 / x2 |
| Baseline utilisation | 70 / 80 / 85 / 90 / 95% |
| Min remaining shelf life at ship | 30 / 50 / 70% |
| Cost weights (expiry : lost sale : changeover) | 3 ratios |
Outputs: tornado chart; frontier chart; break-even statements ("advantage falls below X when ..."); explicit "where it does not help".

## 6. Verification (is the model right?) vs validation (is it realistic?)
- **Verification:** simulator conservation invariant; hand-calculated example; toy MIP vs brute force; zero-changeover regression; independent checker with mutation tests; deterministic re-runs.
- **Validation (limited by no real data):** face validity of baseline KPIs (waste > 0, fill rate < 100%); calibration of forecast intervals (80/95% coverage within +/-5 pts); sanity of parameters against FoodKeeper ranges; written list "what I would validate on real plant data" (memo). State plainly that external validity is not established.

## 7. Numbers permitted on the resume
Only values in `results/headline_numbers.json` (written by T5.1.2/T5.2.2), each with CI where applicable:
1. `forecast_wape_improvement_pct` (selected model vs seasonal naive, test year).
2. `expired_waste_reduction_pct` with 95% CI.
3. `changeover_hours_reduction_pct` with 95% CI.
4. `fill_rate_delta_pts` with CI (and note matched-service frontier result).
5. `sensitivity_min_waste_reduction_pct` / `share_of_cells_improved`.
6. Scale facts: 12 SKUs, 13-week horizon, 52-week test, N scenarios.
Never on the resume: any number not in that file, any unqualified claim of "savings", any dollar figure (cost parameters are assumptions).
