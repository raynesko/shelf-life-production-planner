# Experiments: replay, Monte Carlo, ablation, sensitivity

All results are a **simulation on a synthetic plant model** driven by real Favorita demand. No real-plant savings are claimed.

Code: `src/shelflife/analysis/experiment.py` (engine), `scripts/run_experiment.py` (CLI), `scripts/analyze_experiment.py`
(statistics -> `results/headline_numbers.json`), `scripts/run_sensitivity.py`. Tests: `tests/test_experiment.py`, `tests/test_stats.py`.

## Layers
| Layer | Demand | Runs | Use |
|---|---|---|---|
| A. Historical replay | real test-year demand (2016-04-04 .. 2017-03-27) x calibration scale | 1 per arm | the "what would have happened" story; point values only |
| B. Monte Carlo | N paths: actual test-year demand + 4-week block bootstrap of standardised validation residuals (`forecast/scenarios.py`, centred on actual demand per ADR-008) | N per arm | inference: paired differences with bootstrap CIs |
| C. Sensitivity | as B with one parameter changed, reduced N = 50 | 50 per arm per cell | robustness and break-even (`docs/methods/sensitivity.md`) |

Every arm starts the evaluated year from the same state: B1 run on actual demand from 2013 to the week before the test year.

**Common random numbers:** all paths come from one seed and every arm replays the identical path array, so each path gives
one paired difference. Tested in `tests/test_experiment.py` (same path ids and seeds for both arms; same demand per path).

**Reproducibility:** CP-SAT sequencing runs single-threaded with a fixed seed and SCIP is deterministic, so a re-run with the
same config gives identical KPIs; `meta.json` stores the SHA-256 of the KPI table (`kpi_sha256`), the git hash (when the
repo has commits), a hash of all source and config files, and the wall time. Tested by re-running a small config.

## Arms
| Arm | Forecast | Planning logic |
|---|---|---|
| B1_TUNED (headline baseline) | 4-week moving average | B1 with cover chosen on the validation year by the ADR-007 rule (`configs/baseline.yaml`, ADR-009) |
| B1 (rule-of-thumb) | 4-week moving average | reorder-point (s, S), allergen ladder, 1 week cover (`docs/methods/baseline.md`, ADR-006) |
| OPT | selected model per SKU (`configs/forecast_selection.yaml`) | rolling 13-week MIP + safety stock, settings from `configs/planner.yaml` (ADR-007) |
| B1_SELFC (ablation) | selected model, one-step | B1 (rule-of-thumb) |
| OPT_MA4 (ablation) | flat 4-week moving average | OPT |

## Statistics (`analysis/stats.py`)
Primary: mean paired effect with a 95% percentile bootstrap CI (10,000 resamples of paths; the same resampled paths for both
arms). Relative reductions are ratios of means, 100 x (1 - mean OPT / mean B1); fill rate is a difference in percentage
points. Secondary: Wilcoxon signed-rank p-value and the paired effect size d_z. N is a computing choice, so p-values are
reported but not used as evidence on their own. The bootstrap covers a known true effect in >= 90% of 100 synthetic trials
(`tests/test_stats.py`).

Forecast-accuracy CI: the test-year WAPE ratio (selected vs benchmark), resampling the 52 forecast origins.

## Choosing N (pilot)
A pilot with N = 30 (`configs/experiment_pilot.yaml`) measures the CI half-width of the expired-waste reduction; the CI
shrinks like 1 / sqrt(N), so N = 30 x (half-width / 3)^2 gives the target half-width of <= 3 points. Pilot result and the
chosen N: see "Pilot" below.

## Limitations of the experimental design
1. **Forecasts are not refit to simulated paths (Layer B).** The optimiser plans with the real test-year forecasts,
   while B1's moving average reacts to each path. Paths are centred on ACTUAL demand (ADR-008), so the optimiser keeps
   its real forecast errors plus the path noise it cannot see. Direction: slightly favours B1. (The first design centred
   paths on the forecast itself and favoured the optimiser; superseded, see ADR-008.)
2. **Error model from the validation year.** Its intervals under-cover on the real test year (forecasting.md), so the
   added path noise may be smaller than real week-to-week surprises. Direction: unclear for the difference; both arms
   face the same paths. The error-scale sweep (x0.5 .. x2) brackets it.
3. **Validation-year planner tuning is in-sample for forecasts and sigma** (ADR-007), so validation KPIs are optimistic in
   level; only the ranking of planner variants was used.
4. Cost weights are assumptions (`configs/costs.yaml`); total planning cost is reported only as a relative change, never as
   money, and the weights are swept.

## Pilot
Run `pilot_191ca3a449` (N = 30, seed 20261118, arms B1 and OPT, 135 s wall on 13 workers, 0 checker violations,
0 fallback weeks). The 95% CI half-width of the expired-waste reduction was 1.8 points, so N = 12 would already meet
the 3-point target. Lost cases were the noisiest KPI (half-width 9.4 points at N = 30). **Chosen N = 200** (the
charter target). It costs about 15 minutes and shrinks the lost-cases CI to about +/-3.6 points. The pilot's point
estimates are not reported; the main run supersedes them. (The pilot used the forecast-centred design that ADR-008
replaced. N depends on the noise level, which the change does not alter much; the main run's CI half-widths are
checked against the 3-point target again in `results/experiment_summary.csv`.)

## Numerical reproducibility
The rolling-horizon optimiser carries every small numerical difference forward through 52 weeks, so a change as small
as discarding a 0.0001-case solver artefact changes many individual paths. Aggregates are stable (largest headline
change 0.6 points, inside the CIs; [sensitivity_findings.md](../results/sensitivity_findings.md#numerical-robustness)).
Rule: every reported number comes from one code version; after any change to planning code, the whole pipeline is
re-run (`scripts/run_all.py`) and older outputs move to `results/superseded/`.
