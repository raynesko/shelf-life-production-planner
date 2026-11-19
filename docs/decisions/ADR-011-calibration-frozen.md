# ADR-011: The demand scale k is frozen once calibrated

Status: accepted (2026-11-18)

## Context
`scripts/calibrate.py` picks one demand scale k (plant cases = k x Favorita units) so that the rule-of-thumb B1
loads the line to about 85% on pre-test weeks (A-04). It set k = 0.198324 before any result, with the B1 of that
time. ADR-010 later changed B1's capacity repair. The clean-clone check (T7.2.2) re-ran the whole pipeline from raw
data. Re-deriving k with the new B1 gave 0.19954 (+0.6%), which re-scaled the plant and moved the committed
historical replay by up to 20 points on lost cases. So the pipeline was not reproducible from a clean clone.

## Decision
k is a plant-design assumption, not something re-fitted whenever planner code changes. If
`configs/calibration.yaml` exists, `calibrate.py` keeps its k and only checks that the current B1 still loads the line
within 85% +/- 2 pts. With the current B1 it gives 84.8%. If the check fails, the script stops. Re-deriving k needs
`--recalibrate` and a new ADR.

## Consequences
- A clean clone rebuilds the same plant, so the committed results are reproducible.
- k stays 0.198324 for every result in the repo. The 85% target is itself an assumption, swept from about 70% to 95%
  in the sensitivity grid (demand x0.83-1.12), so a 0.6% difference in k is far inside the explored range.
- The calibration is no longer self-adjusting. A planner-code change that moved B1's load outside 83-87% would
  fail loudly instead of silently re-scaling demand.
