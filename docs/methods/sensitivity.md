# Sensitivity analysis and the waste-vs-service frontier (T5.2.1, T5.2.2)

All results: **simulation on a synthetic plant model**. Findings: [docs/results/sensitivity_findings.md](../results/sensitivity_findings.md).

## Design
- **One at a time.** Each cell changes one parameter; everything else stays at its default
  ([configs/sensitivity.yaml](../../configs/sensitivity.yaml), copied to `results/sensitivity/config_used.yaml`).
  Interactions are not explored: a full factorial of 8 parameters x 3-5 levels is out of the time budget.
- **Paired, common random numbers.** Every cell uses the same seed (20261118), so all planners in a cell, and all
  cells, see the same 50 underlying error draws. Arm differences are paired path by path; cell-to-cell differences
  are not confounded by different noise.
- **Three planners per cell.** Optimiser (OPT), validation-tuned B1 (`B1_TUNED`, headline baseline, ADR-009) and
  the rule-of-thumb B1 (ADR-006). Planner settings are held at their validation-chosen values in every cell (the
  optimiser's per-run changeover estimate scales with the changeover multiplier); nothing is re-tuned per cell,
  because a planner in a real plant would not know the true value of a mis-specified parameter either.
- **Reduced N.** N = 50 paths per cell instead of the main experiment's 200. From the pilot (experiments.md), the
  95% CI half-width scales like 1/sqrt(N), so cell CIs are about twice as wide as the headline's. Every cell's CI
  is reported in `results/sensitivity/summary.csv`.
- **Every executed plan is re-validated** by the independent checker in every cell.

## Grid
| Parameter | Values | Note |
|---|---|---|
| Shelf life (x) | 0.5, 0.75, 1, 1.25 | 0.5 puts 14-day SKUs at 7 days, outside the 14-56 d design range: a stress test |
| Changeover times (x) | 0.5, 1, 1.5, 2 | scales base, routine and allergen-clean hours together (A-09 to A-11) |
| Forecast error (x) | 0.5, 1, 1.5, 2 | scales both the simulated errors and the optimiser's sigma |
| Demand / utilisation (x) | 0.828 ... 1.124 | about 70 / 80 / 85 / 90 / 95% B1 line utilisation |
| Min remaining shelf life at ship | 30, 50, 70% | A-02 / O-04 |
| Cost weights | expiry 2/4/10, changeover 200/400/800 per h, lost sale 25/40/80 | weights steer the optimiser and score both |

**Weekly-bucket caveat.** Shelf life enters the model as a whole number of shippable weeks. Some settings map to
identical week counts for every SKU (e.g. MSL 70% and shelf life x0.5), so their cells are identical by
construction, not by coincidence. x1.25 changes few SKUs' week counts, so it is close to the default.

## Frontier
Each planner is swept along its own service lever: B1 cover 0.5-3 weeks; optimiser service target alpha 80-99%.
The chart plots fill rate against expired waste AND against changeover hours per week, because a planner can buy
waste and service with line time (more, smaller runs), and a two-axis frontier would hide that.

## Measures
Percentage reductions are ratios of means (stats.py). Because the tuned B1's waste is close to zero in some cells,
a % waste reduction can be huge or meaningless there, so the tornado uses bounded measures: planning cost reduction
(%), expired waste in percentage points of production, and fill-rate change in points.

## Runtime budget
About 45 s per optimiser path (13-week MIP + CP-SAT sequencing every week, 52 weeks), 14 worker processes. 30 cells
+ 11 frontier points at N = 50 took about 100 minutes on a 16-thread laptop. The B1 arms take under a second per
path. Re-run: `python scripts/run_sensitivity.py`, then `--append-arms B1_TUNED`, then
`python scripts/analyze_sensitivity.py`.
