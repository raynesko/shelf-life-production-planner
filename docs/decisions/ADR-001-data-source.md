# ADR-001: Demand data source

- **Status:** ACCEPTED 2026-11-17: Favorita files opened and verified (docs/research/data_sources.md); fallback not triggered
- **Decision:** Favorita (Kaggle) is the primary demand source because its item metadata reportedly includes a `perishable` flag and it has ~4.6 years of daily data (needed for >=104 train + 52 validation + 52 test weeks). M5 FOODS is the fallback; documented synthetic demand is the last resort.
- **Fallback trigger:** files unobtainable, columns differ materially from expectation (no usable perishable families, fewer than 208 weeks), or terms forbid use.
- **Consequences:** raw data stays out of git; a download script (T2.1.1) plus manual instructions; "retail sales as DC demand proxy" is a stated assumption.
- **Outcome:** columns as expected; 986 perishable items; 1,684 days. An assortment change in PREPARED FOODS required ending the panel at 2017-03-27 (ADR-005).
