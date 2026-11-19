# Domain Brief - Shelf-Life-Aware Production Planning (T1.1.2)

Tags: claims without a link, or with a weak (vendor/secondary) source, are marked **UNVERIFIED** or **(vendor source)**. Nothing here is plant-specific; the plant is hypothetical.

## 1. Allergens and why changeovers cost line hours
- **Nine major food allergens** in the US: milk, eggs, fish, crustacean shellfish, tree nuts, peanuts, wheat, soybeans, sesame. Sesame became the ninth on **1 Jan 2023** under the FASTER Act of 2021, which amended FD&C Act section 201(qq); the original eight came from FALCPA (2004). Source: [MSU Extension](https://www.canr.msu.edu/news/the-faster-act-sesame-as-major-food-allergen), [Mondaq/Keller & Heckman](https://webiis10.mondaq.com/unitedstates/food-and-drugs-law/1270304/sesame-listed-as-major-food-allergen) (secondary; confirm on fda.gov).
- **Cross-contact:** unintended transfer of an allergen into a food that does not declare it. If a line runs product *i* (containing allergen X) and then product *j* (not declaring X), residue of X on equipment is an undeclared allergen on *j*. This is the **modelling rule used here**: changeover *i -> j* requires an allergen clean iff *i* carries an allergen not declared on *j*. Running *i* -> *j* where allergens(*i*) is a subset of allergens(*j*) needs only a routine changeover. (My simplification; some plants also impose stricter or product-specific rules, e.g. for peanut/tree nut or sesame. **UNVERIFIED** against any specific plant practice.)
- **Regulatory frame:** FSMA's Preventive Controls for Human Food rule (21 CFR Part 117) requires a food safety plan whose preventive controls include **allergen controls**, plus current good manufacturing practice (Subpart B) covering sanitation and cross-contact. Specific subsection numbers (e.g. 117.135 for preventive controls, 117.35 sanitation) **UNVERIFIED**: the eCFR page could not be fetched; check eCFR before quoting.
- **Cleaning and verification:** FDA's Hazard Analysis and Risk-Based Preventive Controls guidance discusses allergen cleaning procedures and their verification; its Appendix 10 (non-binding "current thinking") says a cleaning programme should be shown to remove allergens, and ATP swabs can serve for routine verification only after validation ([FDA guidance, search-result excerpt](https://fda.gov/media/129671/download)). One teaching source states validation is not strictly required ([Colorado State](https://colostate.pressbooks.pub/foodsafety101/?p=94)); the two views conflict, so I treat validated cleaning as good practice and **do not model validation**. Cleaning durations in this project are **assumptions**.
- **Typical sequencing practice:** run allergen-free products first and allergen-heavy ones last, with the wet clean at end of cycle (an "allergen ladder"). Used here as baseline B1. **UNVERIFIED** as a formal standard; it is common plant practice.

## 2. Shelf-life vocabulary
- **Date of manufacture / code date**, **best-by** (quality) vs **use-by** (safety-oriented, typically for highly perishable items). Products here are treated as expiring when age exceeds shelf life; the retail label type is not modelled.
- **FEFO** (first expired, first out) vs FIFO: FEFO issues the oldest-expiring lot first; for single-date-per-lot products they coincide. The simulator uses FEFO.
- **Minimum remaining shelf life (MSL) at receipt:** customers reject product that arrives with too little life left. Vendor sources claim retailers commonly require roughly **60-75% of life remaining at receipt**, club channels lower, and one government programme 85% ([vendor guides found via search, e.g. cleverence.com](https://www.cleverence.com/inventory/guides/minimum-shelf-life/)); actual values are customer-specific contract terms. **(vendor sources; not authoritative).**
  **Flag for the builder:** the plan's default of 50% remaining *at shipment from the plant* is lower than these figures (and transit consumes further life). Sweep 30-70% is planned; consider raising the default to 60%. This materially shortens the usable selling window for 14-56-day products.
- **USDA FoodKeeper** is consumer storage guidance (CC0 data on [data.gov](https://catalog.data.gov/dataset/fsis-foodkeeper-data)), not manufacturer code-date validation; use only as ranges for plausibility.

## 3. Production-planning concepts used
- **Lot sizing / run length:** batches trade changeover cost against inventory and expiry. **Sequence-dependent setup (changeover) times** make this a capacitated lot-sizing problem with sequencing (the CLSP/GLSP family; formulation chosen in T4.2.1).
- **Safety stock** covers forecast error over the lead time; here safety stock = z x forecast-error sigma by horizon, **capped by shelf-life window**, because holding stock of a short-life product is itself a waste risk.
- **Rolling horizon:** plan 13 weeks, execute week 1, re-plan weekly (S&OP-style cadence).
- **Lost sales vs backorders:** retail perishables are modelled as **lost sales** (unfilled demand is lost).
- **OEE** (availability x performance x quality): the standard line-efficiency metric. This project does **not** model downtime, speed or yield losses; capacity is nominal available hours. Stated limitation (biases utilisation headroom upward).
- **Quality links (not modelled):** GMP deviations, CAPA, hold/release, and recall exposure from allergen errors are out of scope; the independent plan checker enforces planning rules only.

## 4. Things I am unsure about (copied to docs/assumptions.md as OPEN)
1. Exact 21 CFR 117 subsection citations for allergen controls and sanitation.
2. Whether allergen-clean is required for subset-allergen transitions in specific plants (rule is a simplification).
3. Realistic allergen-clean and routine changeover durations per line type (no public dataset known).
4. Typical MSL values by customer and whether to model at receipt vs shipment.
5. Whether best-by vs use-by distinction should change expiry handling.
6. Realistic run-size minimums and line rates for refrigerated prepared foods.
7. Whether Favorita families map plausibly to a single manufacturer's SKU set (proxy validity).

## 5. Glossary
| Term | Meaning here |
|---|---|
| Allergen cross-contact | Unintended allergen transfer to a product that does not declare it |
| Big 9 | FDA major allergens incl. sesame (2023) |
| Allergen ladder | Static run order from fewest to most allergens |
| Wet clean / CIP | Water/chemical cleaning of product-contact equipment (CIP = clean-in-place) |
| Changeover | Time between last good unit of product i and first of j |
| Sequence-dependent setup | Changeover time depends on the (i, j) pair |
| SMED | Single-minute exchange of dies: method to cut changeover time (context; not modelled) |
| Lot sizing | Choosing run quantities per product per period |
| Safety stock | Buffer inventory against forecast error |
| Weeks of cover | Inventory / average weekly demand |
| FEFO / FIFO | First-expired / first-in first-out issue rules |
| Shelf life | Days from manufacture until the product expires |
| MSL | Minimum remaining shelf life required at shipment or receipt |
| Fill rate | Shipped / demanded units |
| Lost sales | Unmet demand not carried forward |
| Expired waste | Units discarded because age exceeded shelf life |
| WAPE | Weighted absolute percentage error: sum|error| / sum(actual) |
| MASE | Error scaled by in-sample naive error |
| OEE | Availability x performance x quality |
| Rolling horizon | Re-plan each period over a moving window |
| S&OP | Sales and operations planning cycle |
| FoodKeeper | USDA FSIS consumer food-storage dataset |
| CAPA | Corrective and preventive action (quality system; not modelled) |
