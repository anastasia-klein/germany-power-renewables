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

# CELL ********************

path = (
    "Files/raw/smard/"
    "Actual_consumption_202501010000_202601010000_Hour.csv"
)

consumption_raw = (
    spark.read
    .option("header", True)
    .option("sep", ";")
    .option("inferSchema", False)
    .csv(path)
)

print("Rows:", consumption_raw.count())
print("Columns:", len(consumption_raw.columns))

display(consumption_raw.limit(5))


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

expected_columns = [
    "Start date",
    "End date",
    "grid load [MWh] Calculated resolutions",
    "Grid load incl. hydro pumped storage [MWh] Calculated resolutions",
    "Hydro pumped storage [MWh] Calculated resolutions",
    "Residual load [MWh] Calculated resolutions",
]

assert consumption_raw.columns == expected_columns, "Unexpected CSV columns"

consumption_staging = consumption_raw.toDF(
    "start_local_raw",
    "end_local_raw",
    "grid_load_mwh_raw",
    "grid_load_including_pumping_mwh_raw",
    "pumping_consumption_mwh_raw",
    "residual_load_mwh_raw",
)

display(consumption_staging.limit(5))

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

from pyspark.sql import functions as F

metric_columns = {
    "grid_load_mwh_raw": "grid_load_mwh",
    "grid_load_including_pumping_mwh_raw": "grid_load_including_pumping_mwh",
    "pumping_consumption_mwh_raw": "pumping_consumption_mwh",
    "residual_load_mwh_raw": "residual_load_mwh",
}

consumption_typed = consumption_staging

for source_column, target_column in metric_columns.items():
    cleaned_value = F.regexp_replace(
        F.trim(F.col(source_column)), ",", ""
    )

    consumption_typed = consumption_typed.withColumn(
        target_column,
        F.when(cleaned_value == "-", F.lit(None))
        .otherwise(cleaned_value)
        .cast("decimal(18,2)")
    )

consumption_typed.printSchema()

display(
    consumption_typed.select(
        "start_local_raw",
        "grid_load_mwh_raw",
        "grid_load_mwh",
        "residual_load_mwh",
    ).limit(5)
)

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

from decimal import Decimal

balance_error = F.abs(
    F.col("grid_load_including_pumping_mwh")
    - F.col("grid_load_mwh")
    - F.col("pumping_consumption_mwh")
)

checks = consumption_typed.agg(
    F.count("*").alias("row_count"),
    *[
        F.sum(
            F.when(F.col(column).isNull(), 1).otherwise(0)
        ).alias(f"{column}_null_count")
        for column in metric_columns.values()
    ],
    F.max(balance_error).alias("max_balance_error_mwh"),
).first().asDict()

for name, value in checks.items():
    print(f"{name}: {value}")

assert checks["row_count"] == 8760, "Unexpected row count"

for column in metric_columns.values():
    assert checks[f"{column}_null_count"] == 0, (
        f"Missing numeric values in {column}"
    )

assert checks["max_balance_error_mwh"] <= Decimal("0.02"), (
    "Consumption balance exceeds rounding tolerance"
)

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

spark.conf.set("spark.sql.session.timeZone", "UTC")

local_zone = ZoneInfo("Europe/Berlin")

period_start = datetime(2025, 1, 1, tzinfo=local_zone)
period_end = datetime(2026, 1, 1, tzinfo=local_zone)

current_utc = period_start.astimezone(timezone.utc)
end_utc = period_end.astimezone(timezone.utc)

time_rows = []

while current_utc < end_utc:
    local_time = current_utc.astimezone(local_zone)

    time_rows.append((
        int(current_utc.strftime("%Y%m%d%H")),
        current_utc.replace(tzinfo=None),
        local_time.date(),
        local_time.hour,
        int(local_time.utcoffset().total_seconds() / 60),
        local_time.fold,
    ))

    current_utc += timedelta(hours=1)

dim_time_hour = spark.createDataFrame(
    time_rows,
    schema="""
        time_key LONG,
        interval_start_utc TIMESTAMP,
        local_date DATE,
        local_hour INT,
        utc_offset_minutes INT,
        fold INT
    """,
)

