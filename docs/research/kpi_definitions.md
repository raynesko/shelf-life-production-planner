# KPI Definitions (T1.1.2)

Notation: p = SKU, t = week in the evaluation window T (52 test weeks). Units are **cases**. Sums over p are over all 12 SKUs unless stated. These definitions are binding for the simulator (T4.1.1) and analysis (T5.1.2); change them only with an ADR.

| KPI | Formula | Unit | Denominator / note | Future function | Results column |
|---|---|---|---|---|---|
| Expired waste (cases) | E = sum_{p,t} units written off in week t because they can no longer ship with the minimum remaining shelf life (age a >= A_p and unshipped; ADR-004) | cases | Total over window | `sim.kpis.expired_cases` | `expired_cases` |
| Expired waste (% of produced) | 100 x E / sum_{p,t} produced | % | Produced in the same window; units still in inventory at the end are excluded from E (reported as `end_inventory_cases`) | `sim.kpis.expired_pct_produced` | `expired_pct` |
| Fill rate | sum shipped / sum demand | ratio 0-1 | Demand = realised demand (scenario or actual) | `sim.kpis.fill_rate` | `fill_rate` |
| Lost cases | sum max(demand - shipped, 0) | cases | Lost sales, not backordered. Includes demand not served because on-hand units fail the MSL rule | `sim.kpis.lost_cases` | `lost_cases` |
| Stockout SKU-weeks | count of (p,t) with shipped < demand | count | Of 12 x 52 = 624 SKU-weeks | `sim.kpis.stockout_sku_weeks` | `stockout_sku_weeks` |
| Changeover hours | sum_t sum over consecutive pairs (i -> j) in the executed run order of C[i,j], including carry-over from the previous week's last SKU | hours | Allergen-clean hours reported separately | `sim.kpis.changeover_hours` | `changeover_hours`, `allergen_clean_hours` |
| Line utilisation | (run hours + changeover hours) / available hours, mean over weeks | ratio | Available hours from plant.yaml; not OEE-adjusted | `sim.kpis.utilisation` | `utilisation` |
| Weeks of cover | mean over p,t of end-of-week usable inventory_p,t / mean weekly demand_p | weeks | Mean demand of that SKU over the window | `sim.kpis.weeks_of_cover` | `weeks_of_cover` |
| Age at shipment | shipped-weighted mean age (weeks) | weeks | Shipments only | `sim.kpis.mean_age_at_ship` | `mean_age_ship` |
| Plan violations | count of capacity / run-size / MSL / allergen-clean accounting violations found by the independent checker | count | Must be 0 | `checks.plan_checker.check` | `violations` |
| WAPE | sum |y - yhat| / sum y | % | Aggregated over SKUs, origins and horizon h (reported per h and for h = 1..13) | `forecast.metrics.wape` | `wape` |
| Bias | sum(yhat - y) / sum y | % | Positive = over-forecast | `forecast.metrics.bias` | `bias` |
| MASE | mean |y - yhat| / mean |y_t - y_{t-52}| in the training window | ratio | Seasonal-naive scaling (m = 52) when >= 2 years of history, else m = 1 | `forecast.metrics.mase` | `mase` |

## Derived comparison metrics (T5.1.2)
- Relative reduction (%) = 100 x (1 - mean(KPI_opt) / mean(KPI_base)) across paired scenarios; 95% percentile bootstrap CI.
- Fill-rate delta (percentage points) = 100 x (fill_opt - fill_base).
- Forecast WAPE improvement (%) = 100 x (1 - WAPE_selected / WAPE_seasonal_naive).

## Conventions
- Weeks start Monday (ISO). Shelf life is stored in days. A cohort of age a weeks may ship iff a <= A_p = floor((1 - MSL) x shelf_life_days / 7); unshipped cohorts at age A_p are written off (ADR-004). Production is usable in the week it is made.
- Demand is rounded to whole cases inside the simulator; production quantities are used as given.
- All KPIs are reported with the label "simulation on a synthetic plant model".
