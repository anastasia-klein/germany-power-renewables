# Physical OneLake table archive

[Download the Delta and Parquet archive](2026-11-18/onelake_silver_gold_20261118T141027Z.zip) · [Independent validation](2026-11-18/validation.json) · [Executed Fabric export notebook](../fabric_runs/2026-11-18/05_archive_onelake.ipynb)

On 18 November 2026 the nine existing silver/gold tables were copied directly from `lh_power_renewables` in OneLake. This archive contains the actual Delta storage files and `_delta_log`, rather than a local reconstruction from source CSVs. It also retains current-version Parquet snapshots, Spark schemas, Delta history and a per-file SHA-256 manifest. Source versions were checked before and after each copy; source tables were not rewritten.

| Table | Rows | Columns | Delta version |
|---|---:|---:|---:|
| silver.consumption_hour | 8,760 | 8 | 3 |
| silver.dim_time_hour | 8,760 | 6 | 2 |
| silver.generation_hour | 105,120 | 6 | 3 |
| silver.price_hour | 8,760 | 5 | 3 |
| gold.dim_generation_source | 12 | 5 | 1 |
| gold.dim_market | 1 | 3 | 1 |
| gold.dim_time_hour | 8,760 | 13 | 2 |
| gold.fact_generation_hour | 105,120 | 9 | 1 |
| gold.fact_market_hour | 8,760 | 17 | 1 |

The downloaded ZIP is 15,862,740 bytes; SHA-256: `34b72e22c8df47fcbfbb6f428713d130ee83edd55905fab29ac78f4efc67c889`. All 2,530 inventoried payload files passed size/hash verification. All nine Delta tables were reopened locally through DuckDB's Delta Kernel, without Fabric credentials; every row and column matched the corresponding version-pinned Parquet snapshot. Deletion-vector support was enabled through the Delta reader. The archive also retains older available data/log files, but historical-version reads were not individually validated.

Fabric's auxiliary virtual Iceberg `metadata/` directory was excluded: OneLake listed an Avro object that returned HTTP 404. Every excluded path is recorded in the manifest. This exclusion does not remove the Delta log or active Delta data; successful independent Delta reads verified the current snapshots. Iceberg metadata portability, workspace permissions, SQL endpoint configuration and a full workspace restore are not claimed.

Only public SMARD-derived tables are included. No household consumption, Tibber credentials or authentication tokens are part of the archive. Data attribution: Bundesnetzagentur | [SMARD.de](https://www.smard.de/en), CC BY 4.0.
