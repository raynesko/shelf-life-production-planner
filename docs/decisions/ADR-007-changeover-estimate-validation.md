# ADR-007: Choose the decomposition's per-run changeover estimate on the validation year

- **Status:** ACCEPTED (2026-11-18). Chosen on the validation year; the test year was then re-run once.
- **Context:** The first 52-week test replay with the ADR-003 default (decomposition, per-run changeover = mean incoming
  changeover over all other SKUs) was worse than baseline B1: expired waste +55%, lost cases +36%, despite 43% fewer
  changeover hours. Per-SKU breakdown: the optimiser ran the 14-day SKUs (pasta, egg and tuna salad) about 30 times a
  year against B1's 40. Each extra run was charged about 3 h, so the model batched them, and with a minimum of 50%
  remaining shelf life at shipment those batches have about one week to sell. ADR-003 had already called this estimate
  pessimistic and listed calibrating it as follow-up work. Changing the planner after seeing test numbers would be tuning
  on the test year, so the choice was moved to the validation year.
- **Method:** `scripts/tune_planner_validation.py` replays the validation year (2015-04-06 .. 2016-03-28) from the same
  B1 warm-start state for each variant. Selection rule, written down before any run: lowest simulator-evaluated cost with
  the optimiser's own weights (`configs/costs.yaml`); ties within 0.5% go to fewer expired cases. B1's numbers do not
  enter the rule.
- **Variants and results** (`results/planner_tuning_validation.csv`; cost index B1 = 100):

  | Variant | Per-run changeover charged | Cost index | Expired cases | Lost cases | Changeover h |
  |---|---|---|---|---|---|
  | B1 (reference) | - | 100.0 | 7,258 | 2,075 | 1,260 |
  | mean (ADR-003 default) | mean incoming, 1.9-3.3 h | 100.2 | 12,338 | 3,304 | 689 |
  | iter1-3 | realised mean incoming from the previous replay | 99.2-99.4 | 9,311-10,107 | 2,076-3,408 | 690-709 |
  | arc (exact MIP) | exact sequence-dependent, 60 s/week | 98.1 | 4,739 | 2,942 | 937 |
  | **min (chosen)** | cheapest incoming, 1.0 h | **97.5** | **3,922** | **1,894** | 844 |

- **Decision:** `configs/planner.yaml`: decomposition (`approx`) with a per-run estimate of 1.0 h for every SKU (the
  cheapest possible incoming changeover). CP-SAT still sequences each week exactly, and the simulator and the independent
  checker charge the true changeover hours. If the cheaper estimate lets a week overfill, the plan is cut back to fit
  capacity (1 week in the test replay).
- **Why the optimistic estimate wins, even against the exact model:** the MIP plans against a single point forecast, so
  an exact (or pessimistic) changeover cost makes it batch production as if the forecast were certain. Under-charging
  changeovers pushes it toward smaller, more frequent runs, which hedge forecast error for short-life SKUs. The
  sequencer then recovers most of the changeover savings by grouping allergens. This is a robustness effect, not a
  better changeover model. The deeper fix is stochastic or chance-constrained planning (listed as future work).
- **Test year, run once afterwards** (`results/replay_comparison.csv`): expired waste -43%, changeover hours -35%,
  allergen-clean hours -48%, fill rate -0.06 points, lost cases +9%, evaluated cost -3.0% vs B1. The superseded first
  run (+55% waste) is described in this ADR so the change stays traceable.
- **Consequences:** the iterated-realised variants did not converge to a better point (the estimate oscillates as run
  patterns change), so they were dropped. Planning (validation) and evaluation (test) stay separate. The
  changeover-time sensitivity (x0.5-x2) scales the estimate together with the true matrix.
- **Interview angle:** the "obvious" exact model lost to a deliberately biased approximation, because the real enemy was
  forecast uncertainty, not changeover accounting. The decision was made on held-out validation data, after a
  disappointing first test result, without retuning on the test year.
