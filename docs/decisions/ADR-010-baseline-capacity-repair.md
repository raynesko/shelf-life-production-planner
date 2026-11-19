# ADR-010: Baseline B1 sheds load by run-out priority, not pro rata

- **Status:** ACCEPTED (2026-11-18). All baseline-dependent results were re-run after this change; nothing reported
  before it is kept.
- **Context:** B1's capacity repair scaled every planned run pro rata when a week did not fit in 72 h, dropped runs
  that fell below the minimum run, and repeated. The T5.2.1 sensitivity grid exposed a failure mode: with changeover
  times x1.5 and x2, pro-rata cuts left every SKU short, so every SKU fell below its reorder point the next week,
  the full allergen ladder ran every week, and production collapsed (fill rate 69% and 8%). Instrumenting B1 showed
  the repair also fires in about 43% of weeks at default settings, so it shapes the main comparison as well. No
  competent planner cuts every product at once; they defer the products that have stock and keep the urgent ones.
  Leaving it in would make B1 a strawman exactly where the optimiser claims an advantage (ADR-006 guardrail).
- **Decision:** When the week is over capacity, B1 first tries the pro-rata scale-down; if that would push any run
  below its minimum, it instead defers (sets to zero this week) the SKU with the most usable cover
  (on-hand / forecast, weeks) and repeats. Implemented in `BaselineB1.fit_capacity`; tests
  `test_capacity_repair_defers_most_covered_sku_not_all` and `test_long_changeovers_do_not_starve_the_line`.
- **Effect (B1 alone, 10 Monte Carlo paths, before re-running anything else):** default settings nearly unchanged
  (fill 99.2%, waste 2.3%); changeover x1.5 fill 69% -> 92%; changeover x2 fill 8% -> 79%.
- **Consequences:** Re-run in this order: baseline replay, optimiser tuning (ADR-007; its start state comes from a B1
  warm-up), B1 cover tuning (ADR-009), test replay, main experiment, ablation, sensitivity. The optimiser's settings
  were re-selected by the unchanged rules, not carried over.
- **Alternatives rejected:** exclude the stress cells as "baseline invalid" (hides a real baseline defect that also
  acts at default settings); give B1 an exact knapsack (beyond spreadsheet practice and it would be an optimiser).
