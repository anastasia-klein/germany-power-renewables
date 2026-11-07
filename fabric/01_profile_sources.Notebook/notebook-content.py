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

# # 01 — Profile source files
#
# Source assessment for the three hourly SMARD exports covering the local calendar year 2025. The profile records file hashes, dimensions, numeric coverage, missing markers and the chronological CET/CEST sequence.
#
# The spring transition has 23 physical hours and the autumn transition has 25. Repeated local labels remain separate observations. Nuclear generation and the obsolete DE/AT/LU price series contain expected missing markers; missing values are distinct from zero.
#
# This notebook reads raw files without writing lakehouse tables. The silver build enforces its own input contract independently of this profile.
#
# Data: Bundesnetzagentur | SMARD.de, CC BY 4.0. [Source](https://www.smard.de/en/downloadcenter/download-market-data/) · [Time conventions](https://www.smard.de/en/change-from-summer-to-winter-time-218202)

# CELL ********************

import csv
import hashlib
import json
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

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

raw_root = Path("/lakehouse/default/Files/raw/smard")
profile = profile_sources(raw_root, 2025)

for source in profile["sources"]:
    print(f"{source['file']}: {source['row_count']} rows, {source['column_count']} columns")
    for metric in source["metrics"]:
        if metric["missing_marker_count"]:
            print(f"  Missing markers: {metric['column']} = {metric['missing_marker_count']}")

print("Non-24-hour days:", profile["non_24_hour_days"])
print("Source checks passed")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