print("Calendar rows:", dim_time_hour.count())

display(
    dim_time_hour
    .filter(
        (F.col("local_date") == F.lit("2025-10-26").cast("date"))
        & (F.col("local_hour") == 2)
    )
    .orderBy("time_key")
)

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

import csv

from pyspark.sql.types import StructType, StructField, LongType

file_path = f"/lakehouse/default/{path}"

with open(file_path, encoding="utf-8-sig", newline="") as file:
    reader = csv.reader(file, delimiter=";")
    source_headers = next(reader)
    source_rows = list(reader)

assert source_headers == expected_columns, "Unexpected CSV columns"
assert len(source_rows) == len(time_rows), "Unexpected interval count"

keyed_rows = []

for source_row_number, (source_row, time_row) in enumerate(
    zip(source_rows, time_rows),
    start=2,
):
    time_key, start_utc = time_row[:2]

    expected_local_start = (
        start_utc
        .replace(tzinfo=timezone.utc)
        .astimezone(local_zone)
        .replace(tzinfo=None)
    )

    actual_local_start = datetime.strptime(
        source_row[0], "%b %d, %Y %I:%M %p"
    )

    assert actual_local_start == expected_local_start, (
        f"Unexpected timestamp at CSV row {source_row_number}"
    )

    keyed_rows.append(
        tuple(source_row) + (time_key, source_row_number)
    )

keyed_schema = StructType(
    consumption_staging.schema.fields + [
        StructField("time_key", LongType(), False),
        StructField("source_row_number", LongType(), False),
    ]
)

consumption_keyed_raw = spark.createDataFrame(
    keyed_rows,
    schema=keyed_schema,
)

print("Rows:", consumption_keyed_raw.count())
print(
    "Unique time keys:",
    consumption_keyed_raw.select("time_key").distinct().count(),
)

display(
    consumption_keyed_raw
    .filter(F.col("time_key").isin(2025102600, 2025102601))
    .orderBy("time_key")
)

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

consumption_silver = consumption_keyed_raw

for source_column, target_column in metric_columns.items():
    cleaned_value = F.regexp_replace(
        F.trim(F.col(source_column)), ",", ""
    )

    consumption_silver = consumption_silver.withColumn(
        target_column,
        F.when(cleaned_value == "-", F.lit(None))
        .otherwise(cleaned_value)
        .cast("decimal(18,2)")
    )

consumption_silver = consumption_silver.select(
    "time_key",
    F.lit("DE").alias("country_code"),
    *metric_columns.values(),
    "source_row_number",
    F.lit(path).alias("source_file"),
)

validation = consumption_silver.agg(
    F.count("*").alias("row_count"),
    F.countDistinct("time_key").alias("unique_time_keys"),
    *[
        F.count(column).alias(f"{column}_valid_count")
        for column in metric_columns.values()
    ],
).first().asDict()

assert validation["row_count"] == 8760, "Unexpected row count"
assert validation["unique_time_keys"] == 8760, "Duplicate time keys"

for column in metric_columns.values():
    assert validation[f"{column}_valid_count"] == 8760, (
        f"Missing numeric values in {column}"
    )

spark.sql("CREATE SCHEMA IF NOT EXISTS silver")

consumption_silver.write \
    .format("delta") \
    .mode("overwrite") \
    .saveAsTable("silver.consumption_hour")

saved_consumption = spark.table("silver.consumption_hour")

print("Saved rows:", saved_consumption.count())
display(saved_consumption.orderBy("time_key").limit(5))

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

generation_path = (
    "Files/raw/smard/"
    "Actual_generation_202501010000_202601010000_Hour.csv"
)

generation_raw = (
    spark.read
    .option("header", True)
    .option("sep", ";")
    .option("inferSchema", False)
    .csv(generation_path)
)

print("Rows:", generation_raw.count())
print("Columns:", len(generation_raw.columns))

for column in generation_raw.columns:
    print(column)

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

