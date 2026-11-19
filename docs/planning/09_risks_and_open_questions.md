# 09 - Risks and Open Questions

Risks with mitigations are in `01_charter.md`. Below are decisions for the builder. **None block starting**; each has a default that the tickets already assume. Reply to change a default; changes may touch the listed tickets.

| # | Question | Default assumption (in use) | Tickets affected |
|---|---|---|---|
| 1 | Which demand source? | Favorita (Kaggle) primary; M5 FOODS fallback; synthetic fallback if both blocked | T1.1.1, T2.1.1 |
| 2 | Solver: OR-Tools only, or Gurobi (free academic licence)? | OR-Tools (SCIP/CP-SAT); HiGHS as alternative; no commercial dependency so reviewers can reproduce | T1.2.2, T4.2.1 |
| 3 | Product world: refrigerated prepared foods (dairy, deli, bakery, eggs)? Or pharma-adjacent (e.g. nutraceuticals/OTC with expiry dating)? | Food, because the Favorita `perishable` flag and the allergen rules fit; pharma noted as an extension (expiry dating and cleaning validation are analogous) | T2.2.1 |
| 4 | Planning granularity | Weekly buckets, shelf life 14-56 days; daily scheduling out of scope | T2.2.1, T4.2.x |
| 5 | Minimum remaining shelf life at shipment | 50% (ASSUMPTION). Vendor sources (not authoritative) suggest 60-75% remaining at customer receipt, so 50% at shipment is lenient; consider 60%. Swept 30-70% | T2.2.1, T5.2.1 |
| 6 | Changeover and cleaning times | Assumed ranges (no public per-line dataset known to me; flag); swept x0.5-2 | T2.2.2, T5.2.1 |
| 7 | Monte Carlo N and runtime | N=200 main, ~50 per sensitivity cell; reduce if the 52-week replay exceeds ~90 min | T5.1.1, T5.2.1 |
| 8 | Hosting the dashboard | Run locally; optional free Streamlit Community Cloud | T6.2.2 |
| 9 | Is 75.5 h of scheduled work realistic at your pace? | It leaves ~0-5 h slack at 8-10 h/week; the cut order in 04 applies automatically at 8 h/week | all |
| 11 | Forecast headline target: the charter says '>= 10% WAPE vs seasonal naive', but seasonal naive is the weakest benchmark on this data (test WAPE 17.6% vs 11.5% for the 4-week moving average, which is also B1's forecast). | Recommended: report improvement vs the BEST benchmark (MA4) as the headline; also show seasonal naive. Target vs MA4 >= 5% (TARGET; modest because MA4 is strong here) | T3.2.3, T5.1.2, T7.2.1 |
| 12 | Prepared-food SKUs as sealed packaged product (O-08 in assumptions) | Keep (14-21 d shelf life) | T2.2.1 |
| 10 | Does your current ISE coursework offer a real-plant case or data you may use (with permission) to validate? | No; all synthetic | T7.1.1 |

## Facts to double-check yourself (not verified by this planning pass)
- Kaggle competition terms of use for Favorita (do not redistribute raw data; keep `data/raw` out of git).
- USDA FoodKeeper values are consumer storage guidance, not manufacturer date coding; use only as ranges.
- Typical retailer minimum-remaining-shelf-life requirements (varies; treat as assumption).
- FSMA 21 CFR 117 specific subsection citations for allergen controls (check eCFR text before quoting section numbers).
