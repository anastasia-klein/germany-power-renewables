# Fabric notebook source

# METADATA ********************

# META {
# META   "kernel_info": {
# META     "name": "synapse_pyspark"
# META   },
# META   "dependencies": {
# META     "lakehouse": {
# META       "default_lakehouse": "a5d1c663-d58f-4d6e-bccd-4251c72c3357",
# META       "default_lakehouse_name": "lh_power_renewables",
# META       "default_lakehouse_workspace_id": "af058716-784e-466d-b01b-06f7413c9fdb",
# META       "known_lakehouses": [
# META         {
# META           "id": "a5d1c663-d58f-4d6e-bccd-4251c72c3357"
# META         }
# META       ]
# META     }
# META   }
# META }

# MARKDOWN ********************

# # 04 — Build the 2025 reporting model

# Publish three dimensions and two hourly Delta facts from persisted silver data. The model pairs German grid load and generation with the DE-LU day-ahead price. All twelve generation categories are retained; unavailable nuclear observations stay null.

# Hourly price-volume components support period-specific load-weighted and generation-weighted prices. They describe market-price exposure rather than billed costs, realized revenue or profit. Ratios remain reporting measures; monthly averages are not materialized.

# Input validation, UTC coverage, key checks and EDA reconciliation precede publication. A successful rerun replaces the same five 2025 tables without appending duplicates. Each Delta write is atomic individually; the five writes are not a single transaction. The reporting calendar's existing schema is expanded in this release.

# MARKDOWN ********************

# ## Configuration and validation helpers

# CELL ********************

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

from pyspark.sql import functions as F

spark.conf.set("spark.sql.session.timeZone", "UTC")
YEAR = 2025
EXPECTED_HOURS = 8760
MARKET_KEY = "DE_DE-LU"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def require_grain(frame, keys, expected_rows, name):
    require(frame.count() == expected_rows, f"Unexpected row count: {name}")
    require(frame.select(*keys).distinct().count() == expected_rows, f"Duplicate keys: {name}")
    null_key = F.lit(False)
    for key in keys:
        null_key = null_key | F.col(key).isNull()
    require(frame.filter(null_key).limit(1).count() == 0, f"Null key: {name}")


def require_decimal(frame, columns, name):
    for column in columns:
        require(frame.schema[column].dataType.simpleString() == "decimal(18,2)", f"Unexpected decimal type: {name}.{column}")


source_rows = [
    ("biomass", "Biomass", "biomass", True, False),
    ("hydropower", "Hydropower", "hydropower", True, False),
    ("wind_offshore", "Wind offshore", "wind", True, False),
    ("wind_onshore", "Wind onshore", "wind", True, False),
    ("solar", "Photovoltaics", "solar", True, False),
    ("other_renewable", "Other renewable", "other_renewable", True, False),
    ("nuclear", "Nuclear", "nuclear", False, False),
    ("lignite", "Lignite", "fossil", False, False),
    ("hard_coal", "Hard coal", "fossil", False, False),
    ("fossil_gas", "Fossil gas", "fossil", False, False),
    ("pumped_storage", "Hydro pumped storage", "storage", False, True),
    ("other_conventional", "Other conventional", "other_conventional", False, False),
]

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ## Silver input contract

# CELL ********************

calendar = spark.table("silver.dim_time_hour").select(
    "time_key", "interval_start_utc", "local_date", "local_hour", "utc_offset_minutes", "fold"
)
consumption = spark.table("silver.consumption_hour").filter(F.col("country_code") == "DE")
price = spark.table("silver.price_hour").filter(F.col("bidding_zone_code") == "DE-LU")
generation = spark.table("silver.generation_hour").filter(F.col("country_code") == "DE")

consumption_columns = ["grid_load_mwh", "grid_load_including_pumping_mwh", "pumping_consumption_mwh", "residual_load_mwh"]
require_decimal(consumption, consumption_columns, "consumption")
require_decimal(price, ["day_ahead_price_eur_mwh"], "price")
require_decimal(generation, ["generation_mwh"], "generation")
require_grain(calendar, ["time_key"], EXPECTED_HOURS, "calendar")
require_grain(consumption, ["time_key", "country_code"], EXPECTED_HOURS, "consumption")
require_grain(price, ["time_key", "bidding_zone_code"], EXPECTED_HOURS, "price")
require_grain(generation, ["time_key", "country_code", "generation_source_code"], EXPECTED_HOURS * 12, "generation")

for name, frame in [("consumption", consumption), ("price", price), ("generation", generation)]:
    require(frame.select("time_key").distinct().count() == EXPECTED_HOURS, f"Unexpected time-key coverage: {name}")
    require(frame.join(calendar.select("time_key"), "time_key", "left_anti").limit(1).count() == 0, f"Unknown time key: {name}")