generation_sources = {
    "biomass": "Biomass",
    "hydropower": "Hydropower",
    "wind_offshore": "Wind offshore",
    "wind_onshore": "Wind onshore",
    "solar": "Photovoltaics",
    "other_renewable": "Other renewable",
    "nuclear": "Nuclear",
    "lignite": "Lignite",
    "hard_coal": "Hard coal",
    "fossil_gas": "Fossil gas",
    "pumped_storage": "Hydro pumped storage",
    "other_conventional": "Other conventional",
}

expected_generation_columns = [
    "Start date",
    "End date",
    *[
        f"{label} [MWh] Calculated resolutions"
        for label in generation_sources.values()
    ],
]

with open(
    f"/lakehouse/default/{generation_path}",
    encoding="utf-8-sig",
    newline="",
) as file:
    reader = csv.reader(file, delimiter=";")
    generation_headers = next(reader)
    generation_rows = list(reader)

assert generation_headers == expected_generation_columns, (
    "Unexpected generation columns"
)
assert len(generation_rows) == len(time_rows), (
    "Unexpected generation interval count"
)

keyed_generation_rows = []

for row_number, (source_row, time_row) in enumerate(
    zip(generation_rows, time_rows),
    start=2,
):
    time_key, start_utc = time_row[:2]

    expected_local_start = (
        start_utc
        .replace(tzinfo=timezone.utc)
        .astimezone(local_zone)
        .replace(tzinfo=None)
    )

    actual_local_start = datetime.strptime(
        source_row[0], "%b %d, %Y %I:%M %p"
    )

    assert actual_local_start == expected_local_start, (
        f"Unexpected timestamp at CSV row {row_number}"
    )

    keyed_generation_rows.append(
        (time_key, row_number, *source_row[2:])
    )

generation_schema = (
    "time_key LONG, source_row_number LONG, "
    + ", ".join(
        f"{code} STRING"
        for code in generation_sources
    )
)

generation_wide = spark.createDataFrame(
    keyed_generation_rows,
    schema=generation_schema,
)

generation_long = (
    generation_wide
    .select(
        "time_key",
        "source_row_number",
        F.explode(
            F.array(*[
                F.struct(
                    F.lit(code).alias("generation_source_code"),
                    F.col(code).alias("generation_mwh_raw"),
                )
                for code in generation_sources
            ])
        ).alias("generation"),
    )
    .select(
        "time_key",
        F.lit("DE").alias("country_code"),
        "generation.*",
        "source_row_number",
        F.lit(generation_path).alias("source_file"),
    )
)

cleaned_generation = F.regexp_replace(
    F.trim(F.col("generation_mwh_raw")), ",", ""
)

generation_typed = generation_long.withColumn(
    "generation_mwh",
    F.when(cleaned_generation == "-", F.lit(None))
    .otherwise(cleaned_generation)
    .cast("decimal(18,2)"),
)

print("Rows:", generation_typed.count())

display(
    generation_typed
    .filter(F.col("time_key") == 2024123123)
    .orderBy("generation_source_code")
)

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

generation_quality = (
    generation_typed
    .groupBy("generation_source_code")
    .agg(
        F.count("*").alias("row_count"),
        F.count("generation_mwh").alias("numeric_count"),
        F.sum(
            F.when(
                F.trim(F.col("generation_mwh_raw")) == "-", 1
            ).otherwise(0)
        ).alias("missing_marker_count"),
    )
)

display(generation_quality.orderBy("generation_source_code"))

duplicate_keys = (
    generation_typed
    .groupBy("time_key", "country_code", "generation_source_code")
    .count()
    .filter(F.col("count") > 1)
)

assert duplicate_keys.limit(1).count() == 0, (
    "Duplicate generation keys"
)

quality_rows = generation_quality.collect()

assert len(quality_rows) == 12, "Unexpected generation source count"

for row in quality_rows:
    source = row["generation_source_code"]

    assert row["row_count"] == 8760, (
        f"Unexpected row count for {source}"
    )

    if source == "nuclear":
        assert row["missing_marker_count"] == 8760, (
            "Unexpected nuclear source coverage"
        )
        assert row["numeric_count"] == 0, (
            "Unexpected numeric nuclear values"
        )
    else:
        assert row["numeric_count"] == 8760, (
            f"Missing or invalid numeric values for {source}"
        )

