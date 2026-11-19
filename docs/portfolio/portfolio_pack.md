# Portfolio pack

Rules: every number below appears in `results/headline_numbers.json`, rounded. The block at the end is rendered from
that file by `scripts/render_results.py`, and a test fails if it goes stale. That block is the check list: each resume
number must match a line in it. Every claim says *simulation on a synthetic plant model*. No dollar figures. Targets
are not results; missed targets are reported as missed.

## 3 resume bullets (action + method + quantified result)
1. **Built** a shelf-life-aware weekly production planner for 12 perishable SKUs: statistical forecasts selected on a
   validation year (test-year WAPE 34.7% better than seasonal naive and level with a 4-week moving average) feeding a
   rolling 13-week mixed-integer program in OR-Tools, with allergen-changeover sequencing (CP-SAT), shelf-life and
   capacity constraints. An independent plan checker found 0 violations.
2. **Quantified** the planning trade-off in a 200-path paired Monte Carlo on a synthetic plant model. Against a
   baseline tuned on the same validation data, the optimiser cut changeover hours by 46.0% (95% CI 45.8-46.1) and
   allergen-clean hours by 54.8%, at the cost of expired waste rising from 0.50% to 1.11% of production and a
   0.56-pt lower fill rate. Against a rule-of-thumb baseline it cut waste by 54.2% and changeovers by 30.2%.
3. **Stress-tested** the result across 29 one-at-a-time sensitivity cells and a waste-vs-service frontier. Planning
   cost was lower in every cell, but waste was lower in only 17% (short shelf life). The frontier exposed an untuned
   baseline in my own first analysis and reversed the headline. Delivered a Streamlit scenario explorer, a 2-page
   memo and a 5-slide summary.

## 60-second interview pitch
"Perishable plants face a three-way squeeze. Make too much and product expires; make too little and you stock out;
and every allergen changeover burns line hours on cleaning. I built a planner for a hypothetical refrigerated foods
plant, driven by real grocery demand from the Favorita dataset. Forecasts were chosen on a validation year and tested
on a held-out year. A rolling mixed-integer program then decides quantities, run order and safety stock under line
capacity, shelf life and allergen rules. I compared it with a baseline planner in a paired simulation with confidence
intervals. The interesting part is what happened next. My first result said the optimiser halved waste. Then the
sensitivity frontier showed I had tuned the optimiser on validation data but not the baseline. Once I tuned both the
same way, the honest answer was a trade-off. The optimiser frees about 46% of changeover time, roughly 13 hours of a
72-hour week. A well-tuned simple rule keeps waste and stockouts lower by making every product every week. The
optimiser only wins on waste when shelf life is short, and on service when changeovers are long. The plant
parameters are assumptions, so I'd present this as a validated method and a decision rule, not a savings claim."

## 5-slide summary (realised in `docs/portfolio/summary_slides.pdf`, built by `scripts/build_documents.py`)
1. **The question and the answer.** Frontier chart: three planners, waste and line time vs service.
2. **Results vs both baselines.** KPI table with CIs and the KPI comparison chart.
3. **Where it helps and where it does not.** Short shelf life and long changeovers vs the default plant.
4. **Robustness.** Tornado chart, 29 cells, 0 checker violations.
5. **Limits and validation.** Synthetic plant, untested assumptions, shadow-mode pilot.

## Interview questions with talking points
**1. "How do I know your baseline isn't a strawman?"**
It isn't one, and the project shows why that matters. B1 is a reorder-point (s, S) planner with a moving-average
forecast, an allergen-ordered run ladder and a capacity repair that defers the best-covered SKU (ADR-006, ADR-010).
Its one free setting, cover, was tuned on the validation year by the same rule as the optimiser's (ADR-009). The
untuned version is kept as a second reference. Against it the optimiser looks far better (54% less waste), and that
gap is exactly the strawman effect.

