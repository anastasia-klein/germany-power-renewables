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
# The expanded analysis examines wind and solar associations, generation-weighted prices, negative-price timing and calendar-adjusted relationships. Association alone does not establish causation.

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

# ## Renewable generation, price exposure and market regimes
#
# The hourly research panel pairs German grid load and generation with the DE-LU day-ahead price. Generation is aggregated before joins, and every input must retain its declared grain. All quantities are hourly MWh; 1,000 MWh in an hour corresponds to 1 GW of average power.
#
# Capture price is `sum(price * generation) / sum(generation)` over matched valid hours. Capture rate divides that price by the time-average market price over the same period; it is undefined when the benchmark is non-positive. Exposure products use hourly averages and are not realized revenue, curtailment losses or settlement values.
#
# Negative-price exposure is the share of a source's generation occurring in hours whose exported hourly price is below zero. The hourly export cannot recover the number of negative quarter-hours after the October 2025 market-resolution change.

# CELL ********************

# EDA_INPUT: persisted silver tables only.
import numpy as np
import pandas as pd

for table_name, keys in {
    "silver.consumption_hour": ["time_key", "country_code"],
    "silver.price_hour": ["time_key", "bidding_zone_code"],
    "silver.generation_hour": ["time_key", "country_code", "generation_source_code"],
    "silver.dim_time_hour": ["time_key"],
}.items():
    table = spark.table(table_name)
    assert table.count() == table.select(*keys).distinct().count(), f"Duplicate keys: {table_name}"

eda_hourly = spark.sql("""
    WITH generation AS (
        SELECT time_key, country_code,
            SUM(CASE WHEN generation_source_code = 'wind_onshore' THEN generation_mwh END) AS wind_onshore_mwh,
            SUM(CASE WHEN generation_source_code = 'wind_offshore' THEN generation_mwh END) AS wind_offshore_mwh,
            SUM(CASE WHEN generation_source_code = 'solar' THEN generation_mwh END) AS solar_mwh,
            SUM(CASE WHEN generation_source_code IN ('biomass', 'hydropower', 'wind_onshore', 'wind_offshore', 'solar', 'other_renewable') THEN generation_mwh END) AS renewable_generation_mwh,
            SUM(generation_mwh) AS reported_generation_mwh
        FROM silver.generation_hour
        GROUP BY time_key, country_code
    )
    SELECT c.time_key, t.interval_start_utc, t.local_date, t.local_hour,
        c.grid_load_mwh, c.residual_load_mwh, p.day_ahead_price_eur_mwh,
        g.wind_onshore_mwh, g.wind_offshore_mwh, g.solar_mwh,
        g.renewable_generation_mwh, g.reported_generation_mwh
    FROM silver.consumption_hour c
    INNER JOIN silver.price_hour p ON c.time_key = p.time_key AND p.bidding_zone_code = 'DE-LU'
    INNER JOIN silver.dim_time_hour t ON c.time_key = t.time_key
    INNER JOIN generation g ON c.time_key = g.time_key AND c.country_code = g.country_code
    WHERE c.country_code = 'DE'
    ORDER BY c.time_key
""").toPandas()

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ## Coverage and annual reference values
#
# Reported generation sums available source categories. Nuclear remains unavailable rather than being treated as an observed zero. Renewable share uses reported generation, including pumped-storage output in its denominator; it is distinct from wind-and-solar generation divided by grid load.

# CELL ********************

# EDA_ANALYSIS: preparation and price reference.
import numpy as np
import pandas as pd

price_column = "day_ahead_price_eur_mwh"
metric_columns = [column for column in eda_hourly if column.endswith("_mwh")]
for column in metric_columns:
    eda_hourly[column] = pd.to_numeric(eda_hourly[column], errors="raise").astype(float)
