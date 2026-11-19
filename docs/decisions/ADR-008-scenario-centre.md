# ADR-008: Centre Monte Carlo demand paths on actual demand, not on the planner's forecast

- **Status:** ACCEPTED (2026-11-18). Replaces the T3.3.1 design before any Monte Carlo number was published.
- **Context:** T3.3.1 built each path as `one-step forecast + sigma x bootstrapped standardised residual`. The
  optimiser plans with that same forecast, so inside the simulation its forecast is the true mean of every path. Its
  only "error" is the bootstrapped noise, drawn from the validation year, which under-covers the test year
  (forecasting.md). B1 reacts to each path through its moving average. Result: the first main run (N = 200, kept as
  `results/experiments/superseded_main_forecast_centred_8fe25e1648/`) showed a 66% waste reduction. On the real test
  year, the historical replay with identical planners showed 43%. The gap is the information advantage, not
  planning skill. My earlier limitation note had said this design favoured B1; it favours the optimiser.
- **Decision:** paths are `actual test-year demand + sigma x bootstrapped standardised validation residual`, clipped
  at 0 (`ScenarioGenerator.from_frames(..., center="actual")`, now the default). Every path keeps the real forecast
  errors the optimiser faced (bias, missed swings) and adds variation around them for inference. B1 keeps reacting to
  each path. The forecast-centred design stays available (`center="forecast"`) and is tested, but it is not used for
  results.
- **Consequences:** the variance of a path around its centre is unchanged (sigma from the validation year); the
  variance around the forecast grows (actual error + noise), which is the realistic direction. Monte Carlo estimates
  should now bracket the historical replay instead of overstating it. Selection rules, planner settings and cost
  weights are unchanged; only the experiment design moved, and in the conservative direction. Main, ablation and
  sensitivity runs were all re-run with this design.
- **Interview angle:** "my simulation was grading the optimiser against its own forecast": found by comparing
  Monte Carlo to the historical replay, fixed in the conservative direction, and the superseded run is kept.