**2. "So the optimiser loses on waste. Why build it?"**
Because line time is the scarce resource in many plants. The tuned rule only wins by running every SKU every week,
which uses 29.1 changeover hours a week and 91% of the line. The optimiser uses 15.7 h and 73%. If the plant can sell
extra volume or loses hours to breakdowns, those hours are worth more than 0.6 pts of waste. The sensitivity grid
shows the rule breaking when changeovers get 1.5x longer (fill rate falls to 90% while the optimiser holds 99%). It
also shows the optimiser winning on waste when shelf life is short. I'd recommend it on those conditions, not across
the board.

**3. "Your plant is synthetic. Why believe any of it?"**
Demand is real retail data; every plant parameter has a source or range in an assumptions register. I swept the ones
that matter (cleaning time, shelf life, minimum remaining shelf life, forecast error, utilisation, cost weights), and
the findings doc says where the result flips. The claim is about the method and the decision rule, not about savings.

**4. "Walk me through the allergen changeover logic."**
Moving from product i to j requires an allergen clean if i carries an allergen not declared on j. Residue would be an
undeclared allergen on j's label (FDA Big 9, including sesame since 2023). Going to the same or a subset profile needs
only a light changeover. So changeover time is asymmetric and sequence-dependent, and sequencing matters. Cleaning
times are assumptions; clean validation (swabs, ATP, test kits) is out of scope. I did not model GMP deviation or CAPA
workflows; the checker enforces planning rules only.

**5. "Which targets did you miss?"**
Several, and they are reported as missed (`docs/results/summary.md`). Against the tuned baseline, the optimiser missed
the waste-reduction and fill-rate non-inferiority targets. The forecast beat seasonal naive by 34.7% but showed no gain
over a 4-week moving average. The forecast intervals under-cover on the test year (80% intervals hold 71.9% of outcomes, 95% intervals 86.7%). Changeover reduction, 0
checker violations and replay runtime were met.

**6. "What would it take to use this in a real plant?"**
Real changeover and run-rate data from MES or CMMS logs, OEE losses, daily or shift scheduling, multi-line and
raw-material constraints, retailer shelf-life agreements and a planner-override workflow. Rollout would be shadow mode
on a few SKUs for 8 weeks, comparing against the actual plan. Tune the incumbent rule first; it may be enough.

## Source numbers (rendered; do not edit by hand)
<!-- PORTFOLIO:START -->
- baseline for these numbers: B1_TUNED (ADR-009)
- expired_waste_reduction_pct (Monte Carlo): -119.8% (95% CI -124.2 to -115.6); historical replay: -100.7%
- lost_cases_reduction_pct (Monte Carlo): -110.8% (95% CI -118.1 to -103.9); historical replay: -117.8%
- fill_rate_delta_pts (Monte Carlo): -0.56 pts (95% CI -0.58 to -0.53); historical replay: -0.39 pts
- changeover_hours_reduction_pct (Monte Carlo): +46.0% (95% CI +45.8 to +46.1); historical replay: +48.2%
- allergen_clean_hours_reduction_pct (Monte Carlo): +54.8% (95% CI +54.6 to +55.0); historical replay: -
- evaluated_cost_reduction_pct (Monte Carlo): +1.4% (95% CI +1.3 to +1.4); historical replay: +2.1%
- vs rule-of-thumb B1, expired_waste_reduction_pct: +54.2 (95% CI +53.5 to +55.0)
- vs rule-of-thumb B1, changeover_hours_reduction_pct: +30.2 (95% CI +29.9 to +30.5)
- vs rule-of-thumb B1, fill_rate_delta_pts: -0.34 (95% CI -0.37 to -0.32)
- OPT: expired 1.11% of production; fill 98.9%; changeover h/week 15.7; utilisation 73%
- B1_TUNED: expired 0.50% of production; fill 99.5%; changeover h/week 29.1; utilisation 91%
- B1: expired 2.37% of production; fill 99.3%; changeover h/week 22.5; utilisation 83%
- forecast WAPE vs seasonal naive: 34.7% better; vs 4-week moving average: -0.2%
- sensitivity: 29 cells; cost improved in 100%; waste improved in 17%
- n_paths: 200; checker_violations_total: 0
<!-- PORTFOLIO:END -->
