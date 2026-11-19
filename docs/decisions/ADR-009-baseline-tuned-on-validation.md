# ADR-009: Tune baseline B1's cover on the validation year; report against the tuned baseline

- **Status:** ACCEPTED (2026-11-18)
- **Context:** ADR-007 chose the optimiser's changeover estimate on the validation year. B1 kept the cover fixed by
  ADR-006 (order up to 2 weeks), which was argued from a rule of thumb, not tuned. The T5.2.1 frontier (test year,
  N = 50) then showed that B1 with a 0.5-week cover sits at lower waste and higher fill rate than every optimiser
  setting, at the price of far more changeover hours. So the main comparison gave one planner a tuning step and the
  other none. That asymmetry flatters the optimiser, and a reviewer would be right to reject it.
  How this was found matters: the trigger was a test-year sensitivity result. The fix therefore must not use the test
  year to pick B1's setting, only the same validation-year procedure the optimiser got.
- **Decision:**
  1. `scripts/tune_baseline_validation.py` replays B1 on the validation year for cover in
     {0.5, 0.75, 1, 1.5, 2, 2.5, 3} weeks (reorder point unchanged at 1 week) and applies the ADR-007 rule unchanged:
     lowest simulator-evaluated cost with `configs/costs.yaml` weights, ties within 0.5% to fewer expired cases.
     Result: cover 0.5 week (cost index 99.6 vs 100 for the default; optimiser 97.5 on the same year), written to
     `configs/baseline.yaml` ([results/baseline_tuning_validation.csv](../../results/baseline_tuning_validation.csv)).
  2. New experiment arm `B1_TUNED` (B1 with that cover). The **headline comparison is the optimiser vs B1_TUNED**.
     The ADR-006 default (`B1`, a two-week cycle) stays as a secondary row, labelled "rule-of-thumb B1".
  3. Sensitivity cells gain a B1_TUNED arm on the same paths (`run_sensitivity.py --append-arms B1_TUNED`); the
     tuned cover is held at 0.5 in every cell, as the optimiser's settings are.
  4. The ablation (T5.1.3) is left against the default B1: it asks where the optimiser's gain over a fixed rule comes
     from, and its arms share B1's sizing logic.
- **Consequences:** The headline changes character. The tuned B1 runs almost every SKU every week (about 29 h of
  changeovers a week, line utilisation about 91%), which keeps stock young and waste very low. Against it, the
  optimiser's gain is mainly line time and total cost, not waste. Numbers: [docs/results/summary.md](../results/summary.md).
  The charter target "waste >= 25% lower" was set against the default baseline and is reported against both.
- **Alternatives rejected:** keep the default B1 as the only baseline (asymmetric tuning; inflates waste gains);
  tune B1 on the test year (leakage); re-tune the optimiser on the test year to "win back" waste (leakage, and
  tune-to-hit).