generation_silver = generation_typed.select(
    "time_key",
    "country_code",
    "generation_source_code",
    "generation_mwh",
    "source_row_number",
    "source_file",
)

generation_silver.write \
    .format("delta") \
    .mode("overwrite") \
    .saveAsTable("silver.generation_hour")

print(
    "Saved rows:",
    spark.table("silver.generation_hour").count(),
)

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

price_path = (
    "Files/raw/smard/"
    "Day-ahead_prices_202501010000_202601010000_Hour.csv"
)

price_raw = (
    spark.read
    .option("header", True)
    .option("sep", ";")
    .option("inferSchema", False)
    .csv(price_path)
)

print("Rows:", price_raw.count())
print("Columns:", len(price_raw.columns))

for column in price_raw.columns:
    print(column)

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

price_column = (
    "Germany/Luxembourg [€/MWh] Calculated resolutions"
)

with open(
    f"/lakehouse/default/{price_path}",
    encoding="utf-8-sig",
    newline="",
) as file:
    reader = csv.DictReader(file, delimiter=";")

    assert reader.fieldnames == price_raw.columns, (
        "Unexpected price columns"
    )
    assert price_column in reader.fieldnames, (
        "Required DE-LU price column is missing"
    )

    price_rows = list(reader)

assert len(price_rows) == len(time_rows), (
    "Unexpected price interval count"
)

keyed_price_rows = []

for row_number, (source_row, time_row) in enumerate(
    zip(price_rows, time_rows),
    start=2,
):
    time_key, start_utc = time_row[:2]

    expected_local_start = (
        start_utc
        .replace(tzinfo=timezone.utc)
        .astimezone(local_zone)
        .replace(tzinfo=None)
    )

    actual_local_start = datetime.strptime(
        source_row["Start date"], "%b %d, %Y %I:%M %p"
    )

    assert actual_local_start == expected_local_start, (
        f"Unexpected timestamp at CSV row {row_number}"
    )

    keyed_price_rows.append((
        time_key,
        source_row[price_column],
        row_number,
    ))

price_keyed_raw = spark.createDataFrame(
    keyed_price_rows,
    schema="""
        time_key LONG,
        day_ahead_price_raw STRING,
        source_row_number LONG
    """,
)

cleaned_price = F.regexp_replace(
    F.trim(F.col("day_ahead_price_raw")), ",", ""
)

price_silver = (
    price_keyed_raw
    .withColumn(
        "day_ahead_price_eur_mwh",
        F.when(cleaned_price == "-", F.lit(None))
        .otherwise(cleaned_price)
        .cast("decimal(18,2)"),
    )
    .select(
        "time_key",
        F.lit("DE-LU").alias("bidding_zone_code"),
        "day_ahead_price_eur_mwh",
        "source_row_number",
        F.lit(price_path).alias("source_file"),
    )
)

price_validation = price_silver.agg(
    F.count("*").alias("row_count"),
    F.countDistinct("time_key").alias("unique_time_keys"),
    F.count("day_ahead_price_eur_mwh").alias("numeric_count"),
    F.min("day_ahead_price_eur_mwh").alias("min_price"),
    F.max("day_ahead_price_eur_mwh").alias("max_price"),
).first().asDict()

for name, value in price_validation.items():
    print(f"{name}: {value}")

assert price_validation["row_count"] == 8760, (
    "Unexpected price row count"
)
assert price_validation["unique_time_keys"] == 8760, (
    "Duplicate price time keys"
)
assert price_validation["numeric_count"] == 8760, (
    "Missing or invalid price values"
)

price_silver.write \
    .format("delta") \
    .mode("overwrite") \
    .saveAsTable("silver.price_hour")

print(
    "Saved rows:",
    spark.table("silver.price_hour").count(),
)

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

