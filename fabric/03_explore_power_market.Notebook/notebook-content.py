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

# # 03 — Explore the power market
#
# Does consumption coincide with expensive hours? This analysis compares the time-average day-ahead price with the load-weighted price for each month of 2025. Weights are hourly German grid-load MWh; the market price represents the Germany/Luxembourg bidding zone.
#
# The analysis reads persisted silver tables and produces tables and charts without publishing gold tables. Hourly price multiplied by hourly volume estimates market-price exposure; it does not represent household bills or exact sub-hourly settlement costs.
#
# Wind and solar associations, generation-weighted prices and negative-price exposure remain research questions for subsequent analysis. Association alone does not establish causation.

# CELL ********************

from pyspark.sql import functions as F
import matplotlib.pyplot as plt

spark.conf.set("spark.sql.session.timeZone", "UTC")

for table_name in (
    "silver.consumption_hour", "silver.generation_hour",
    "silver.price_hour", "silver.dim_time_hour",
):
    print(f"{table_name}: {spark.table(table_name).count()} rows")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ## Check join coverage and reconciliation

# CELL ********************

from decimal import Decimal

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

display(cross_source_checks.toPandas())

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

# MARKDOWN ********************

# ## Monthly consumption-weighted price

# CELL ********************

spark.table("silver.dim_time_hour").createOrReplaceTempView("time_hour")

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

display(monthly_price_profile.toPandas())

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

monthly_checks = monthly_price_profile.collect()
assert len(monthly_checks) == 12, "Unexpected month count"
assert sum(row["matched_hours"] for row in monthly_checks) == 8760, "Unexpected annual coverage"
hours_by_month = {row["month"]: row["matched_hours"] for row in monthly_checks}
assert hours_by_month["2025-03"] == 743, "Unexpected spring DST coverage"
assert hours_by_month["2025-10"] == 745, "Unexpected autumn DST coverage"

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

# MARKDOWN ********************

# ## Interpretation of the captured results
#
# The original Fabric execution showed a January gap of +4.35 EUR/MWh and a June gap of -0.39 EUR/MWh. Those results are preserved in the separate execution snapshot. A positive gap indicates positive within-month association between price and load. A near-zero gap can reflect offsetting patterns and does not imply constant consumption.
#
# Monthly comparisons describe seasonality in the exposure gap. They do not explain its causes; hourly and seasonal comparisons are needed before interpreting renewable generation as a price driver.
