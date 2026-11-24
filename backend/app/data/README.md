# Source-share data (review before relying on it)

| File | What | How it was made |
| --- | --- | --- |
| `source_shares_studies.csv` | Static PM2.5 source shares per city (one study per city) | UrbanEmissions.info APnA city reports, "PM2.5 concentration: source-wise percentage share in 2018". Read from each report's pie chart (labels by leader line and APnA's fixed sector colours) on 2026-11-24. Values exactly as printed; they sum to 99.9–100.1 because of rounding |
| `delhi_dss_daily.csv` | Daily Delhi shares from IITM's Decision Support System | **Entered manually** from the DSS "Daily Mean" page ("Fractional contribution to PM2.5 in Delhi", DSS forecast for 23–26 Nov 2026, read on 2026-11-24). The DSS site publishes no terms of use or data API, so VayuKavach does not scrape it automatically. Mapping: Delhi's own sectors one-to-one; the 19 NCR districts → `outside_city`; Biomass Burning → `stubble_fires`; DSS "Others" (outside the modelled region) + Delhi other sectors → `other`. DSS values add up to ~101% as published; the API scales to 100 |

Cities without a study in this file (Delhi static, Kanpur, Chennai, Bengaluru, Patna: their APnA
reports were not available online) show "No source data for this city yet" instead of a guess.
Load into the database with `cd jobs && uv run python run.py sources`.