eda_hourly["interval_start_utc"] = pd.to_datetime(eda_hourly["interval_start_utc"], utc=True)
eda_hourly["local_date"] = pd.to_datetime(eda_hourly["local_date"])
eda_hourly = eda_hourly.sort_values("time_key").reset_index(drop=True)
assert len(eda_hourly) == 8760 and eda_hourly.time_key.is_unique, "Unexpected hourly panel grain"
assert eda_hourly[metric_columns].notna().all().all(), "Missing research inputs"
assert (eda_hourly.grid_load_mwh > 0).all(), "Non-positive grid load"
assert (eda_hourly[["wind_onshore_mwh", "wind_offshore_mwh", "solar_mwh"]] >= 0).all().all(), "Negative source generation"
assert eda_hourly.interval_start_utc.diff().dropna().eq(pd.Timedelta(hours=1)).all(), "Non-contiguous UTC panel"
local_starts = eda_hourly.interval_start_utc.dt.tz_convert("Europe/Berlin")
assert (eda_hourly.local_date.dt.date == local_starts.dt.date).all(), "Local-date mismatch"
assert (eda_hourly.local_hour.astype(int) == local_starts.dt.hour).all(), "Local-hour mismatch"
eda_hourly["month"] = eda_hourly.local_date.dt.strftime("%Y-%m")
eda_hourly["day_of_week"] = eda_hourly.local_date.dt.dayofweek
eda_hourly["wind_mwh"] = eda_hourly.wind_onshore_mwh + eda_hourly.wind_offshore_mwh
eda_hourly["wind_solar_mwh"] = eda_hourly.wind_mwh + eda_hourly.solar_mwh
eda_hourly["wind_solar_load_ratio"] = eda_hourly.wind_solar_mwh / eda_hourly.grid_load_mwh
eda_hourly["is_negative_price"] = eda_hourly[price_column] < 0
assert np.allclose(eda_hourly.grid_load_mwh - eda_hourly.wind_solar_mwh, eda_hourly.residual_load_mwh, atol=0.03, rtol=0), "Residual reconciliation failed"

price = eda_hourly[price_column]
annual_summary = pd.DataFrame([{
    "matched_hours": len(eda_hourly),
    "consumption_twh": eda_hourly.grid_load_mwh.sum() / 1e6,
    "wind_twh": eda_hourly.wind_mwh.sum() / 1e6,
    "solar_twh": eda_hourly.solar_mwh.sum() / 1e6,
    "renewable_share_of_reported_generation": eda_hourly.renewable_generation_mwh.sum() / eda_hourly.reported_generation_mwh.sum(),
    "average_price_eur_mwh": price.mean(),
    "load_weighted_price_eur_mwh": np.average(price, weights=eda_hourly.grid_load_mwh),
    "negative_price_hours": int((price < 0).sum()),
    "negative_price_hour_share": (price < 0).mean(),
    "zero_price_hours": int((price == 0).sum()),
    "p05_price_eur_mwh": price.quantile(0.05),
    "median_price_eur_mwh": price.median(),
    "p95_price_eur_mwh": price.quantile(0.95),
    "price_std_eur_mwh": price.std(ddof=0),
    "minimum_price_eur_mwh": price.min(),
    "maximum_price_eur_mwh": price.max(),
}])
display(annual_summary.round(4))

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ## Generation-weighted prices and negative-price exposure
#
# The annual capture ratio is recomputed from annual hourly components. It is not the average of monthly ratios. Combined wind is weighted by combined onshore and offshore generation. Negative-price volume exposure and negative-price hour share have different denominators.

# CELL ********************

# EDA_ANALYSIS: capture metrics.
def capture_metrics(frame, volume_column):
    matched = frame[[price_column, volume_column]].dropna()
    volume = matched[volume_column]
    market_price = matched[price_column]
    denominator = volume.sum()
    benchmark = market_price.mean()
    captured = (market_price * volume).sum() / denominator if denominator > 0 else np.nan
    return {
        "matched_hours": len(matched),
        "generation_twh": denominator / 1e6,
        "average_price_eur_mwh": benchmark,
        "capture_price_eur_mwh": captured,
        "capture_rate": captured / benchmark if benchmark > 0 else np.nan,
        "negative_price_generation_share": volume[market_price < 0].sum() / denominator if denominator > 0 else np.nan,
    }

capture_sources = {"wind_onshore": "wind_onshore_mwh", "wind_offshore": "wind_offshore_mwh", "wind_combined": "wind_mwh", "solar": "solar_mwh"}
annual_capture = pd.DataFrame([
    {"generation_source": source, **capture_metrics(eda_hourly, column)}
    for source, column in capture_sources.items()
])
monthly_capture = pd.DataFrame([
    {"month": month, "generation_source": source, **capture_metrics(group, column)}
    for month, group in eda_hourly.groupby("month", sort=True)
    for source, column in capture_sources.items()
])
display(annual_capture.round(4))
display(monthly_capture.pivot(index="month", columns="generation_source", values="capture_rate").round(4))

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ## Negative prices: timing, conditions and episode length
#
# Episodes are consecutive negative hourly observations in UTC. They cross local date boundaries when appropriate. Shares are based on matched hours, while generation exposure is weighted by MWh. This does not establish curtailment, losses or negative retail prices.

