# Technical implementation, validation and archive

[Project overview and findings](../README.md)

This page records the Fabric implementation, execution evidence and retained artifacts. Research conclusions are described separately in [2025 findings](eda_2025_findings.md) and [metric and figure interpretation](metrics_and_figures.md).

## Data preparation and model

The implemented flow is **SMARD CSV files in OneLake → silver Delta tables → exploratory analysis → gold → Direct Lake semantic model → Power BI**.

Silver contains `consumption_hour`, `generation_hour`, `price_hour` and `dim_time_hour`. Gold contains three dimensions (`dim_time_hour`, `dim_market`, `dim_generation_source`) and two hourly facts (`fact_market_hour`, `fact_generation_hour`). The [gold metric contract](../model/gold_metric_contract.json) retains hourly numerator and denominator components so weighted prices and rates can be recomputed for each filter context.

The notebook collection separates source profiling, silver preparation, exploration and gold publication. Every code cell in the silver build belongs to its validation, transformation or publication flow; exploratory previews are kept in notebook 03. [Fabric item definitions](../fabric/) are the versioned source of truth; [portable notebooks](../notebooks/) are output-free exports. The workspace is connected to GitHub.

The semantic model `sm_power_renewables` has five gold-model relationships and nineteen core measures. It also includes nine report measures for adaptive axes, colours and icons, eight descriptive supply-and-demand measures, and eight hourly-profile measures, including four hidden common-axis helpers. Definitions are retained in the [semantic specification](../model/semantic_model_spec.json), [DAX measures](../model/semantic_measures.dax) and native TMDL model under `fabric/`.

## Validation and calculation rules

- The three unchanged SMARD exports cover the full local calendar year 2025. Their hashes and source profiles are retained. UTC keys distinguish repeated local timestamps; local dates support calendar analysis.
- Numeric source fields use fixed precision. Missing markers remain distinct from zero, including unavailable nuclear observations. Negative prices remain valid observations.
- Grid load including pumping is reconciled with grid load plus pumping consumption. Residual load is reconciled with grid load minus wind and solar generation.
- Generation is aggregated to the required grain before joining consumption and prices, preventing duplicated hourly records.
- Weighted prices are recalculated from matched hourly components. Load-weighted price is `sum(price × grid load) / sum(grid load)`. It is market-price exposure of the load profile, not a complete consumer bill.
- The renewable share denominator is total reported generation, including pumped-storage output. Wind-and-solar generation divided by grid load is a separate measure.
- Hourly prices and energy cannot reconstruct within-hour covariance or quarter-hour settlement. Calendar-adjusted associations remain descriptive, not causal or forecasting claims.

## Report behaviour

The [native PBIR report](../fabric/rpt_power_renewables.Report/) uses the Direct Lake model over gold. Three small presentation tables provide shared source colours, SVG icons and adaptive-axis metadata.

Month selectors use calendar names and filter each page. One selected month switches timeline charts to days; multiple months use monthly values. The generation-source selector changes source-specific charts and cards while the comparison table retains all sources for the selected period. Chart clicks do not cross-filter unrelated KPIs.

Hourly profiles compare Monday–Friday with Saturday–Sunday; holidays follow their weekday. Price panels show mean, median, P10 and P90. Power panels stack Solar, combined Wind and Residual load in GW with a Grid load line on the same scale. Negative residual values extend below zero. Paired panels share filter-aware scales. Percentiles describe observed prices, not confidence intervals.

Supply & demand compares hourly price with residual load, wind and solar, plus a month-by-local-hour mean-price heatmap. Pearson correlations recalculate for the selected months. The visual style follows the author's Global Critical Materials report.

## Execution evidence

The original combined notebook produced the first monthly analysis, including January's time-average/load-weighted prices of 114.14/118.49 EUR/MWh and June's 63.99/63.60 EUR/MWh. Its [execution snapshot](../evidence/03_explore_power_market_snapshot.ipynb), [monthly CSV](../evidence/monthly_price_profile.csv) and historical exports are retained.

The expanded EDA was executed locally against the original exports, with [captured outputs](../evidence/eda_2025/03_power_market_eda_local.ipynb), tables and figures. The project author confirmed successful expanded EDA and gold execution in Fabric on 9 November 2026, including the generation-mix addition. These earlier local outputs remain labelled separately from Fabric evidence.

On 18 November 2026 all four current notebooks were rerun successfully in Fabric and exported with authentic outputs: 31 executed code cells, no error outputs. Their code matched the versioned portable sources by AST comparison. The [Fabric execution archive](../evidence/fabric_runs/) includes the output inventory and historical combined notebook/HTML export. Notebook 04 confirmed 8,760 time rows, one market, twelve sources, 8,760 market facts and 105,120 generation facts.

Browser checks verified annual totals, solar capture metrics, source/month filters, hourly percentile bands, signed stacks and page order. The [web counterpart](../web/) was checked against Fabric controls and all 624 independent hourly-profile groups. Its snapshot was derived from the validated source CSVs; it is not a direct OneLake export.

The additional `05_archive_onelake` notebook copied the nine physical silver/gold tables directly from OneLake. Its successful execution output is retained alongside the four analysis/build notebooks. The downloaded Delta snapshots were reopened locally and compared row by row with their Parquet snapshots.

## Retained artifacts and scope

- [Power BI Service video and five-page PDF](../evidence/powerbi/archive_2026-11-18/)
- [Physical silver/gold Delta and Parquet archive](../evidence/onelake/)
- [Preservation status and remaining dependencies](preservation_status.md)
- [Independent interactive web dashboard](https://anastasia-klein.github.io/germany-power-renewables/)

Fabric Git integration retains notebook source rather than cell outputs; executed exports are stored separately in `evidence/`. The physical archive includes Delta data, transaction logs, schemas, history and file hashes. It does not constitute a complete workspace restore. The separate preservation page records exclusions and trial-related dependencies.

Data Factory orchestration remains planned; no pipeline execution is claimed. An offline Import-mode PBIX has not been validated. Unauthenticated access to the original Power BI report has not been verified; the public GitHub Pages dashboard is independently available.

A private household extension will compare tariffs using Tibber consumption data. It is outside this public market analysis; household records and credentials are excluded. Candidate forecast, flow and fuel datasets are listed in the [data extension plan](data_extension_plan.md).
