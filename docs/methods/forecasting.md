# Demand forecasting

Code: `src/shelflife/forecast/` (`backtest.py` harness and benchmarks, `arima_ets.py`, `prophet_model.py`,
`selection.py`, `scenarios.py`). Tests: `tests/test_backtest.py`, `tests/test_stat_models.py`.
Numbers on this page are copied from the files named next to them; if they disagree, the files win.

## Set-up
- Panel: 12 Favorita SKUs x 221 weeks (2013-01-07 .. 2017-03-27, ADR-005), weekly units, demand unconstrained (A-22).
- Rolling origin, refit at every origin on history strictly before it, horizons 1-13 weeks.
  Validation year = 52 origins before the test year (model selection, error sigma); test year = last 52 weeks (reporting only).
  Rows whose target falls past the window end are dropped, so validation never touches test actuals.
- Metrics (definitions: `docs/research/kpi_definitions.md`): WAPE, bias, MASE, pooled over SKUs, origins and horizons.

## Models
| Name | What | Notes |
|---|---|---|
| naive, ma4, seasonal_naive | benchmarks | ma4 = 4-week moving average, also baseline B1's forecast |
| arima | statsforecast AutoARIMA, non-seasonal | |
| arima52 | AutoARIMA, season length 52 | slow: 2.5 h wall on 14 workers |
| ets | AutoETS, season length 52 (automatic selection decides on the seasonal term) | |
| prophet | Prophet, yearly seasonality only | rejected, see holiday decision |
| prophet_hol | prophet + Ecuador national holidays (Favorita `holidays_events.csv`, non-transferred, no "Work Day"), mapped to the Monday of their week | kept |

Failed fits fall back to MA(4) and are counted: 0 failures for every model (`results/logs/forecast_runtime.txt`).
All forecasts are clipped at 0 and `scripts/run_stat_models.py` asserts finite, non-negative output.
Runtimes (wall, 14 workers): arima 91 s, ets 33 s, prophet 50 s, prophet_hol 55 s, arima52 9,130 s.

## Prophet holiday decision (T3.2.2): holidays KEPT
Validation-year WAPE (pooled, all 12 SKUs): prophet 12.13%, prophet_hol 11.55%. Holidays improve validation WAPE,
so `prophet_hol` is kept and plain `prophet` is excluded from model selection (`EXCLUDED` in `scripts/select_forecasts.py`).
Per SKU, holidays help on 9 of 12 SKUs and hurt on SKU-03, SKU-10 and SKU-12.
Both Prophet variants are worse than MA(4) on validation (9.83%).

Fit cache: `results/forecast/cache/`, keyed by variant + horizon + exact history. Second run with unchanged inputs:
5.0 s vs 50.3 s wall (9.9%; most of what is left is process start-up) and 9 s vs 434 s CPU (2%).

## Residual diagnostics (T3.2.1)
One-step-ahead residuals on the validation year (`scripts/plot_residual_acf.py`):
`results/figures/residual_acf.png` (SKU-11, the hardest SKU, and SKU-04, a typical one) and
`results/forecast/residual_ljungbox.csv`. Ljung-Box at lag 8 does not reject white noise for any SKU under either
model (all p > 0.05; lowest p = 0.055, ARIMA, SKU-05). ETS on SKU-04 shows isolated spikes at lags 4 and 9 just
outside the approximate 95% band; with 52 points and 16 lags, one or two such spikes are expected by chance.

## Accuracy (validation used for choice, test reported) - `results/forecast/model_metrics.csv`
| Model | Validation WAPE | Test WAPE |
|---|---|---|
| ma4 | 9.83 | 11.48 |
| ets | 9.84 | 11.11 |
| arima | 10.16 | 11.79 |
| arima52 | 10.50 | 11.70 |
| naive | 10.98 | 12.25 |
| prophet_hol | 11.55 | 11.95 |
| prophet (rejected) | 12.13 | 12.16 |
| seasonal_naive | 15.35 | 17.60 |

## Model selection (T3.2.3)
Rule fixed before any test numbers for arima52/prophet existed (`selection.py` docstring): per SKU, the model with
the lowest validation WAPE (ties -> simpler model). Choices: `configs/forecast_selection.yaml`.
The single best model on validation is MA(4).

Test-year result (`results/forecast/headline_forecast.csv`):
- Selected per-SKU forecast: test WAPE 11.50%.
- vs seasonal naive (17.60%): 34.7% lower WAPE. This clears the charter's 10% target, but seasonal naive is the
  weakest benchmark on this data (open question O-09), so this comparison flatters the models.
- **vs MA(4) (11.48%), the strongest benchmark and B1's own forecast: no improvement (-0.2%).**
- ETS alone would have scored 11.11% on test (3.2% better than MA(4)), but ETS was not the validation winner,
  so choosing it now would be selecting on the test year. It is reported, not used.

Plain reading: on 12 aggregated, fairly stable weekly series, the statistical models do not beat a 4-week moving
average in a way that survives honest out-of-sample selection. Per-SKU selection on one validation year adds noise
(validation differences between the top models are fractions of a point). Any planning gain from the optimiser
should therefore be attributed to the planning logic (shelf-life-aware sizing, sequencing, safety stock), not to a
better point forecast; the ablation (T5.1.3) tests this directly.

Planner input: `results/forecast/forecasts_test.parquet` (selected model, 12 SKUs x 52 test origins x horizons
1-13, truncated at the panel end).

## Uncertainty (T3.3.1)
- `results/forecast/error_sigma.csv`: per SKU x horizon (12 x 13) standard deviation of forecast errors of the
  selected model, from VALIDATION-year rows only (test: `test_sigma_validation_only_and_scenarios_reproducible`).
- Scenario generator `ScenarioGenerator.generate(n_paths, seed)` in `scenarios.py`: actual test-year demand (ADR-008; originally the one-step forecast) plus a
  4-week block bootstrap of standardised validation residuals; returns non-negative demand of shape
  (n_paths, 12, 52), identical for the same seed. Sanity plot: `results/figures/scenario_paths.png` (SKU-05).
- **Interval calibration on the test year misses the +/-5-point target** (`results/forecast/interval_coverage.csv`):

  | Nominal | Empirical (all h) | h = 1 | h = 4 | h = 13 |
  |---|---|---|---|---|
  | 80% | 71.9% | 79.6% | 72.3% | 65.8% |
  | 95% | 86.6% | 90.7% | 87.1% | 83.5% |

  One-step intervals are close to nominal; longer horizons are too narrow by 8-15 points. Likely causes: the test
  year is noisier than the validation year (pooled WAPE 11.5% vs 9.8% for the same rule), and 52 validation
  origins give a thin, partly overlapping sample of long-horizon errors. The sigmas were NOT re-tuned on the test
  year (that would leak). Consequence: safety stock built from these sigmas (T4.3.1) will protect less than its
  nominal service level; the realised fill rate in simulation is what gets reported, and the sensitivity sweep
  (T5.2.1) varies the safety factor, so the frontier shows what a wider buffer costs in waste.