# CELL ********************

# EDA_ANALYSIS: negative-price profiles and episodes.
negative_by_month = eda_hourly.groupby("month").agg(
    matched_hours=("time_key", "size"), negative_hours=("is_negative_price", "sum"),
    average_price_eur_mwh=(price_column, "mean"),
)
negative_by_month["negative_hour_share"] = negative_by_month.negative_hours / negative_by_month.matched_hours
negative_by_hour = eda_hourly.groupby("local_hour").agg(
    matched_hours=("time_key", "size"), negative_hours=("is_negative_price", "sum"),
)
negative_by_hour["negative_hour_share"] = negative_by_hour.negative_hours / negative_by_hour.matched_hours
negative_conditions = eda_hourly.groupby("is_negative_price")[["grid_load_mwh", "wind_mwh", "solar_mwh", "residual_load_mwh", "wind_solar_load_ratio"]].mean()
negative = eda_hourly.is_negative_price
runs = negative.ne(negative.shift(fill_value=False)).cumsum()
negative_episodes = eda_hourly.loc[negative].groupby(runs[negative]).agg(
    interval_start_utc=("interval_start_utc", "min"),
    last_interval_start_utc=("interval_start_utc", "max"),
    duration_hours=("time_key", "size"),
    minimum_price_eur_mwh=(price_column, "min"),
)
negative_episodes["interval_end_utc"] = negative_episodes.last_interval_start_utc + pd.Timedelta(hours=1)
negative_episodes = negative_episodes.drop(columns="last_interval_start_utc").rename_axis("episode_id").sort_values("duration_hours", ascending=False)
daily_price_spread = eda_hourly.groupby("local_date")[price_column].agg(["min", "max"])
daily_price_spread["spread_eur_mwh"] = daily_price_spread["max"] - daily_price_spread["min"]
display(negative_by_month.round(4))
display(negative_conditions.round(4))
display(negative_episodes.head(8))

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ## Raw and calendar-adjusted associations
#
# The adjustment removes month-by-local-hour fixed effects and additive day-of-week effects from both prices and each explanatory variable. It describes deviations from the expected calendar profile, not a causal effect. Spearman correlation uses average ranks and does not require SciPy.
#
# A separate descriptive OLS model includes wind, solar and grid load together with the same calendar controls. Residual load is excluded from that model because it is grid load minus wind and solar. Coefficients are not forecasts or estimates of a renewable policy effect; weather, fuel prices, imports, forecasts, outages and serial dependence remain unmodeled. The sensitivity sample uses local hours 08:00 through 17:00, not an inferred astronomical daylight window. No significance claims are made.

# CELL ********************

# EDA_ANALYSIS: calendar adjustment and conditional association.
association_columns = ["wind_mwh", "solar_mwh", "grid_load_mwh", "residual_load_mwh", "wind_solar_load_ratio"]
calendar_groups = eda_hourly.month + "_" + eda_hourly.local_hour.astype(str)
calendar_controls = np.column_stack([
    np.ones(len(eda_hourly)),
    pd.get_dummies(calendar_groups, drop_first=True, dtype=float).to_numpy(),
    pd.get_dummies(eda_hourly.day_of_week, drop_first=True, dtype=float).to_numpy(),
])
values = eda_hourly[[price_column, *association_columns]].to_numpy(dtype=float)
calendar_coefficients = np.linalg.lstsq(calendar_controls, values, rcond=None)[0]
calendar_residuals = values - calendar_controls @ calendar_coefficients
correlation_rows = []
for index, column in enumerate(association_columns, start=1):
    correlation_rows.append({
        "variable": column,
        "raw_pearson": np.corrcoef(values[:, 0], values[:, index])[0, 1],
        "raw_spearman": eda_hourly[[price_column, column]].rank().corr().iloc[0, 1],
        "calendar_adjusted_pearson": np.corrcoef(calendar_residuals[:, 0], calendar_residuals[:, index])[0, 1],
    })
associations = pd.DataFrame(correlation_rows)

