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

# # 02 — Build silver
#
# Deterministic transformation of the complete 2025 SMARD exports into four Delta tables: `silver.consumption_hour`, `silver.generation_hour`, `silver.price_hour` and `silver.dim_time_hour`.
#
# The build validates raw structure, numeric precision, chronological coverage, business keys and energy reconciliation before publishing any table. Ordered CSV records distinguish the repeated autumn hour; incomplete or reordered inputs are rejected. Missing nuclear generation remains null, and negative prices are retained.
#
# Every code cell belongs to the build. There are no exploratory previews or analytical outputs. Each table is fully replaced on a successful rerun; publication across the four tables is not a single transaction. The driver-based CSV reader is appropriate for these small annual source files.

# MARKDOWN ********************

# ## Input contract

# CELL ********************

import csv
import hashlib
from collections import Counter
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from zoneinfo import ZoneInfo


def profile_sources(raw_root, year):
    """Validate complete, ordered hourly exports; partial or reordered files fail."""
    zone = ZoneInfo("Europe/Berlin")
    cursor = datetime(year, 1, 1, tzinfo=zone).astimezone(timezone.utc)
    finish = datetime(year + 1, 1, 1, tzinfo=zone).astimezone(timezone.utc)
    expected = []
    while cursor < finish:
        expected.append(cursor.astimezone(zone).replace(tzinfo=None))
        cursor += timedelta(hours=1)

    reports = []
    for category in ("Actual_consumption", "Actual_generation", "Day-ahead_prices"):
        filename = f"{category}_{year}01010000_{year + 1}01010000_Hour.csv"
        path = raw_root / filename
        with path.open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.reader(handle, delimiter=";")
            headers = next(reader)
            rows = list(reader)
        assert len(headers) == len(set(headers)), f"Duplicate headers in {filename}"
        assert headers[:2] == ["Start date", "End date"], f"Unexpected time headers in {filename}"
        assert all(len(row) == len(headers) for row in rows), f"Invalid CSV width in {filename}"
        starts = [datetime.strptime(row[0], "%b %d, %Y %I:%M %p") for row in rows]
        assert starts == expected, f"Unexpected time sequence in {filename}"
        assert all(
            datetime.strptime(row[1], "%b %d, %Y %I:%M %p") == start + timedelta(hours=1)
            for row, start in zip(rows, starts)
        ), f"Unexpected end labels in {filename}"
        metrics = []
        for column_index, header in enumerate(headers[2:], start=2):
            numeric = 0
            missing = 0
            for row in rows:
                value = row[column_index].strip()
                if value == "-":
                    missing += 1
                    continue
                try:
                    number = Decimal(value.replace(",", ""))
                except InvalidOperation as error:
                    raise ValueError(f"Invalid numeric value in {filename}: {header}") from error
                assert number.is_finite(), f"Non-finite value in {filename}: {header}"
                assert number == number.quantize(Decimal("0.01")), f"Unexpected precision: {header}"
                assert abs(number) < Decimal("1e16"), f"DECIMAL(18,2) overflow: {header}"
                numeric += 1
            metrics.append({"column": header, "numeric_count": numeric,
                            "missing_marker_count": missing})
        reports.append({"file": filename, "row_count": len(rows),
                        "column_count": len(headers), "timeline_verified": True,
                        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                        "metrics": metrics})
    day_counts = Counter(value.date().isoformat() for value in expected)
    return {"year": year, "expected_hours": len(expected), "sources": reports,
            "non_24_hour_days": {day: count for day, count in day_counts.items() if count != 24}}

from pyspark.sql import functions as F
from pyspark.sql.types import StructType, StructField, LongType, StringType

spark.conf.set("spark.sql.session.timeZone", "UTC")
profile = profile_sources(Path("/lakehouse/default/Files/raw/smard"), 2025)
expected_hours = profile["expected_hours"]

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ## UTC calendar

# CELL ********************

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

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ## Consumption transformation and validation

# CELL ********************

path = "Files/raw/smard/Actual_consumption_202501010000_202601010000_Hour.csv"
raw_column_names = [
    "start_local_raw", "end_local_raw", "grid_load_mwh_raw",
    "grid_load_including_pumping_mwh_raw", "pumping_consumption_mwh_raw",
    "residual_load_mwh_raw",
]

expected_columns = [
    "Start date",
    "End date",
    "grid load [MWh] Calculated resolutions",
    "Grid load incl. hydro pumped storage [MWh] Calculated resolutions",
    "Hydro pumped storage [MWh] Calculated resolutions",
    "Residual load [MWh] Calculated resolutions",
]


