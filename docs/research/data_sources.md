# Data Sources (T1.1.1 spike) - STATUS: Favorita and FoodKeeper VERIFIED; M5 fallback not needed

Verification levels: **VERIFIED** = file opened by me; **LISTED** = confirmed in a catalog/page but file not opened; **UNVERIFIED** = not confirmed.

| Dataset | Role | URL | Terms | Access | Status |
|---|---|---|---|---|---|
| Corporacion Favorita Grocery Sales Forecasting (Kaggle) | Primary weekly demand | https://www.kaggle.com/competitions/favorita-grocery-sales-forecasting | Kaggle competition rules accepted by the builder (2026-11-17); raw and derived data not redistributed (git-ignored) | Kaggle API (`scripts/download_data.py`); .7z archives; train.csv streamed through 7-Zip, never extracted | **VERIFIED** (opened 2026-11-17): train.csv.7z 474,092,593 bytes (4,997,452,288 uncompressed); columns id, date, store_nbr, item_nbr, unit_sales, onpromotion; 125,497,040 rows; 2013-01-01..2017-08-15 (1,684 days present; e.g. 25 Dec absent); 513 negative unit_sales rows among kept items (clipped to 0). items.csv: 4,100 items, columns item_nbr, family, class, perishable; perishable=1 for 986 (DAIRY 242, DELI 91, PREPARED FOODS 26, ...). stores.csv 54 stores; holidays_events.csv 350 rows 2012-03-02..2017-12-26. Panel cut at 2017-03-27 (ADR-005). |
| M5 Forecasting - Accuracy (Walmart, Kaggle) | Fallback demand (FOODS department) | https://www.kaggle.com/c/m5-forecasting-accuracy | Kaggle rules | Same as above | UNVERIFIED (not checked this spike; known from prior knowledge only) |
| USDA FSIS FoodKeeper | Shelf-life cross-check only (consumer storage guidance, not manufacturer code dates) | Original: http://www.fsis.usda.gov/shared/data/EN/foodkeeper.json ; catalog: https://catalog.data.gov/dataset/fsis-foodkeeper-data | CC0 1.0 (data.gov catalog) | FSIS URL returned 403 to scripts and an empty page in a browser (Nov 2026). Retrieved from Internet Archive snapshot https://web.archive.org/web/20250702182320/https://www.fsis.usda.gov/shared/data/EN/foodkeeper.json (gzip; SHA-256 of downloaded bytes f0c031ff2bd191fd1ef70c6d1817b4f6c389a29c41733f9b7f9fc850a0bd4f61) | **VERIFIED** (opened): 6 sheets (Version, Category, Product 661 rows, CookingTips, CookingMethods, Data Dictionary); data version 128, modified 2018-09-06. Fields used: Name, Name_subtitle, Refrigerate_Min/Max/Metric, DOP_Refrigerate_Min/Max/Metric. Cross-check: docs/research/foodkeeper_crosscheck.md |

## What is still needed (builder, ~10 min, by hand)
1. ~~FoodKeeper~~ done (archived copy, see table).
2. ~~Kaggle~~ done 2026-11-17. (Original instructions kept for reproduction:) Create a Kaggle account, accept the Favorita competition rules, create an API token (Kaggle > Settings), put `kaggle.json` in `C:\Users\<you>\.kaggle\` (never commit it), then run `kaggle competitions download -c favorita-grocery-sales-forecasting -p data/raw/favorita`.
3. Then ask the agent to resume T1.1.1: it will open the files and fill the VERIFIED columns (columns, row counts, date range, perishable families, FoodKeeper fields).

## Fallback trigger (see ADR-001)
If Favorita files cannot be obtained or terms forbid the use, switch to M5 FOODS; if that fails, use synthetic demand with documented seasonality/noise parameters.
