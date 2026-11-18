# Authentic Fabric execution exports

The four notebooks in [2026-11-18](2026-11-18/) were executed successfully in the existing Microsoft Fabric workspace and downloaded through Fabric's **Download as → Notebook only** command. These files retain real cell outputs and execution counts. They are not locally simulated Spark runs and are not the output-free portable source exports in `notebooks/`.

| Notebook | Executed code cells | Cells retaining output | Error outputs |
|---|---:|---:|---:|
| [01_profile_sources](2026-11-18/01_profile_sources.ipynb) | 2 | 2 | 0 |
| [02_build_silver](2026-11-18/02_build_silver.ipynb) | 7 | 7 | 0 |
| [03_explore_power_market](2026-11-18/03_explore_power_market.ipynb) | 15 | 15 | 0 |
| [04_build_gold](2026-11-18/04_build_gold.ipynb) | 7 | 7 | 0 |

The gold run confirms 8,760 time-dimension rows, one market, twelve generation sources, 8,760 market-hour facts and 105,120 generation-hour facts. Silver and gold were rebuilt using the existing validated 2025 public SMARD source files. Completed Spark sessions were stopped after the exports.

[output_inventory.json](output_inventory.json) records file hashes, execution counts and output/error coverage across the source notebooks and captured evidence. The `historical/` directory preserves the earlier combined `01_prepare_smard` notebook and its HTML export unchanged. Historical and independent local EDA evidence are not presented as current Fabric executions.

The additional [05_archive_onelake](2026-11-18/05_archive_onelake.ipynb) contains the successful physical-export run output for all nine silver/gold tables, the ZIP size and checksum. Its source is retained in [archive_onelake.py](../../scripts/archive_onelake.py). The downloaded [physical archive](../onelake/) was independently validated locally.

Fabric Git synchronization does not retain notebook cell outputs. These exports provide a separate execution archive; future source synchronization should not overwrite them. Notebook outputs alone do not constitute a physical backup of OneLake Delta table files or transaction logs; the separate physical archive now addresses that requirement.
