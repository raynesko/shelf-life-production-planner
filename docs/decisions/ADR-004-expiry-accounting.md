# ADR-004: When does inventory count as expired waste?

- **Status:** ACCEPTED (T4.1.1)
- **Context:** With a minimum-remaining-shelf-life (MSL) rule at shipment, a cohort becomes unsaleable to customers *before* its code date passes. The original KPI spec counted waste only when age exceeded shelf life, which would leave unsaleable stock sitting in inventory and inflate weeks of cover.
- **Decision:** A cohort is written off as expired (unsaleable) waste at the end of the last week in which it could still ship, i.e. when age a >= A_p = floor((1 - MSL) x L_p / 7) and it was not shipped. Production is usable in the week it is made; FEFO; lost sales.
- **Consequences:** Waste is counted earlier and is higher than a pure code-date rule, the realistic case for a manufacturer selling to retailers with MSL terms. A_p is sensitive to MSL and shelf life (e.g. L = 14 days at MSL 70% gives A_p = 0: product must ship in the week it is made), which the sensitivity sweep covers. Secondary channels (donation, discount outlets) are not modelled; in reality some of this stock would be recovered, so waste is an upper bound. Recorded as a limitation.
- **Changed:** `docs/research/kpi_definitions.md` expired-waste row and conventions.
