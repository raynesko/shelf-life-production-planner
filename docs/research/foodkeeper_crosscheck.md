# FoodKeeper cross-check of model shelf lives

**Source:** USDA FSIS FoodKeeper, data version 128 (modified 2018-09-06 per its Version sheet), CC0. The FSIS URL (`https://www.fsis.usda.gov/shared/data/EN/foodkeeper.json`) returned 403 to scripts and an empty page in the builder's browser (Nov 2026). The file was taken from the Internet Archive snapshot of that exact URL dated **2025-07-02**: `https://web.archive.org/web/20250702182320/https://www.fsis.usda.gov/shared/data/EN/foodkeeper.json` (gzip-encoded; 661 products). SHA-256 of the downloaded bytes: `f0c031ff...` (prior to decompression; recorded in data_sources.md).
**Reproduce:** `python scripts/foodkeeper_crosscheck.py` -> `data/processed/foodkeeper_crosscheck.csv`.

## What FoodKeeper measures (and does not)
- `DOP_Refrigerate_*` = how long a **consumer** can keep the product refrigerated **from the date of purchase**. That is roughly the remaining life at retail purchase, so it is a rough *lower-bound proxy* for remaining shelf life at the shelf, not total life from manufacture.
- `Refrigerate_*` without DOP = storage of a **prepared or opened** item (deli-counter or homemade salads, leftovers). It describes fresh deli-made food, not factory-sealed, code-dated packaged product.
- FoodKeeper does not give manufacturer shelf life from date of production. Packaged products can last longer through modified-atmosphere packaging, high-pressure processing (HPP) or preservatives. I have **not verified** typical manufacturer code dates for these categories.

## Comparison
| SKU | Model (days from production) | FoodKeeper match | FoodKeeper value | Reading |
|---|---|---|---|---|
| SKU-01/02 yogurt | 35 | Yogurt (#33) | 7-14 d from purchase | Consistent: at 50% MSL, 35 d leaves >= 17.5 d at shipment; transit plus retail then leaves about 1-2 weeks. |
| SKU-03 cream cheese | 56 | Cream cheese (#10) | 14 d from purchase | Plausible-to-generous. Wrapped cream cheese typically carries a longer code; **UNVERIFIED**. |
| SKU-04 pudding | 28 | Pudding (#28) | "package use-by date" | No numeric anchor; assumption stands. |
| SKU-05 hummus | 42 | Commercial (#181) / traditional (#183) | 90 d from purchase / 7 d | Model sits between preserved and fresh. Defensible if described as a refrigerated, non-HPP commercial hummus; conservative versus #181. |
| SKU-06 tzatziki | 21 | Dips, sour cream based (#16) | 14 d from purchase | Consistent. |
| SKU-07 pesto | 28 | Pesto, jarred (#354) | 180 d | Jarred pesto is a different (ambient-stable) product; refrigerated fresh pesto is not listed. No anchor. |
| SKU-08 guacamole | 14 | Guacamole (#180) | 3-4 d prepared | Not comparable (prepared vs packaged/HPP). 14 d is an **assumption** for packaged product; FoodKeeper says fresh-made guacamole lasts 3-4 d. |
| SKU-09 pasta salad | 14 | Pasta salad (#420) | 3-5 d prepared | Same as above. |
| SKU-10 egg salad | 14 | Egg salad (#190) | 3-4 d prepared | Same as above. |
| SKU-11 tuna salad | 14 | Seafood salads (#417) | 3-4 d prepared | Same as above. |
| SKU-12 vegetable soup | 21 | Soup, stews (#193) | 3-4 d prepared | Same as above. |

## Conclusion
- Dairy and dip shelf lives are **consistent** with FoodKeeper's from-purchase values once the minimum remaining shelf life at shipment and distribution time are accounted for.
- For the five prepared-food SKUs, FoodKeeper only describes fresh/prepared storage (3-5 d). The model's 14-21 d values therefore **remain assumptions** representing sealed, packaged (e.g. MAP/HPP) product and cannot be validated with this source. They are flagged in `docs/assumptions.md` (A-15) and will be swept (-50% to +25%) in T5.2.1.
- **Builder decision needed (open question):** keep the prepared-food SKUs as sealed packaged products (current), or shorten their lives toward FoodKeeper. Shorter than 14 d breaks the weekly-bucket model (A-03): those products would have to ship the week they are made and would need daily planning.