metric_columns = {
    "grid_load_mwh_raw": "grid_load_mwh",
    "grid_load_including_pumping_mwh_raw": "grid_load_including_pumping_mwh",
    "pumping_consumption_mwh_raw": "pumping_consumption_mwh",
    "residual_load_mwh_raw": "residual_load_mwh",
}


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
    [StructField(name, StringType(), True) for name in raw_column_names] + [
        StructField("time_key", LongType(), False),
        StructField("source_row_number", LongType(), False),
    ]
)

consumption_keyed_raw = spark.createDataFrame(
    keyed_rows,
    schema=keyed_schema,
)

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

assert validation["row_count"] == expected_hours, "Unexpected row count"
assert validation["unique_time_keys"] == expected_hours, "Duplicate time keys"

for column in metric_columns.values():
    assert validation[f"{column}_valid_count"] == expected_hours, (
        f"Missing numeric values in {column}"
    )

balance_error = F.abs(
    F.col("grid_load_including_pumping_mwh")
    - F.col("grid_load_mwh")
    - F.col("pumping_consumption_mwh")
)

checks = consumption_silver.agg(
    F.count("*").alias("row_count"),
    *[
        F.sum(
            F.when(F.col(column).isNull(), 1).otherwise(0)
        ).alias(f"{column}_null_count")
        for column in metric_columns.values()
    ],
    F.max(balance_error).alias("max_balance_error_mwh"),
).first().asDict()


assert checks["row_count"] == expected_hours, "Unexpected row count"

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

# MARKDOWN ********************

# ## Generation transformation and validation

# CELL ********************

generation_path = "Files/raw/smard/Actual_generation_202501010000_202601010000_Hour.csv"

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

    assert row["row_count"] == expected_hours, (
        f"Unexpected row count for {source}"
    )

    if source == "nuclear":
        assert row["missing_marker_count"] == expected_hours, (
            "Unexpected nuclear source coverage"
        )
        assert row["numeric_count"] == 0, (
            "Unexpected numeric nuclear values"
        )
    else:
        assert row["numeric_count"] == expected_hours, (
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

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ## Day-ahead price transformation and validation

# CELL ********************

price_path = "Files/raw/smard/Day-ahead_prices_202501010000_202601010000_Hour.csv"

price_column = (
    "Germany/Luxembourg [€/MWh] Calculated resolutions"
)

with open(
    f"/lakehouse/default/{price_path}",
    encoding="utf-8-sig",
    newline="",
) as file:
    reader = csv.DictReader(file, delimiter=";")

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
).first().asDict()


assert price_validation["row_count"] == expected_hours, (
    "Unexpected price row count"
)
assert price_validation["unique_time_keys"] == expected_hours, (
    "Duplicate price time keys"
)
assert price_validation["numeric_count"] == expected_hours, (
    "Missing or invalid price values"
)

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ## Cross-source quality gate

# CELL ********************

consumption_silver.createOrReplaceTempView("check_consumption_hour")
generation_silver.createOrReplaceTempView("check_generation_hour")
price_silver.createOrReplaceTempView("check_price_hour")
cross_source_checks = spark.sql("""
    WITH wind_solar AS (
        SELECT
            time_key,
            country_code,
            SUM(generation_mwh) AS wind_solar_mwh
        FROM check_generation_hour
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
    FROM check_consumption_hour AS c
    LEFT JOIN check_price_hour AS p
        ON c.time_key = p.time_key
        AND p.bidding_zone_code = 'DE-LU'
    LEFT JOIN wind_solar AS g
        ON c.time_key = g.time_key
        AND c.country_code = g.country_code
    WHERE c.country_code = 'DE'
""")


result = cross_source_checks.first().asDict()

assert result["row_count"] == expected_hours, (
    "Unexpected joined row count"
)
assert result["matched_price_hours"] == expected_hours, (
    "Missing matching price hours"
)
assert result["matched_generation_hours"] == expected_hours, (
    "Missing matching generation hours"
)
assert result["max_residual_error_mwh"] <= Decimal("0.03"), (
    "Residual load reconciliation exceeds rounding tolerance"
)

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ## Publish silver Delta tables

# CELL ********************

spark.sql("CREATE SCHEMA IF NOT EXISTS silver")

silver_tables = {
    "silver.consumption_hour": consumption_silver,
    "silver.generation_hour": generation_silver,
    "silver.price_hour": price_silver,
    "silver.dim_time_hour": dim_time_hour,
}

for table_name, dataframe in silver_tables.items():
    dataframe.write.format("delta").mode("overwrite").saveAsTable(table_name)
    saved = spark.table(table_name)
    assert saved.schema == dataframe.schema or (
        saved.schema.simpleString() == dataframe.schema.simpleString()
    ), f"Unexpected saved schema: {table_name}"
    assert saved.count() == dataframe.count(), f"Unexpected saved row count: {table_name}"
    print(f"Saved {table_name}: {saved.count()} rows")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
