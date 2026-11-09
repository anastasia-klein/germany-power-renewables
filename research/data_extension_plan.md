# Additional data for the research

The first reporting model describes observed hourly price exposure in 2025. Broader data would help explain market conditions and test whether the findings persist across years. The following series are candidates; none of these additional datasets has been ingested by this document.

| Priority | Data | Source and availability | Research use |
| --- | --- | --- | --- |
| Immediate | Full generation mix, including coal, gas and storage output | Already present in the current raw file and silver tables | Context for wind and solar patterns; supplement the focused EDA |
| Next | Day-ahead and intraday generation forecasts: onshore wind, offshore wind, solar, other and total | [SMARD forecast data](https://www.smard.de/page/en/wiki-article/6080/206318/forecast-data) | Compare forecast and actual profiles; investigate forecast errors and distinguish information sets |
| Next | Forecast grid load and residual load | [SMARD forecast data](https://www.smard.de/page/en/wiki-article/6080/206318/forecast-data) | Demand expectations and expected remaining demand |
| Next | Physical cross-border imports and exports, by border and direction | [SMARD trade and physical-flow data](https://www.smard.de/page/en/wiki-article/5884/6140/electricity-trade-and-physical-flow-of-electricity) | Interconnection usage and observed system balance |
| Next | Commercial cross-border exchange schedules | Same SMARD source; distinct from physical flows | Market coupling and trading positions; do not substitute physical flows |
| Next | Other bidding-zone prices | Already present in the current raw price file; not yet published to silver price tables | Compare DE-LU with connected markets and price spreads |
| Next | Full 2024 history and quarter-hour data for 2025 | SMARD download center | Second-year comparison; resolution sensitivity and within-hour exposure |
| Later | Pan-European load, generation, forecasts, transmission and outages | [ENTSO-E Transparency Platform](https://www.entsoe.eu/data/transparency-platform/); programmatic access and dataset-specific terms require verification | Foreign supply availability, nuclear outages and interconnected-market context |
| Later | Monthly European gas and coal price benchmarks | [World Bank Pink Sheet](https://www.worldbank.org/en/research/commodity-markets) publishes downloadable monthly historical series | Public macro context; not hourly power-plant fuel costs or an hourly TTF spot series |
| Conditional | Daily TTF/THE gas, coal and carbon-market series | [EEX market-data services](https://www.eex.com/en/market-data) and other primary providers; historical coverage and public redistribution rights vary | Fuel and carbon cost drivers; paid or non-redistributable data are not assumed available for this public project |

## Data contracts and chronology

The current build targets complete 2025 files and expects 8,760 hours and unavailable nuclear values. A 2024 extension requires 8,784 physical hours. Data before Germany's 2023 nuclear closure require a different source-coverage expectation; current nuclear assertions must not be reused unchanged. Partial 2026 data need an explicit partial-period contract rather than being passed through the full-year build.

Each new series needs a declared region or bidding zone, physical interval, unit, issue time when relevant, revision policy, source hash and join grain. Power in MW must be converted using interval duration before combining with MWh; quarter-hour energy is summed, not averaged, when building an hourly quantity.

For forecasts, a delivery timestamp alone is insufficient. The day-ahead label does not prove that the specific version was available before the price auction. SMARD describes generation forecasts published by 18:00 for the next day, while the market auction occurs earlier. A pre-auction model needs the relevant earlier issue vintage; using a later revised forecast or realized flow would introduce future information. Initial forecast-versus-actual research can proceed with explicit limits on what historical vintages are available.

Monthly fuel benchmarks should be analyzed at monthly frequency or as explicitly labeled period context. Repeating the same monthly value across 720 hourly rows does not create 720 independent fuel-price observations. For forecasts, the historical publication date matters as well as the month being described. Natural-gas electricity generation in MWh is not the natural-gas fuel price.

Neighboring nuclear supply may affect the interconnected market even though the German nuclear series is unavailable in this snapshot. Imports are not labeled by production technology in ordinary flow data; country-level imports must not be assigned a nuclear share without an explicit allocation method and additional data.

The current scope supports descriptive reporting. Additional explanatory series should be added incrementally with coverage checks and time alignment, rather than delaying all reporting until a complete price-formation model exists.