for column in consumption_columns:
    require(consumption.filter(F.col(column).isNull()).limit(1).count() == 0, f"Missing consumption input: {column}")
require(consumption.filter(F.col("grid_load_mwh") <= 0).limit(1).count() == 0, "Non-positive grid load")
require(price.filter(F.col("day_ahead_price_eur_mwh").isNull()).limit(1).count() == 0, "Missing price")
require(generation.filter(F.col("generation_mwh") < 0).limit(1).count() == 0, "Negative generation volume")

coverage = generation.groupBy("generation_source_code").agg(
    F.count("*").alias("hours"), F.count("generation_mwh").alias("valid_hours")
).collect()
require({row.generation_source_code for row in coverage} == {row[0] for row in source_rows}, "Unexpected generation categories")
for row in coverage:
    expected_valid = 0 if row.generation_source_code == "nuclear" else EXPECTED_HOURS
    require(row.hours == EXPECTED_HOURS and row.valid_hours == expected_valid, f"Unexpected source coverage: {row.generation_source_code}")

balance_error = consumption.agg(F.max(F.abs(
    F.col("grid_load_including_pumping_mwh") - F.col("grid_load_mwh") - F.col("pumping_consumption_mwh")
)).alias("error")).first().error
require(balance_error <= Decimal("0.02"), "Pumping balance exceeds rounding tolerance")

consumption.createOrReplaceTempView("gold_input_consumption")
price.createOrReplaceTempView("gold_input_price")
generation.createOrReplaceTempView("gold_input_generation")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ## Shared dimensions

# CELL ********************

local_zone = ZoneInfo("Europe/Berlin")
current = datetime(YEAR, 1, 1, tzinfo=local_zone).astimezone(timezone.utc)
finish = datetime(YEAR + 1, 1, 1, tzinfo=local_zone).astimezone(timezone.utc)
time_rows = []
while current < finish:
    local = current.astimezone(local_zone)
    time_rows.append((
        int(current.strftime("%Y%m%d%H")), current.replace(tzinfo=None),
        local.date(), local.hour, int(local.utcoffset().total_seconds() / 60), local.fold,
        (current + timedelta(hours=1)).replace(tzinfo=None), 60,
        local.year, local.month, local.isoweekday(), local.weekday() >= 5,
        15 if local.date() >= date(2025, 10, 1) else 60,
    ))
    current += timedelta(hours=1)
require(len(time_rows) == EXPECTED_HOURS, "Unexpected physical calendar length")
require({tuple(row) for row in calendar.collect()} == {row[:6] for row in time_rows}, "Silver calendar does not match the complete 2025 UTC/local timeline")

dim_time_hour = spark.createDataFrame(time_rows, schema="""
    time_key LONG, interval_start_utc TIMESTAMP, local_date DATE, local_hour INT,
    utc_offset_minutes INT, fold INT, interval_end_utc TIMESTAMP,
    duration_minutes INT, year INT, month INT, day_of_week INT,
    is_weekend BOOLEAN, market_product_resolution_minutes INT
""")
dim_market = spark.createDataFrame([(MARKET_KEY, "DE", "DE-LU")], schema="market_key STRING, country_code STRING, bidding_zone_code STRING")
dim_generation_source = spark.createDataFrame(source_rows, schema="""
    generation_source_code STRING, generation_source_name STRING,
    source_group STRING, is_renewable BOOLEAN, is_storage_output BOOLEAN
""")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ## Hourly market fact

# CELL ********************

