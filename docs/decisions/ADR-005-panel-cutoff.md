# ADR-005: End the demand panel at week 2017-03-27

- **Status:** ACCEPTED (T2.1.1)
- **Context:** The Favorita source runs 2013-01-01 to 2017-08-15 (1,684 days; 125,497,040 rows read). From the week starting **2017-04-03**, the long-running PREPARED FOODS perishable items sell zero in every week, while total family sales continue (about 42k units/week in March 2017, then 33-37k/week). Ten new PREPARED FOODS item numbers first sell around 2016-11-27 and carry the family afterwards. This is an assortment change (relaunch or renumbering), not a demand collapse. As a result, no PREPARED FOODS item met the >= 95% non-zero-weeks rule over the full span (best 92.1%), and the 19 zero weeks are identical across the top items.
- **Options considered:**
  1. Chain old to new item numbers. Rejected: no mapping exists in the data; guessing would invent data.
  2. Model PREPARED FOODS at `class` level and the other families at item level. Rejected: inconsistent unit of analysis.
  3. **End the panel for all SKUs at the last week before the switch.** Chosen: simple, honest, common calendar.
- **Consequences:** 221 contiguous weeks per SKU (2013-01-07 .. 2017-03-27), enough for >= 104 training + 52 validation + 52 test weeks (117 / 52 / 52). The final 4.5 months of the source are unused. The selection rule is applied within the cut window; result in `configs/skus.yaml`.
- **Interview angle:** a real planning-data problem (SKU supersession or new product introduction) detected by a coverage rule and handled without fabricating a mapping.
