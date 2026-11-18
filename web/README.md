# Public web report

Five interactive pages reproduce the current Fabric report's design and analytical behaviour using HTML, CSS, JavaScript and browser-native SVG. The site uses no third-party JavaScript CDN, analytics tracker, runtime server or API key. GitHub Pages receives only the `web/` directory.

Page order: Market overview → Generation & value → Hourly profiles → Supply & demand → Negative prices.

## Analytical contract

The versioned 2025 snapshot contains 8,760 unique UTC physical hours, local calendar attributes and twelve generation-source slots. It is derived from the original validated SMARD CSV files by `scripts/build_web_data.py`, with source hashes embedded. It is not presented as a direct export of the Fabric lakehouse.

Month filters are independent per page and support multiple selections. One selected month switches timeline charts to daily observations; all other selections use monthly observations. The generation selector changes source cards and charts; the source-comparison table retains all sources for the selected months. The URL fragment preserves the current selection.

All means, weighted prices, inclusive percentiles, correlations and ratios are recalculated from hourly observations. Nuclear remains unavailable, not zero. Capture measures require complete source-price coverage, and capture rate is unavailable for a non-positive benchmark. Grid load excludes pumping consumption. DST repeats keep distinct UTC timestamps.

Hourly power panels stack Solar, Wind and Residual load, with a Grid load line on the same scale. Negative residual load extends below zero. The positive stack can exceed the net line when residual load is negative. Price profiles use monotone smooth interpolation, circular markers, dashed P10/P90 boundaries and a translucent band between them. Scatter plots retain all selected matched points; native SVG titles and keyboard-focusable profile markers expose values.

## Verification

The dependency-free JavaScript tests reconcile Fabric headline controls, June filters, source values, correlations, heatmap DST counts and all 624 independently calculated hourly-profile groups. Browser checks cover page navigation, month and source filters, chart rendering and responsive layout. Original Fabric evidence remains under `evidence/` and is distinguished from independently computed web results.
