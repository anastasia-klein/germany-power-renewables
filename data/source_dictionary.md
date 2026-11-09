# SMARD source data and interpretation

The current research uses three unchanged CSV exports from [Bundesnetzagentur | SMARD.de](https://www.smard.de/en/downloadcenter/download-market-data/), retrieved on 6 November 2026 under CC BY 4.0. Each covers the local calendar year 2025 at hourly export resolution. File hashes and initial coverage checks are recorded in `smard_download_manifest.json`.

## Common structure and units

| Property | Interpretation |
| --- | --- |
| Encoding and separator | UTF-8 with BOM; semicolon-separated fields |
| Start date / End date | Displayed local wall-clock labels in Europe/Berlin, without an explicit UTC offset |
| Physical coverage | 8,760 hours; the spring transition has 23 hours and the autumn transition has 25 |
| Time key | UTC `YYYYMMDDHH`; repeated local autumn labels have different keys |
| Actual interval end | UTC start plus one hour; raw End date labels alone do not resolve DST |
| MWh | Energy delivered or consumed during the interval, not installed capacity |
| MW | Average power; MWh divided by interval length in hours |
| Conversion | 1 MWh = 1,000 kWh; 1 GWh = 1,000 MWh; 1 TWh = 1,000,000 MWh |
| EUR/MWh | Wholesale electricity price per unit of energy; 100 EUR/MWh = 0.10 EUR/kWh before retail additions |
| `-` | Missing or unavailable source value; not an observed zero |
| `Calculated resolutions` | Source label on the calculated export resolution; the project uses the exported hourly values |

Energy is summed when aggregating intervals. Prices require time or volume weights. Products of hourly prices and hourly energy describe hourly market-price exposure and cannot reconstruct within-hour price/volume covariance.

## Actual consumption: 8,760 rows, six columns

File: `Actual_consumption_202501010000_202601010000_Hour.csv`.

| Source column | Silver field | Meaning and use |
| --- | --- | --- |
| Start date | Used for UTC validation | Start label for the source interval |
| End date | Validated in raw input | Source end label; raw file retained for provenance |
| grid load [MWh] | `grid_load_mwh` | Electricity taken from the public grid, excluding electricity used for pumped-storage pumping. This is the demand weight used in the current load-weighted price |
| Grid load incl. hydro pumped storage [MWh] | `grid_load_including_pumping_mwh` | Grid load plus pumping consumption; retained and reconciled, but not the current price-weighting denominator |
| Hydro pumped storage [MWh] | `pumping_consumption_mwh` | Electricity consumed to pump water uphill, a storage charging activity |
| Residual load [MWh] | `residual_load_mwh` | Grid load minus wind onshore, wind offshore and photovoltaics |

The build checks `grid load including pumping ≈ grid load + pumping consumption` and `residual load ≈ grid load − wind − solar` within source rounding tolerances. The latter uses grid load excluding pumping, matching the source definition.

Residual load is demand not covered by wind and solar. It can still be met by biomass, ordinary hydropower, other renewables, conventional generation, storage discharge and imports. It is not a direct measurement of fossil generation or emissions. It can be negative.

Pumped storage has two different series: charging consumption here and discharging generation in the generation file. They must not be added together as generation. Neither a same-hour ratio nor a full-year discharge/charge ratio alone establishes plant efficiency without storage-state and coverage information. [SMARD: pumping consumption](https://www.smard.de/en/new-on-smard-data-on-electricity-offtake-of-pumped-storage-204420), [consumption and residual load](https://www.smard.de/page/en/wiki-article/6078/6036/electricity-consumption).

## Actual generation: 8,760 rows, fourteen columns

File: `Actual_generation_202501010000_202601010000_Hour.csv`. It has two time columns and twelve energy categories. Silver unpivots these into 105,120 source-hour rows, including the unavailable nuclear category.

| Source category | Silver code | Interpretation | Research classification |
| --- | --- | --- | --- |
| Biomass | `biomass` | Electricity from biomass generation | Renewable |
| Hydropower | `hydropower` | Hydropower other than the separately reported pumped-storage output | Renewable |
| Wind offshore | `wind_offshore` | Offshore wind generation | Renewable, variable |
| Wind onshore | `wind_onshore` | Onshore wind generation | Renewable, variable |
| Photovoltaics | `solar` | Solar photovoltaic generation | Renewable, variable |
| Other renewable | `other_renewable` | Remaining renewable generation categories | Renewable |
| Nuclear | `nuclear` | Nuclear generation category; all source observations are `-` in this snapshot | Non-renewable; unavailable observations retained as null |
| Lignite | `lignite` | Brown-coal generation | Conventional fossil |
| Hard coal | `hard_coal` | Hard-coal generation | Conventional fossil |
| Fossil gas | `fossil_gas` | Gas-fired electricity generation, not the price or volume of gas fuel purchased | Conventional fossil |
| Hydro pumped storage | `pumped_storage` | Electricity produced when stored water is released through turbines | Storage output; not classified as additional renewable primary generation |
| Other conventional | `other_conventional` | Other generation in the source's conventional grouping | Conventional; the aggregate alone does not identify its detailed fuel mix |

All twelve categories are preserved. The current capture-price charts emphasize wind and solar, while the renewable-share summary uses six renewable categories and the denominator sums all observed generation categories, including storage output. The missing nuclear category is not silently converted to measured zero.

These data describe net electricity fed into the general supply network. Behind-the-meter electricity used where it is produced is outside this scope. Some generation observations, particularly for smaller installations, can be estimates; the label actual should not be read as proof that every point is a direct meter reading. [SMARD: net generation](https://www.smard.de/page/en/wiki-article/6080/208040/gross-and-net-figures), [SMARD user guide](https://www.smard.de/resource/blob/205652/63fcff2c9813096fa2229d769da164ef/smard-user-guide-09-2021-data.pdf).

German nuclear generation ended with the final plant closures on 15 April 2023. That historical fact is distinct from the file's missing-value encoding. Foreign nuclear generation may still influence the interconnected market; this German generation file does not identify the fuel origin of imports. [SMARD: 2023 market review](https://www.smard.de/page/en/topic-article/5892/211754/the-electricity-market-in-2023).

## Day-ahead prices: 8,760 rows, nineteen columns

File: `Day-ahead_prices_202501010000_202601010000_Hour.csv`. Two time columns accompany seventeen price or benchmark columns. Prices refer to the wholesale day-ahead market, not household tariffs or fuel prices.

| Source price column | Treatment |
| --- | --- |
| Germany/Luxembourg | Selected for `silver.price_hour`, bidding zone `DE-LU` |
| ∅ DE/LU neighbours | SMARD-published neighbouring-market benchmark; retained in raw data, not used as the German project price |
| Belgium | Retained in raw data |
| Denmark 1 / Denmark 2 | Separate bidding zones, retained in raw data |
| France | Retained in raw data |
| Netherlands | Retained in raw data |
| Norway 2 | One Norwegian bidding zone, retained in raw data |
| Austria | Retained in raw data |
| Poland | Retained in raw data |
| Sweden 4 | One Swedish bidding zone, retained in raw data |
| Switzerland | Retained in raw data |
| Czech Republic | Retained in raw data |
| DE/AT/LU | Historical joint-zone column; unavailable for 2025 and not substituted for DE-LU |
| Northern Italy | Italian zone, retained in raw data |
| Slovenia | Retained in raw data |
| Hungary | Retained in raw data |

Consumption and generation have country scope DE; price has bidding-zone scope DE-LU. This is an explicit pairing, not an assertion that Germany and Luxembourg are one country. Other price columns are available for subsequent market-coupling comparisons but do not describe physical imports.

The market changed from hourly to 15-minute day-ahead products on 1 October 2025. The current files have hourly export resolution throughout. A negative hourly value does not reveal how many of the four underlying quarter-hours were negative. [SMARD: resolution change](https://www.smard.de/en/15-minute-wholesale-prices-available-218078).

## Quantities that must remain distinct

| Measure | Denominator | What it describes |
| --- | --- | --- |
| Renewable generation share | Total reported generation | Generation mix, including storage output in the denominator |
| Wind-and-solar generation share | Total reported generation | Contribution of the three variable renewable categories to reported output |
| Wind + solar / grid load | Grid load excluding pumping | Variable renewable output relative to public-grid demand; can exceed 100% |
| Negative-price hour share | Valid matched physical hours in the selected period | Frequency of negative exported prices |
| Negative-price generation share | Matched MWh from the selected source | Source-volume exposure to negative exported prices |
| Capture rate | Time-average market price over the same selected hours | Relative price exposure, not an energy share or efficiency |

Domestic generation and domestic consumption need not match because of cross-border trade and storage definitions. Generation shares are not consumption-origin shares. [SMARD: trade versus physical flows](https://www.smard.de/page/en/wiki-article/5884/6140/electricity-trade-and-physical-flow-of-electricity).