market_sql = """
WITH variable_generation AS (
    SELECT time_key, country_code,
        CAST(SUM(CASE WHEN generation_source_code IN ('wind_onshore', 'wind_offshore') THEN generation_mwh END) AS DECIMAL(18,2)) AS wind_mwh,
        CAST(SUM(CASE WHEN generation_source_code = 'solar' THEN generation_mwh END) AS DECIMAL(18,2)) AS solar_mwh
    FROM gold_input_generation
    GROUP BY time_key, country_code
), hourly AS (
    SELECT c.time_key, 'DE_DE-LU' AS market_key,
        p.day_ahead_price_eur_mwh,
        c.grid_load_mwh, c.grid_load_including_pumping_mwh,
        c.pumping_consumption_mwh, c.residual_load_mwh,
        g.wind_mwh, g.solar_mwh,
        CAST(g.wind_mwh + g.solar_mwh AS DECIMAL(18,2)) AS wind_solar_mwh
    FROM gold_input_consumption c
    INNER JOIN gold_input_price p ON c.time_key = p.time_key AND p.bidding_zone_code = 'DE-LU'
    INNER JOIN variable_generation g ON c.time_key = g.time_key AND c.country_code = g.country_code
    WHERE c.country_code = 'DE'
)
SELECT *,
    CASE WHEN grid_load_mwh > 0
        THEN CAST(wind_solar_mwh AS DOUBLE) / CAST(grid_load_mwh AS DOUBLE)
        ELSE CAST(NULL AS DOUBLE) END AS wind_solar_load_ratio,
    CASE WHEN day_ahead_price_eur_mwh IS NOT NULL AND grid_load_mwh IS NOT NULL
        THEN CAST(day_ahead_price_eur_mwh * grid_load_mwh AS DECIMAL(38,4))
        ELSE CAST(NULL AS DECIMAL(38,4)) END AS price_weighted_load_eur,
    CASE WHEN day_ahead_price_eur_mwh IS NOT NULL AND grid_load_mwh IS NOT NULL
        THEN grid_load_mwh ELSE CAST(NULL AS DECIMAL(18,2)) END AS matched_grid_load_mwh,
    day_ahead_price_eur_mwh < 0 AS is_negative_price,
    day_ahead_price_eur_mwh = 0 AS is_zero_price,
    day_ahead_price_eur_mwh IS NOT NULL AS is_valid_price,
    day_ahead_price_eur_mwh IS NOT NULL AND grid_load_mwh IS NOT NULL AS is_valid_load_price
FROM hourly
"""
fact_market_hour = spark.sql(market_sql)

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ## Hourly generation-source fact

# CELL ********************

generation_sql = """
SELECT g.time_key, 'DE_DE-LU' AS market_key,
    g.generation_source_code, g.generation_mwh,
    CASE WHEN g.generation_mwh IS NOT NULL AND p.day_ahead_price_eur_mwh IS NOT NULL
        THEN CAST(g.generation_mwh * p.day_ahead_price_eur_mwh AS DECIMAL(38,4))
        ELSE CAST(NULL AS DECIMAL(38,4)) END AS price_weighted_generation_eur,
    CASE WHEN g.generation_mwh IS NOT NULL AND p.day_ahead_price_eur_mwh IS NOT NULL
        THEN g.generation_mwh ELSE CAST(NULL AS DECIMAL(18,2)) END AS matched_generation_mwh,
    CASE WHEN g.generation_mwh IS NULL OR p.day_ahead_price_eur_mwh IS NULL
        THEN CAST(NULL AS DECIMAL(18,2))
        WHEN p.day_ahead_price_eur_mwh < 0 THEN g.generation_mwh
        ELSE CAST(0 AS DECIMAL(18,2)) END AS negative_price_generation_mwh,
    g.generation_mwh IS NOT NULL AS is_valid_generation,
    g.generation_mwh IS NOT NULL AND p.day_ahead_price_eur_mwh IS NOT NULL AS is_valid_generation_price
FROM gold_input_generation g
INNER JOIN gold_input_price p ON g.time_key = p.time_key AND p.bidding_zone_code = 'DE-LU'
WHERE g.country_code = 'DE'
"""
fact_generation_hour = spark.sql(generation_sql)

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ## Reporting-contract checks before publication

# CELL ********************

gold_tables = {
    "gold.dim_time_hour": (dim_time_hour, ["time_key"], EXPECTED_HOURS),
    "gold.dim_market": (dim_market, ["market_key"], 1),
    "gold.dim_generation_source": (dim_generation_source, ["generation_source_code"], 12),
    "gold.fact_market_hour": (fact_market_hour, ["time_key", "market_key"], EXPECTED_HOURS),
    "gold.fact_generation_hour": (fact_generation_hour, ["time_key", "market_key", "generation_source_code"], EXPECTED_HOURS * 12),
}
for name, (frame, keys, count) in gold_tables.items():
    frame.cache()
    require_grain(frame, keys, count, name)

for name, fact in [("market", fact_market_hour), ("generation", fact_generation_hour)]:
    require(fact.join(dim_time_hour.select("time_key"), "time_key", "left_anti").limit(1).count() == 0, f"Missing time dimension: {name}")
    require(fact.join(dim_market, "market_key", "left_anti").limit(1).count() == 0, f"Missing market dimension: {name}")
require(fact_generation_hour.join(dim_generation_source, "generation_source_code", "left_anti").limit(1).count() == 0, "Missing source dimension")

market_nonnull_columns = ["day_ahead_price_eur_mwh", *consumption_columns, "wind_mwh", "solar_mwh", "wind_solar_mwh", "wind_solar_load_ratio", "price_weighted_load_eur", "matched_grid_load_mwh"]
for column in market_nonnull_columns:
    require(fact_market_hour.filter(F.col(column).isNull()).limit(1).count() == 0, f"Missing market-fact value: {column}")