feature_columns = ["wind_mwh", "solar_mwh", "grid_load_mwh"]
conditional_rows = []
for sample_name, mask in {
    "all_hours": np.ones(len(eda_hourly), dtype=bool),
    "local_hours_08_to_17": eda_hourly.local_hour.between(8, 17).to_numpy(),
}.items():
    subset = eda_hourly.loc[mask]
    groups = subset.month + "_" + subset.local_hour.astype(str)
    controls = np.column_stack([
        np.ones(len(subset)),
        pd.get_dummies(groups, drop_first=True, dtype=float).to_numpy(),
        pd.get_dummies(subset.day_of_week, drop_first=True, dtype=float).to_numpy(),
    ])
    features = subset[feature_columns].to_numpy() / 1000
    matrix = np.column_stack([controls, features])
    response = subset[price_column].to_numpy()
    coefficients = np.linalg.lstsq(matrix, response, rcond=None)[0]
    residual = response - matrix @ coefficients
    r_squared = 1 - np.sum(residual ** 2) / np.sum((response - response.mean()) ** 2)
    for column, coefficient in zip(feature_columns, coefficients[-3:]):
        conditional_rows.append({"sample": sample_name, "variable": column,
                                 "eur_mwh_per_additional_gwh": coefficient,
                                 "in_sample_r_squared": r_squared, "hours": len(subset)})
conditional_associations = pd.DataFrame(conditional_rows)
display(associations.round(4))
display(conditional_associations.round(4))

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ## Price distribution across generation and residual-load regimes
#
# Deciles use annual observed values and are descriptive bins, not policy thresholds. Lowest and highest groups can differ in season, hour and demand. Residual-load bins help distinguish the quantity of variable renewable output from its size relative to grid load.

# CELL ********************

# EDA_ANALYSIS: regime summaries.
regime_rows = []
for variable in ["wind_solar_load_ratio", "residual_load_mwh"]:
    deciles = pd.qcut(eda_hourly[variable], q=10, labels=False, duplicates="drop")
    for decile, group in eda_hourly.groupby(deciles):
        regime_rows.append({
            "variable": variable, "decile": int(decile) + 1, "hours": len(group),
            "mean_explanatory_value": group[variable].mean(),
            "average_price_eur_mwh": group[price_column].mean(),
            "negative_price_hour_share": group.is_negative_price.mean(),
        })
price_regimes = pd.DataFrame(regime_rows)
resolution_period_summary = eda_hourly.assign(
    period=np.where(eda_hourly.local_date < pd.Timestamp("2025-10-01"), "Jan-Sep hourly market", "Oct-Dec hourly export of quarter-hour market")
).groupby("period").agg(matched_hours=("time_key", "size"), average_price_eur_mwh=(price_column, "mean"), negative_hours=("is_negative_price", "sum"))
display(price_regimes.round(4))
display(resolution_period_summary.round(4))

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ## Price and generation patterns

# CELL ********************

# EDA_ANALYSIS: association figures.
import matplotlib.pyplot as plt
from matplotlib.colors import LogNorm

plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False})
fig, axes = plt.subplots(1, 3, figsize=(15, 4.5), constrained_layout=True)
densities = []
for ax, variable, title in zip(axes, ["wind_mwh", "solar_mwh", "residual_load_mwh"], ["Wind generation", "Solar generation", "Residual load"]):
    density = ax.hexbin(eda_hourly[variable] / 1000, eda_hourly[price_column], gridsize=35, mincnt=1, bins="log", cmap="viridis", linewidths=0)
    densities.append(density)
    ax.axhline(0, color="#64748b", linewidth=0.8)
    ax.set_xlabel(f"{title} (GWh per hour)")
    ax.set_ylabel("Day-ahead price (EUR/MWh)")
    ax.set_title(title)
maximum_density = max(item.get_array().max() for item in densities)
for density in densities:
    density.set_norm(LogNorm(vmin=1, vmax=maximum_density))
fig.colorbar(density, ax=axes, label="Hour count (log scale)", shrink=0.8)
fig.suptitle("Germany / DE-LU: observed hourly associations, 2025", fontsize=14)
plt.show()

fig, axes = plt.subplots(1, 2, figsize=(13, 4.8), constrained_layout=True)
for source, label, color in [("wind_combined", "Wind combined", "#2563eb"), ("solar", "Solar", "#d97706")]:
    group = monthly_capture.loc[monthly_capture.generation_source == source]
    axes[0].plot(group.month.str[-2:], group.capture_rate * 100, marker="o", label=label, color=color)
