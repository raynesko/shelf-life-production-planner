# 01 - Project Charter

**Project:** Shelf-Life-Aware Production Planner (EPIC-1)
**Builder:** solo, ISE grad student | **Cadence:** ~9-10 h/week x 8 weeks (~76 h scheduled + 5.5 h stretch)
**Target roles:** supply chain analyst, demand planner, operations analyst (NJ food and pharma-adjacent)

## 1. Problem statement
A food manufacturer making perishable products on a shared line must decide each week *how much* of each SKU to make, *in what order*, and *how much safety stock* to hold. Three forces conflict:

- **Shelf life:** over-production expires (waste, plus lost margin and disposal).
- **Allergen rules:** a changeover from a product carrying allergen X to one not declaring X needs a validated clean. These cleans are long and consume scarce line hours.
- **Demand uncertainty:** under-production causes stockouts (lost sales, penalty risk).

Rule-of-thumb planning (moving average, fixed cover, fixed product rotation) ignores the interaction. This project builds a forecast-plus-optimise planner and measures, against a fair baseline in simulation, how much expired waste, stockouts and changeover time it removes.

## 2. Target user and business context
- **User:** production planner / demand planner at a mid-size refrigerated prepared-foods manufacturer (hypothetical; no real company data).
- **Decision cadence:** weekly S&OP-style schedule release, 13-week look-ahead, rolling re-plan.
- **Reviewer (resume audience):** operations or supply chain hiring manager; non-technical, so a dashboard and a 2-page memo are part of the deliverable.

## 3. Objectives
1. Forecast weekly SKU demand with benchmark-beating models (ARIMA/ETS, Prophet) and quantify the error honestly.
2. Build a mixed-integer program that sizes and sequences runs under capacity, shelf-life and allergen constraints, with forecast-error-based safety stock.
3. Compare against baseline B1 (a realistic good-practice planner) using paired simulation with confidence intervals.
4. Show sensitivity: where the advantage holds, shrinks, or vanishes.
5. Package as a reproducible repo, Streamlit dashboard, memo and resume pack.

## 4. Scope
- 12 perishable SKUs, 4-5 product families, one bottleneck line, weekly buckets, 13-week horizon, 52-week test year.
- Real demand patterns from public retail data (Favorita); documented synthetic plant parameters.
- Allergen-driven sequence-dependent changeovers using the FDA Big 9 allergens.
- Forecasting, MIP (OR-Tools), simulation, statistics, sensitivity, dashboard.

## 5. Explicit non-goals
- No real plant data, no claim of real-world savings. All results are labelled *simulation on a synthetic plant model*.
- No multi-line / multi-plant / network design, no raw-material or BOM planning, no labour scheduling.
- No daily/shift-level scheduling; no OEE loss modelling (availability/performance/quality losses are not modelled; stated in limitations).
- No deep-learning forecasters, no real-time ERP integration, no formal GMP validation of cleaning (cleaning times are assumptions).
- No claim that retail sales equal manufacturer demand (it is a stated proxy).

## 6. Success metrics (all are TARGETS, not results)
| Metric | Target | Justification |
|---|---|---|
| Forecast WAPE, selected model vs seasonal naive (test year, aggregate) | >= 10% relative improvement | Modest bar; weekly retail demand usually has structure beyond naive. If missed, report honestly. |
| Expired waste vs B1 (Monte Carlo mean, relative) | >= 25% reduction, 95% CI excluding 0 | Hypothesis: B1 ignores shelf life and over-produces slow sellers. Unknown until run; sensitivity will show conditions. |
| Fill rate vs B1 | non-inferior (>= -0.5 pt) and ideally +1-2 pts; AND improvement shown at matched service level on the frontier | Prevents "waste cut by under-producing". |
| Changeover hours vs B1 | >= 20% reduction | Sequence optimisation within allergen rules; depends heavily on assumed cleaning times. |
| Allergen/capacity/shelf-life violations in any executed plan | 0 (hard requirement) | Verified by independent checker. |
| Reproducibility | clean clone reproduces headline numbers within tolerance | Credibility. |
| Solve performance | 13-week solve <= 60 s typical; 52-week replay < 90 min | Practical usability. |

## 7. Assumptions (full register in docs/assumptions.md)
- Favorita chain-wide weekly sales are a proxy for a manufacturer's DC demand for comparable perishable SKUs.
- Plant parameters (rates, run sizes, cleaning times, costs, minimum remaining shelf life at shipment) are assumptions with ranges; shelf lives anchored to USDA FoodKeeper where comparable products exist. FoodKeeper is *consumer storage guidance*, not manufacturer code-date validation (flagged).
- Shelf life 14-56 days, so weekly buckets are valid.
- Baseline utilisation calibrated to about 85% (target calibration assumption).

## 8. Key risks and mitigations
| Risk | L / I | Mitigation |
|---|---|---|
| Kaggle access/terms block data use | M / H | Spike T1.1.1 in week 1; fallback M5 FOODS or synthetic demand calibrated to published retail patterns (ADR-001). |
| Prophet install on Windows fails | M / L | Spike T1.2.2; fallback statsforecast only; Prophet marked P2-cut. |
| MIP too slow with sequencing | M / H | Spike T4.2.1 with decision criterion; decomposition fallback; solver time limit + baseline fallback week. |
| Baseline seen as a strawman | M / H | B1 uses static allergen ladder and cover logic; frontier comparison at matched fill rate. |
| Results driven by invented parameters | H / H | Sensitivity on every key assumption; say where advantage vanishes. |
| Result misses targets | M / M | Targets are labelled targets; report honestly (interviewers value that). |
| Scope creep / time | H / M | Weekly P2 cut list in 04_milestone_plan.md; 75.5 h scheduled vs ~80 h max capacity is tight. |
