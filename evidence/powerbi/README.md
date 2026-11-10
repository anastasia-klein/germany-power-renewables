# Power BI report rendered in Microsoft Fabric

These screenshots capture the actual authenticated Fabric report, not a local mock-up. The report queries `sm_power_renewables`, which reads the five gold tables in Direct Lake mode. The browser checks and deployment state are recorded in [validation.json](validation.json).

## Market overview

Market and load-weighted prices, German grid load, renewable share of observed generation, the full generation mix and wind-plus-solar output relative to grid load. The renewable denominator includes reported pumped-storage output; nuclear observations remain unavailable.

![Market overview in Fabric](01_market_overview.png)

## Generation and value

The selected source defaults to Solar (photovoltaics). Each source has a fixed color and an original inline SVG icon; the selected-source cards and charts reuse that color. The cards and monthly charts use the selected source. The comparison table retains all sources for the selected months. Capture price is generation-weighted day-ahead price exposure, not realized generator revenue or profit. Capture rate is a ratio to the same period's market average.

![Generation and value in Fabric](02_generation_value.png)

## Negative prices

Counts and shares refer to negative hourly exported price values. The local-hour chart divides each hour-of-day group by its own valid observations. The wind-and-solar exposure bars divide source generation in negative-price hours by that source's matched generation volume.

![Negative prices in Fabric](03_negative_prices.png)

The report currently requires workspace authentication. An unauthenticated public link and walkthrough video have not been created. The source design follows the author's [Global Critical Materials](https://github.com/anastasia-klein/global-critical-materials-intelligence) report, with an expanded palette for electricity-market analysis.

## Presentation update, 10 November 2026

The refreshed report uses a cool white background and rounded, lightly tinted navigation. The declared font stack is `'Avenir Next', Arial, sans-serif`; the intended Mac rendering was checked in the browser, while other operating systems and server-side exports can use a fallback. Technical architecture text was removed from the page footer; its evidence remains in source definitions and this directory.

A single selected month switches the timeline to days. Multiple selected months or the complete year retain monthly observations. The axis is a static 2025 presentation table; measures apply the corresponding local-date or month filter to the original hourly facts. None of the market data has been copied into the presentation tables.

![June daily detail in Fabric](04_daily_june.png)