axes[0].axhline(100, color="#64748b", linestyle="--", linewidth=1)
axes[0].set(xlabel="Month", ylabel="Capture rate (%)", title="Generation-weighted price / market average")
axes[0].legend(frameon=False)
axes[0].grid(axis="y", alpha=0.2)
selected = annual_capture.set_index("generation_source").loc[["wind_onshore", "wind_offshore", "solar"]]
axes[1].bar(["Wind onshore", "Wind offshore", "Solar"], selected.negative_price_generation_share * 100, color=["#2563eb", "#0891b2", "#d97706"])
axes[1].axhline(annual_summary.negative_price_hour_share.iloc[0] * 100, color="#64748b", linestyle="--", label="Share of all hours with negative price")
axes[1].set(ylabel="Generation during negative-price hours (%)", title="Negative-price volume exposure")
axes[1].legend(frameon=False, fontsize=8)
fig.suptitle("Hourly market-price exposure, 2025", fontsize=14)
plt.show()

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# EDA_ANALYSIS: calendar and regime figures.
negative_heatmap = eda_hourly.pivot_table(index="month", columns="local_hour", values="is_negative_price", aggfunc="mean") * 100
fig, axes = plt.subplots(1, 2, figsize=(14, 5.5), constrained_layout=True)
image = axes[0].imshow(negative_heatmap.to_numpy(), aspect="auto", cmap="YlOrRd", vmin=0)
axes[0].set_xticks(range(0, 24, 3), range(0, 24, 3))
axes[0].set_yticks(range(12), negative_heatmap.index)
axes[0].set(xlabel="Local hour (Europe/Berlin)", title="Negative-price share within month and local hour")
fig.colorbar(image, ax=axes[0], label="Share of hours (%)", shrink=0.85)
regimes = price_regimes.loc[price_regimes.variable == "wind_solar_load_ratio"]
axes[1].plot(regimes.mean_explanatory_value * 100, regimes.average_price_eur_mwh, marker="o", color="#2563eb")
axes[1].axhline(0, color="#64748b", linewidth=0.8)
axes[1].set(xlabel="Wind + solar generation / grid load (%)", ylabel="Mean price (EUR/MWh)", title="Annual generation-to-load deciles")
axes[1].grid(alpha=0.2)
fig.suptitle("Negative prices and renewable generation relative to load, 2025", fontsize=14)
plt.show()

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ## Full generation mix: context beyond wind and solar

# This fifth figure includes every reported generation category, not only variable renewables. Values are annual energy delivered to the public grid. The mix is not a decomposition of the electricity price or the origin of consumed electricity.

# Nuclear observations remain unavailable; they are retained in the table and omitted from the bars rather than plotted as measured zero. Pumped-storage output is shown separately from renewable generation. The denominator of each share is the sum of all available generation categories, including pumped-storage output.

# CELL ********************

# EDA_INPUT: generation mix from persisted silver data.
eda_generation_mix = spark.sql("""
    SELECT generation_source_code,
        COUNT(*) AS matched_hours,
        COUNT(generation_mwh) AS valid_hours,
        SUM(generation_mwh) / 1000000 AS generation_twh
    FROM silver.generation_hour
    WHERE country_code = 'DE'
    GROUP BY generation_source_code
""").toPandas()

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# EDA_ANALYSIS: full generation mix table and figure.
from matplotlib.patches import Patch

mix_sources = {
    "biomass": ("Biomass", "renewable"),
    "hydropower": ("Hydropower", "renewable"),
    "wind_offshore": ("Wind offshore", "renewable"),
    "wind_onshore": ("Wind onshore", "renewable"),
    "solar": ("Photovoltaics", "renewable"),
    "other_renewable": ("Other renewable", "renewable"),
    "nuclear": ("Nuclear", "other_generation"),
    "lignite": ("Lignite", "other_generation"),
    "hard_coal": ("Hard coal", "other_generation"),
    "fossil_gas": ("Fossil gas", "other_generation"),
    "pumped_storage": ("Hydro pumped storage", "storage_output"),
    "other_conventional": ("Other conventional", "other_generation"),
}
assert eda_generation_mix.generation_source_code.is_unique, "Duplicate generation mix categories"
assert set(eda_generation_mix.generation_source_code) == set(mix_sources), "Unexpected generation mix categories"
assert eda_generation_mix.matched_hours.eq(8760).all(), "Incomplete annual source coverage"
expected_valid = eda_generation_mix.generation_source_code.map(lambda code: 0 if code == "nuclear" else 8760)
assert eda_generation_mix.valid_hours.eq(expected_valid).all(), "Unexpected generation availability"

