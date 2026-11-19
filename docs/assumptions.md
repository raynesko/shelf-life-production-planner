# Assumptions Register

Every row has a source, or the tag `assumption` with a plausible range. The last column links to the sensitivity
result for that assumption (one-at-a-time sweep, N = 50 paired paths per cell, see
[docs/methods/sensitivity.md](methods/sensitivity.md)). Rows that are not swept say why: a structural choice whose
effect is discussed under Limitations in the [README](../README.md#6-limitations-each-with-its-likely-direction-of-bias).
SF = [docs/results/sensitivity_findings.md](results/sensitivity_findings.md).

## Data
| ID | Assumption | Value | Range swept | Source | Sensitivity result |
|---|---|---|---|---|---|
| A-01 | Retail chain sales are a proxy for manufacturer DC demand; each plant SKU borrows the weekly pattern of one real anonymous Favorita perishable item of the same family (configs/skus.yaml) | sum over 54 stores, Monday weeks | n/a | assumption | not swept (structural); README limitation 2 |
| A-20 | Store-closure days (e.g. 25 Dec) are real lost selling time and are not imputed; returns (negative sales) clipped to 0 | 513 rows clipped | n/a | data-handling choice (src/shelflife/data/favorita.py) | not swept (affects < 0.1% of volume) |
| A-21 | Panel ends 2017-03-27 because of a PREPARED FOODS assortment change | 221 weeks | n/a | [ADR-005](decisions/ADR-005-panel-cutoff.md) | not swept (data availability) |
| A-22 | Demand unconstraining: a week below 20% of the trailing 8-week median is a supply/data gap and is replaced by that median; past-only | 18 of 2,652 SKU-weeks (0.7%) | threshold 20% | data-handling choice (favorita.unconstrain) | not swept (0.7% of SKU-weeks) |
| A-23 | Selected items must sell in each of the final 13 weeks (excludes products being phased out) | rule | n/a | data-handling choice | not swept (selection rule) |
| A-04 | Demand is scaled to plant cases so that B1 runs the line at about 85% utilisation | k = 0.198 cases per Favorita unit, frozen once calibrated (current B1: 84.8%) | demand x0.83-1.12 (utilisation ~70-95%) | assumption ([configs/calibration.yaml](../configs/calibration.yaml), [ADR-011](decisions/ADR-011-calibration-frozen.md)) | [SF: demand level](results/sensitivity_findings.md#demand-level-utilisation) |

## Plant
| ID | Assumption | Value | Range swept | Source | Sensitivity result |
|---|---|---|---|---|---|
| A-02 | Minimum remaining shelf life at plant shipment | 50% (O-04: evidence suggests 60-75% at customer receipt) | 30 / 50 / 70% | assumption; vendor sources in domain brief | [SF: minimum remaining shelf life](results/sensitivity_findings.md#minimum-remaining-shelf-life-at-shipment) |
| A-03 | Planning buckets are weekly | weekly | n/a | design choice | not swept (structural); README limitation 3 |
| A-05 | Unmet demand is lost (no backorders) | lost sales | n/a | retail perishables convention | not swept (structural) |
| A-06 | Allergen-clean rule: i -> j needs a clean iff i has an allergen not declared on j | rule | n/a | modelling simplification (domain brief s1) | not swept (rule); clean duration swept via A-11 |
| A-07 | One refrigerated filling line is the only bottleneck; 3 families, 12 SKUs | 1 line | n/a | design choice | not swept (structural); README limitation 4 |
| A-08 | Weekly available line hours | 72 h | equivalent to the utilisation sweep | assumption (80 gross less ~8 h maintenance/sanitation) | [SF: demand level](results/sensitivity_findings.md#demand-level-utilisation) |
| A-09 | Base changeover (label/format) | 0.5 h | x0.5-x2 (with A-10, A-11) | assumption | [SF: changeover times](results/sensitivity_findings.md#changeover-times) |
| A-10 | Routine (non-allergen) clean at flavour change | 0.5 h | x0.5-x2 | assumption | [SF: changeover times](results/sensitivity_findings.md#changeover-times) |
| A-11 | Allergen clean (wet clean + verification) | 3.0 h | x0.5-x2 | assumption | [SF: changeover times](results/sensitivity_findings.md#changeover-times) |
| A-12 | Line rate per SKU | 210-360 cases/h | via the utilisation sweep | assumption | [SF: demand level](results/sensitivity_findings.md#demand-level-utilisation) |
| A-14 | Min / max run length | 1.5 h / 24 h | not swept | assumption | not swept (rarely binding: runs are sized by demand) |
| A-15 | SKU shelf lives (days from production, sealed packaged product) | 14-56 days by SKU | x0.5 / 0.75 / 1 / 1.25 | assumption; vs USDA FoodKeeper v128: dairy/dips consistent; prepared foods not comparable ([crosscheck](research/foodkeeper_crosscheck.md)) | [SF: shelf life](results/sensitivity_findings.md#shelf-life) |
| A-16 | SKU allergen sets assigned by recipe type (pine nuts treated as tree nuts) | plant.yaml | n/a | assumption; FDA Big 9 vocabulary | not swept (recipe definition) |
| A-18 | Unsaleable stock (past minimum remaining life) is written off; no secondary channel | rule | n/a | [ADR-004](decisions/ADR-004-expiry-accounting.md) (waste is an upper bound) | not swept (structural) |
| A-19 | Production is usable for shipment in the week it is made | rule | n/a | weekly-bucket simplification | not swept (structural); README limitation 3 |

## Planning and evaluation
| ID | Assumption | Value | Range swept | Source | Sensitivity result |
|---|---|---|---|---|---|
| A-13 | Unit production cost per case (cost units; never a resume claim) | 18 | n/a (cancels in the comparison: both planners pay it per case) | assumption | not swept separately; ratios via A-25 |
| A-17 | Planning horizon 13 weeks | 13 | n/a | design choice (S&OP look-ahead) | not swept (solve time grows with horizon) |
| A-24 | Safety-stock service target alpha (a TARGET, not a result) | 95% | 80-99% | assumption | [SF: frontier](results/sensitivity_findings.md#waste-vs-service-frontier) |
| A-25 | Objective weights: holding 0.25/case-week, expiry 4/case, lost sale 40/case, changeover 400/h, safety-stock shortfall 2/case ([configs/costs.yaml](../configs/costs.yaml)) | see file | expiry 2/4/10, changeover 200/400/800, lost sale 25/40/80 | assumption | [SF: cost weights](results/sensitivity_findings.md#cost-weights) |
| A-26 | Decomposition charges 1.0 h per run (cheapest incoming changeover), chosen on the validation year | 1.0 h | 4 alternatives on the validation year | [ADR-007](decisions/ADR-007-changeover-estimate-validation.md) | validation-year comparison in ADR-007; scales with the changeover sweep |
| A-27 | Monte Carlo demand = actual test-year demand + block-bootstrapped standardised validation errors | block 4 weeks | error x0.5-x2 | [ADR-008](decisions/ADR-008-scenario-centre.md) | [SF: forecast error](results/sensitivity_findings.md#forecast-error) |
| A-28 | B1 cover (order-up-to) | 0.5 week extra for the headline baseline (chosen on the validation year); 1 week for the rule-of-thumb B1; capacity repair defers the best-covered SKU (ADR-010) | 0.5-3 weeks | [ADR-006](decisions/ADR-006-baseline-reorder-point.md), [ADR-009](decisions/ADR-009-baseline-tuned-on-validation.md), [ADR-010](decisions/ADR-010-baseline-capacity-repair.md) | [SF: frontier](results/sensitivity_findings.md#waste-vs-service-frontier) |

## OPEN items (from docs/research/domain_brief.md s4)
| ID | Question |
|---|---|
| O-01 | Exact 21 CFR 117 subsection citations for allergen controls and sanitation (eCFR not fetched) |
| O-02 | Is an allergen clean required for subset-allergen transitions in specific plants? |
| O-03 | Realistic allergen-clean and routine changeover durations (no public dataset known); bracketed by the x0.5-x2 sweep |
| O-04 | Typical minimum remaining shelf life and whether to model it at receipt or at shipment; default 50% may be low; bracketed by the 30-70% sweep |
| O-05 | Does best-by vs use-by change expiry handling? |
| O-06 | Realistic run-size minimums and line rates for refrigerated prepared foods |
| O-07 | Plausibility of mapping Favorita families to one manufacturer's SKU set |
| O-08 | Keep prepared-food SKUs as sealed packaged (MAP/HPP) product with 14-21 d life, or shorten toward FoodKeeper's 3-5 d (breaks weekly buckets)? Default: keep |
