# ADR-003: MIP formulation and solver

- **Status:** ACCEPTED (T4.2.1 spike, inside its 2.5 h time box)
- **Evidence:** `python scripts/spike_formulation.py` -> `results/logs/spike_formulation.csv`; summary in `notebooks/02_formulation_spike.ipynb`. Synthetic demand (seed 11) at ~78% run-hour load; 120 s limit, 2% relative gap target.

## Options compared
- **A, single MIP (`sequencing="arc"`):** lot sizing plus exact sequence-dependent allergen changeovers inside each week (one run per SKU per week, MTZ subtour elimination, carry-over of the line state between weeks). 12 x 13 instance: 4,810 variables.
- **B, decomposition (`sequencing="approx"` + `opt/sequencing.py`):** lot-sizing MIP that charges each run a changeover estimate (mean incoming changeover for that SKU), then sequences each week by CP-SAT (shortest Hamiltonian path from last week's final SKU), with pro-rata repair if the true changeover overflows capacity. 741 variables.

## Results (cost = common simulator-based evaluator; lower is better)
| Instance | Approach | Solver | Status | Solve s | Gap | Cost | Changeover h | Lost cases |
|---|---|---|---|---|---|---|---|---|
| 4 x 8 toy | A | SCIP | optimal (<=2%) | 0.6 | 1.9% | 2,426,048 | 43.0 | 2,096 |
| 4 x 8 toy | A | HiGHS | optimal | 0.7 | 0.0% | 2,379,991 | 42.0 | 213 |
| 4 x 8 toy | A | CBC | optimal (<=2%) | 1.4 | 0.2% | 2,383,161 | 50.5 | 213 |
| 4 x 8 toy | B | SCIP | optimal | 0.2 | 0.0% | 2,381,266 | 38.0 | 213 |
| 12 x 13 | A | SCIP | time limit, feasible | 120 | 2.8% | **4,050,329** | 214.0 | 5,018 |
| 12 x 13 | A | CBC | time limit, feasible | 120 | 3.7% | 4,086,480 | 205.0 | 6,848 |
| 12 x 13 | A | HiGHS | no solution in 120 s | 120 | - | - | - | - |
| 12 x 13 | B | SCIP | optimal | **3.4** | 1.2% | 4,110,802 (+1.5% vs A) | 155.5 | 8,485 |
| 12 x 13 | B | HiGHS | no solution in 120 s | 120 | - | - | - | - |

Verification found along the way: for every solved A run, the MIP objective equals the simulator-evaluated cost exactly (0.000% difference), so the optimiser's cohort, expiry and changeover accounting agrees with the independent simulator. Locked in by `tests/test_opt_consistency.py`.

## Decision
1. **Default planner = B (decomposition) with SCIP + CP-SAT.** It is about 35x faster (3.4 s vs a 120 s timeout) and within 1.5% of A's best incumbent on the full instance. A 52-week rolling replay takes ~3 min with B, versus ~1.7 h with A.
2. **Keep A as an "exact" mode** for one validation run on the historical replay, to report the decomposition's suboptimality honestly (an interview talking point).
3. **Solver:** SCIP via OR-Tools pywraplp. HiGHS (1.12 via pywraplp) returned no solution within 120 s on both 12 x 13 models, so it is dropped for the MIP. CBC is a working fallback.
4. ADR criterion "12 x 13 reaches <= 2% gap or a 120 s limit with a feasible incumbent": B meets it (1.2% in 3.4 s); A meets the weaker form only (feasible at 120 s, 2.8% gap).

## Known limitations
- B's per-run changeover estimate is pessimistic (mean incoming time), so B under-produces slightly: in the instance above it had fewer changeover hours (155 vs 214) but more lost cases (8.5k vs 5.0k). **T4.2.3 follow-up:** calibrate the estimate (e.g. allergen-class-aware or iterated from realised sequences) and re-measure the gap against A.
- One run per SKU per week; SKUs cannot be split around an allergen clean.
- No terminal-inventory valuation: end-of-horizon stock is worth nothing, which is acceptable because only week 1 of each 13-week plan is executed.
- **Runtime risk for the Monte Carlo layer (T5.1.1):** N = 200 paths x 52 weekly solves x ~3.4 s is about 10 h single-threaded, or roughly 40-60 min across the machine's 16 cores. Plan: run paths in parallel processes, pilot N first, and lower the per-solve limit if needed (record any change in a new ADR).