generation_mix = eda_generation_mix.copy()
generation_mix["generation_twh"] = pd.to_numeric(generation_mix.generation_twh, errors="raise").astype(float)
generation_mix["generation_source"] = generation_mix.generation_source_code.map(lambda code: mix_sources[code][0])
generation_mix["classification"] = generation_mix.generation_source_code.map(lambda code: mix_sources[code][1])
assert generation_mix.loc[generation_mix.generation_source_code == "nuclear", "generation_twh"].isna().all(), "Nuclear must remain unavailable"
assert generation_mix.loc[generation_mix.generation_source_code != "nuclear", "generation_twh"].notna().all(), "Missing observed source total"
reported_total = generation_mix.generation_twh.sum(min_count=1)
assert reported_total > 0, "Non-positive reported generation total"
generation_mix["share_of_reported_generation"] = generation_mix.generation_twh / reported_total
assert abs(generation_mix.share_of_reported_generation.sum() - 1) < 1e-10, "Generation shares do not reconcile"
assert abs(reported_total - eda_hourly.reported_generation_mwh.sum() / 1e6) < 1e-7, "Generation total differs from the hourly panel"
generation_mix = generation_mix.sort_values("generation_twh", ascending=False, na_position="last").reset_index(drop=True)
display(generation_mix[["generation_source", "classification", "valid_hours", "generation_twh", "share_of_reported_generation"]].round(4))

mix_plot = generation_mix.dropna(subset=["generation_twh"]).sort_values("generation_twh")
mix_colors = {"renewable": "#22836c", "storage_output": "#2563eb", "other_generation": "#64748b"}
fig, ax = plt.subplots(figsize=(10, 6.8), constrained_layout=True)
bars = ax.barh(mix_plot.generation_source, mix_plot.generation_twh, color=mix_plot.classification.map(mix_colors))
ax.bar_label(bars, fmt="%.2f", padding=4, fontsize=9)
ax.set_xlim(0, mix_plot.generation_twh.max() * 1.17)
ax.set_xlabel("Reported net generation (TWh)")
ax.set_title("Germany: reported generation by source, 2025\nNuclear unavailable in this export; not plotted as measured zero", loc="left", pad=16)
ax.spines[["top", "right", "left"]].set_visible(False)
ax.grid(axis="x", alpha=0.15)
ax.set_axisbelow(True)
ax.legend(handles=[Patch(color=mix_colors[key], label=label) for key, label in [
    ("renewable", "Renewable"), ("other_generation", "Other reported generation"), ("storage_output", "Pumped-storage output")
]], loc="lower right", frameon=False, fontsize=8)
plt.show()

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ## Findings and gold candidates
#
# The local execution against the original CSV exports gives a market average of 89.32 EUR/MWh and a load-weighted price of 92.42 EUR/MWh. Annual capture prices are 46.07 for solar, 77.31 for onshore wind and 85.53 for offshore wind. Solar capture rate is 51.58%; 24.13% of solar generation occurs in negative-price hours.
#
# There are 573 negative hourly exported prices, or 6.54% of the year. June has 141 negative hours. Its solar capture rate is 31.36%, with 46.94% of solar generation in negative-price hours. These describe market exposure, not generator profits or household bills.
#
# Raw price correlation is 0.876 with residual load, -0.286 with wind and -0.557 with solar. After calendar adjustment, the respective values are 0.774, -0.628 and -0.232. These are descriptive relationships; actual generation is known after the day-ahead auction and cannot be treated as an available bidding-time forecast.
#
# The gold model contains an hourly market fact and a generation-source fact with shared time, market and generation-source dimensions. The project author confirmed that notebook 04 published all five tables successfully in Fabric. Weighted prices, capture rates and exposure shares are recomputed from hourly components. Monthly means, regression coefficients and decile bins are not permanent fact tables.
#
# The expanded EDA passed in Fabric before the generation-mix figure was added. This fifth-figure revision still awaits its Fabric run. Saved local output snapshots are labeled separately from Fabric execution evidence.