cross_source_checks = spark.sql("""
    WITH wind_solar AS (
        SELECT
            time_key,
            country_code,
            SUM(generation_mwh) AS wind_solar_mwh
        FROM silver.generation_hour
        WHERE generation_source_code IN (
            'wind_offshore',
            'wind_onshore',
            'solar'
        )
        GROUP BY time_key, country_code
    )
    SELECT
        COUNT(*) AS row_count,
        COUNT(p.time_key) AS matched_price_hours,
        COUNT(g.time_key) AS matched_generation_hours,
        MAX(
            ABS(
                c.grid_load_mwh
                - g.wind_solar_mwh
                - c.residual_load_mwh
            )
        ) AS max_residual_error_mwh
    FROM silver.consumption_hour AS c
    LEFT JOIN silver.price_hour AS p
        ON c.time_key = p.time_key
        AND p.bidding_zone_code = 'DE-LU'
    LEFT JOIN wind_solar AS g
        ON c.time_key = g.time_key
        AND c.country_code = g.country_code
    WHERE c.country_code = 'DE'
""")

display(cross_source_checks)

result = cross_source_checks.first().asDict()

assert result["row_count"] == 8760, (
    "Unexpected joined row count"
)
assert result["matched_price_hours"] == 8760, (
    "Missing matching price hours"
)
assert result["matched_generation_hours"] == 8760, (
    "Missing matching generation hours"
)
assert result["max_residual_error_mwh"] <= Decimal("0.03"), (
    "Residual load reconciliation exceeds rounding tolerance"
)

print("Cross-source checks passed")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

spark.sql("CREATE SCHEMA IF NOT EXISTS gold")

dim_time_hour.write \
    .format("delta") \
    .mode("overwrite") \
    .saveAsTable("gold.dim_time_hour")

print(
    "Calendar rows:",
    spark.table("gold.dim_time_hour").count(),
)

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

spark.table("gold.dim_time_hour").createOrReplaceTempView("time_hour")

monthly_price_profile = spark.sql("""
    SELECT
        DATE_FORMAT(t.local_date, 'yyyy-MM') AS month,
        COUNT(*) AS matched_hours,
        ROUND(SUM(c.grid_load_mwh) / 1000000, 3)
            AS consumption_twh,
        ROUND(AVG(p.day_ahead_price_eur_mwh), 2)
            AS average_price_eur_mwh,
        ROUND(
            SUM(
                p.day_ahead_price_eur_mwh * c.grid_load_mwh
            ) / SUM(c.grid_load_mwh),
            2
        ) AS load_weighted_price_eur_mwh
    FROM silver.consumption_hour AS c
    INNER JOIN silver.price_hour AS p
        ON c.time_key = p.time_key
    INNER JOIN time_hour AS t
        ON c.time_key = t.time_key
    WHERE c.country_code = 'DE'
        AND p.bidding_zone_code = 'DE-LU'
    GROUP BY DATE_FORMAT(t.local_date, 'yyyy-MM')
    ORDER BY month
""")

display(monthly_price_profile)


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

import matplotlib.pyplot as plt

monthly = monthly_price_profile.orderBy("month").toPandas()

price_columns = [
    "average_price_eur_mwh",
    "load_weighted_price_eur_mwh",
]

for column in price_columns:
    monthly[column] = monthly[column].astype(float)

monthly["price_gap_eur_mwh"] = (
    monthly["load_weighted_price_eur_mwh"]
    - monthly["average_price_eur_mwh"]
)

fig, axes = plt.subplots(
    2, 1,
    figsize=(12, 8),
    sharex=True,
    constrained_layout=True,
)

axes[0].plot(
    monthly["month"],
    monthly["average_price_eur_mwh"],
    marker="o",
    label="Time-average price",
    color="#2563EB",
)

axes[0].plot(
    monthly["month"],
    monthly["load_weighted_price_eur_mwh"],
    marker="o",
    label="Load-weighted price",
    color="#D97706",
)

axes[0].set_title("Germany: monthly day-ahead prices, 2025")
axes[0].set_ylabel("EUR/MWh")
axes[0].legend(frameon=False)
axes[0].grid(axis="y", alpha=0.25)

axes[1].bar(
    monthly["month"],
    monthly["price_gap_eur_mwh"],
    color="#64748B",
)

axes[1].axhline(0, color="#111827", linewidth=0.8)
axes[1].set_title("Load-weighted price minus time-average price")
axes[1].set_ylabel("EUR/MWh")
axes[1].set_xlabel("Month")
axes[1].grid(axis="y", alpha=0.25)
axes[1].tick_params(axis="x", rotation=45)

plt.show()

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
