# Hand calculation for the simulator (T4.1.1)

Rules: see the docstring of `src/shelflife/sim/engine.py` and ADR-004. MSL = 50%.
Max ship age A_p = floor(0.5 x L / 7): A (L=14) -> 1, B (L=28) -> 2, C (L=21) -> floor(1.5) = 1.
Allergens: A none, B milk, C milk+egg -> A->B 1.0, A->C 1.0, B->C 1.0 (routine); B->A, C->A, C->B 3.5 (allergen clean).
Rates 100 cases/h; 10 h available per week. No initial inventory.

Plan: W0 [A 200, B 300]; W1 [B 100, C 200]; W2 [A 100]; W3 [].
Demand (A, B, C): W0 150/100/50, W1 100/150/100, W2 80/100/150, W3 10/100/50.

## Line
| Week | Sequence (with carry-over) | Run h | Changeover h | Allergen-clean h | Utilisation |
|---|---|---|---|---|---|
| 0 | A -> B | 5 | 1.0 (A->B) | 0 | 0.60 |
| 1 | (B) -> B -> C | 3 | 1.0 (B->C; B->B free) | 0 | 0.40 |
| 2 | (C) -> A | 1 | 3.5 (C->A, egg+milk residue) | 3.5 | 0.45 |
| 3 | - | 0 | 0 | 0 | 0.00 |
Total changeover 5.5 h, allergen-clean 3.5 h, mean utilisation 0.3625.

## SKU A (A_max = 1)
- W0: +200 @0. Ship 150 @0. Left 50 @0 -> age to 50 @1. End inv 50.
- W1: Ship 50 @1 of demand 100 -> lost 50. Nothing left. End 0.
- W2: +100 @0. Ship 80 @0. Left 20 -> 20 @1. End 20.
- W3: Ship 10 @1. Left 10 @1 = A_max, unshipped -> expired 10. End 0.
Produced 300 = shipped 290 + expired 10. Lost 50. Age-weighted shipments 0+50+0+10 = 60.

## SKU B (A_max = 2)
- W0: +300 @0. Ship 100 @0. 200 -> @1. End 200.
- W1: +100 @0. FEFO: ship 150 from @1. Left 50 @1, 100 @0 -> 50 @2, 100 @1. End 150.
- W2: Ship 50 @2 + 50 @1. Left 50 @1 -> 50 @2. End 50.
- W3: Ship 50 @2; demand 100 -> lost 50. End 0.
Produced 400 = shipped 400. Lost 50. Age-weighted 0 + 150 + (100+50) + 100 = 400.

## SKU C (A_max = 1)
- W0: no stock, lost 50.
- W1: +200 @0. Ship 100. 100 -> @1. End 100.
- W2: Ship 100 @1; demand 150 -> lost 50. End 0.
- W3: lost 50.
Produced 200 = shipped 200. Lost 150. Age-weighted 100.

## KPIs
- Demand 340 + 450 + 350 = 1140; shipped 890; fill rate 890/1140 = 0.780702.
- Lost 250; stockout SKU-weeks: A W1, B W3, C W0/W2/W3 = 5.
- Expired 10 of 900 produced = 1.1111%.
- Mean age at shipment 560/890 = 0.629213 weeks.
- Weeks of cover (mean of end_inv / mean demand over 12 SKU-weeks): mean demand A 85, B 112.5, C 87.5;
  (70/85 + 400/112.5 + 100/87.5)/12 = (0.823529 + 3.555556 + 1.142857)/12 = 0.460162.
- Conservation: 0 initial + 900 produced = 890 shipped + 10 expired + 0 ending.
