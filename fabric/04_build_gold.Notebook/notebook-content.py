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

# # 04 — Build gold
#
# Current scope: publish the validated technical calendar from `silver.dim_time_hour` as `gold.dim_time_hour`. The reporting calendar preserves UTC uniqueness and local calendar attributes.
#
# Analytical fact tables are proposed in the gold metric contract following EDA and are not implemented yet. The proposed model contains an hourly market fact and an hourly generation-source fact with shared dimensions. This notebook currently publishes only the calendar from persisted silver data.

# CELL ********************

from pyspark.sql import functions as F

spark.conf.set("spark.sql.session.timeZone", "UTC")
calendar = spark.table("silver.dim_time_hour")

calendar_checks = calendar.agg(
    F.count("*").alias("rows"),
    F.countDistinct("time_key").alias("unique_keys"),
    F.countDistinct("interval_start_utc").alias("unique_utc_starts"),
).first().asDict()

assert calendar_checks["rows"] == 8760, "Unexpected calendar coverage"
assert calendar_checks["unique_keys"] == 8760, "Duplicate calendar keys"
assert calendar_checks["unique_utc_starts"] == 8760, "Duplicate UTC starts"

spark.sql("CREATE SCHEMA IF NOT EXISTS gold")
calendar.write.format("delta").mode("overwrite").saveAsTable("gold.dim_time_hour")

saved_calendar = spark.table("gold.dim_time_hour")
assert saved_calendar.count() == 8760, "Unexpected saved calendar coverage"
print("Saved gold.dim_time_hour: 8760 rows")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