require(fact_market_hour.filter(~F.col("is_valid_price") | ~F.col("is_valid_load_price")).limit(1).count() == 0, "Invalid market matched coverage")
residual_error = fact_market_hour.agg(F.max(F.abs(
    F.col("grid_load_mwh") - F.col("wind_solar_mwh") - F.col("residual_load_mwh")
)).alias("error")).first().error
require(residual_error <= Decimal("0.03"), "Residual load reconciliation failed")

generation_components = ["generation_mwh", "price_weighted_generation_eur", "matched_generation_mwh", "negative_price_generation_mwh"]
for column in generation_components:
    missing = fact_generation_hour.filter(F.col(column).isNull())
    require(missing.count() == EXPECTED_HOURS and missing.filter(F.col("generation_source_code") != "nuclear").limit(1).count() == 0, f"Unexpected component nulls: {column}")
require(fact_generation_hour.filter((F.col("generation_source_code") == "nuclear") & (F.col("is_valid_generation") | F.col("is_valid_generation_price"))).limit(1).count() == 0, "Unavailable nuclear marked valid")
require(fact_generation_hour.filter((F.col("generation_source_code") != "nuclear") & (~F.col("is_valid_generation") | ~F.col("is_valid_generation_price"))).limit(1).count() == 0, "Observed generation marked invalid")

fact_market_hour.createOrReplaceTempView("gold_prepared_market")
fact_generation_hour.createOrReplaceTempView("gold_prepared_generation")
market_metric_sql = """
SELECT COUNT(*) AS matched_hours,
    AVG(day_ahead_price_eur_mwh) AS average_price_eur_mwh,
    SUM(price_weighted_load_eur) / SUM(matched_grid_load_mwh) AS load_weighted_price_eur_mwh,
    SUM(CASE WHEN is_negative_price THEN 1 ELSE 0 END) AS negative_price_hours,
    SUM(CASE WHEN is_zero_price THEN 1 ELSE 0 END) AS zero_price_hours
FROM gold_prepared_market
"""
market_check = spark.sql(market_metric_sql).first().asDict()
require(market_check["matched_hours"] == EXPECTED_HOURS, "Incomplete market metric coverage")
require(abs(Decimal(str(market_check["average_price_eur_mwh"])) - Decimal("89.32")) < Decimal("0.005"), "Market mean differs from the captured 2025 EDA snapshot")
require(abs(Decimal(str(market_check["load_weighted_price_eur_mwh"])) - Decimal("92.42")) < Decimal("0.005"), "Load-weighted price differs from EDA")
require(market_check["negative_price_hours"] == 573 and market_check["zero_price_hours"] == 82, "Price-sign counts differ from EDA")

capture_metric_sql = """
SELECT generation_source_code,
    SUM(price_weighted_generation_eur) / SUM(matched_generation_mwh) AS capture_price_eur_mwh,
    SUM(negative_price_generation_mwh) / SUM(matched_generation_mwh) AS negative_price_generation_share
FROM gold_prepared_generation
GROUP BY generation_source_code
"""
capture_checks = {row.generation_source_code: row.asDict() for row in spark.sql(capture_metric_sql).collect()}
for source, expected in {"wind_onshore": "77.31", "wind_offshore": "85.53", "solar": "46.07"}.items():
    require(abs(Decimal(str(capture_checks[source]["capture_price_eur_mwh"])) - Decimal(expected)) < Decimal("0.005"), f"Capture price differs from EDA: {source}")
require(capture_checks["nuclear"]["capture_price_eur_mwh"] is None, "Nuclear capture price must remain unavailable")
require(abs(Decimal(str(capture_checks["solar"]["negative_price_generation_share"])) - Decimal("0.2413")) < Decimal("0.00005"), "Solar negative-price exposure differs from EDA")
print("Gold input, grain, relationship and EDA checks passed")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ## Publish the validated 2025 Delta tables

# CELL ********************

try:
    spark.sql("CREATE SCHEMA IF NOT EXISTS gold")
    for name, (frame, keys, expected_rows) in gold_tables.items():
        frame.write.format("delta").mode("overwrite").option("overwriteSchema", "true").saveAsTable(name)
        saved = spark.table(name)
        require_grain(saved, keys, expected_rows, name)
        require(saved.schema.simpleString() == frame.schema.simpleString(), f"Saved schema mismatch: {name}")
        print(f"Saved {name}: {expected_rows} rows")
    print("Gold publication completed: five validated 2025 tables")
finally:
    for frame, _, _ in gold_tables.values():
        frame.unpersist()

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
