"""Validate the gold notebook SQL with Decimal inputs in local DuckDB.

This checks transformation logic and edge cases, not Fabric Spark execution or
Delta publication. The SQL strings are extracted from the versioned notebook.
"""

import ast
import csv
import hashlib
import json
from datetime import date, datetime, timedelta, timezone
from collections import Counter
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

import duckdb
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]


def main():
    path = ROOT / "fabric/04_build_gold.Notebook/notebook-content.py"
    tree = ast.parse(path.read_text())
    names = {"market_sql", "generation_sql", "market_metric_sql", "capture_metric_sql", "source_rows"}
    definitions = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            if node.targets[0].id in names:
                definitions[node.targets[0].id] = ast.literal_eval(node.value)
    assert definitions.keys() == names
    calendar_nodes = []
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            if node.targets[0].id in {"local_zone", "current", "finish", "time_rows"}:
                calendar_nodes.append(node)
        elif isinstance(node, ast.While):
            calendar_nodes.append(node)
    calendar_namespace = {"YEAR": 2025, "date": date, "datetime": datetime, "timedelta": timedelta, "timezone": timezone, "ZoneInfo": ZoneInfo}
    exec(compile(ast.Module(body=calendar_nodes, type_ignores=[]), "gold_calendar", "exec"), calendar_namespace)
    calendar = calendar_namespace["time_rows"]
    assert len(calendar) == len({row[0] for row in calendar}) == 8760
    day_counts = Counter(row[2] for row in calendar)
    assert day_counts[date(2025, 3, 30)] == 23 and day_counts[date(2025, 10, 26)] == 25
    autumn = [row for row in calendar if row[2] == date(2025, 10, 26) and row[3] == 2]
    assert [(row[0], row[5]) for row in autumn] == [(2025102600, 0), (2025102601, 1)]
    assert all(row[6] - row[1] == timedelta(hours=1) and row[7] == 60 for row in calendar)
    assert sum(row[12] == 15 for row in calendar) == 2209

    def raw(category):
        path = ROOT / f"data/raw/smard/{category}_202501010000_202601010000_Hour.csv"
        with path.open(encoding="utf-8-sig", newline="") as handle:
            return list(csv.DictReader(handle, delimiter=";"))

    def number(value):
        return None if value == "-" else Decimal(value.replace(",", ""))

    zone = ZoneInfo("Europe/Berlin")
    first = datetime(2025, 1, 1, tzinfo=zone).astimezone(timezone.utc)
    instants = [first + timedelta(hours=hour) for hour in range(8760)]
    keys = [int(value.strftime("%Y%m%d%H")) for value in instants]
    consumption_rows = raw("Actual_consumption")
    price_rows = raw("Day-ahead_prices")
    generation_rows = raw("Actual_generation")
    expected_labels = [instant.astimezone(zone).replace(tzinfo=None) for instant in instants]
    for rows in [consumption_rows, price_rows, generation_rows]:
        assert [datetime.strptime(row["Start date"], "%b %d, %Y %I:%M %p") for row in rows] == expected_labels

    consumption_names = {
        "grid_load_mwh": "grid load", "grid_load_including_pumping_mwh": "Grid load incl. hydro pumped storage",
        "pumping_consumption_mwh": "Hydro pumped storage", "residual_load_mwh": "Residual load",
    }
    source_labels = {row[0]: row[1] for row in definitions["source_rows"]}
    consumption = pd.DataFrame([
        {"time_key": key, "country_code": "DE", **{
            column: number(row[f"{label} [MWh] Calculated resolutions"])
            for column, label in consumption_names.items()
        }} for key, row in zip(keys, consumption_rows)
    ])
    price = pd.DataFrame([
        {"time_key": key, "bidding_zone_code": "DE-LU", "day_ahead_price_eur_mwh": number(row["Germany/Luxembourg [€/MWh] Calculated resolutions"])}
        for key, row in zip(keys, price_rows)
    ])
    generation = pd.DataFrame([
        {"time_key": key, "country_code": "DE", "generation_source_code": code,
         "generation_mwh": number(row[f"{label} [MWh] Calculated resolutions"])}
        for key, row in zip(keys, generation_rows)
        for code, label in source_labels.items()
    ])
    with duckdb.connect() as db:
        for name, frame in [("consumption", consumption), ("price", price), ("generation", generation)]:
            db.register("input_frame", frame)
            decimals = [column for column in frame if column.endswith("_mwh")]
            projection = [f'CAST("{column}" AS DECIMAL(18,2)) AS "{column}"' if column in decimals else f'"{column}"' for column in frame]
            db.execute(f"CREATE TABLE gold_input_{name} AS SELECT {', '.join(projection)} FROM input_frame")
            db.unregister("input_frame")
        db.execute("CREATE TABLE gold_prepared_market AS " + definitions["market_sql"])
        db.execute("CREATE TABLE gold_prepared_generation AS " + definitions["generation_sql"])
        assert db.sql("SELECT COUNT(*), COUNT(DISTINCT time_key) FROM gold_prepared_market").fetchall()[0] == (8760, 8760)
        assert db.sql("SELECT COUNT(*) FROM gold_prepared_generation").fetchall()[0][0] == 105120
        assert db.sql("SELECT COUNT(*) FROM (SELECT time_key, market_key, generation_source_code FROM gold_prepared_generation GROUP BY ALL)").fetchall()[0][0] == 105120
        assert db.sql("SELECT COUNT(*) FROM gold_prepared_market WHERE ABS(grid_load_including_pumping_mwh-grid_load_mwh-pumping_consumption_mwh)>0.02 OR ABS(grid_load_mwh-wind_solar_mwh-residual_load_mwh)>0.03").fetchall()[0][0] == 0
        for column in ["generation_mwh", "price_weighted_generation_eur", "matched_generation_mwh", "negative_price_generation_mwh"]:
            assert db.sql(f"SELECT COUNT(*) FROM gold_prepared_generation WHERE {column} IS NULL").fetchall()[0][0] == 8760
            assert db.sql(f"SELECT COUNT(*) FROM gold_prepared_generation WHERE {column} IS NULL AND generation_source_code <> 'nuclear'").fetchall()[0][0] == 0

        metrics = db.sql(definitions["market_metric_sql"]).fetchall()[0]
        prices = price.day_ahead_price_eur_mwh.tolist()
        loads = consumption.grid_load_mwh.tolist()
        exact_mean = sum(prices) / Decimal(8760)
        exact_load_weighted = sum(p * q for p, q in zip(prices, loads)) / sum(loads)
        assert abs(Decimal(str(metrics[1])) - exact_mean) < Decimal("1e-8")
        assert abs(Decimal(str(metrics[2])) - exact_load_weighted) < Decimal("1e-8")
        assert metrics[3:] == (573, 82)
        captures = {row[0]: row[1:] for row in db.sql(definitions["capture_metric_sql"]).fetchall()}
        for code, label in source_labels.items():
            volumes = [number(row[f"{label} [MWh] Calculated resolutions"]) for row in generation_rows]
            if code == "nuclear":
                assert captures[code] == (None, None)
                continue
            exact_capture = sum(p * q for p, q in zip(prices, volumes)) / sum(volumes)
            exact_negative_share = sum(q for p, q in zip(prices, volumes) if p < 0) / sum(volumes)
            assert abs(Decimal(str(captures[code][0])) - exact_capture) < Decimal("1e-8"), code
            assert abs(Decimal(str(captures[code][1])) - exact_negative_share) < Decimal("1e-8"), code

        # Preserve missing and observed zero volumes, and handle all price signs.
        db.execute("DELETE FROM gold_input_generation")
        db.execute("DELETE FROM gold_input_price")
        db.execute("INSERT INTO gold_input_price VALUES (1,'DE-LU',-10),(2,'DE-LU',0),(3,'DE-LU',100),(4,'DE-LU',NULL)")
        db.execute("INSERT INTO gold_input_generation VALUES (1,'DE','solar',2),(2,'DE','solar',3),(3,'DE','solar',0),(4,'DE','solar',4),(1,'DE','nuclear',NULL)")
        result = {row[0:3]: row[3:] for row in db.sql(definitions["generation_sql"]).fetchall()}
        assert result[(1, "DE_DE-LU", "solar")] == (Decimal(2), Decimal(-20), Decimal(2), Decimal(2), True, True)
        assert result[(2, "DE_DE-LU", "solar")] == (Decimal(3), Decimal(0), Decimal(3), Decimal(0), True, True)
        assert result[(3, "DE_DE-LU", "solar")] == (Decimal(0), Decimal(0), Decimal(0), Decimal(0), True, True)
        assert result[(4, "DE_DE-LU", "solar")] == (Decimal(4), None, None, None, True, False)
        assert result[(1, "DE_DE-LU", "nuclear")] == (None, None, None, None, False, False)

    sources = definitions["source_rows"]
    assert len(sources) == len({row[0] for row in sources}) == 12
    assert sum(row[3] for row in sources) == 6
    assert [row[0] for row in sources if row[4]] == ["pumped_storage"]
    result = {
        "checked_on": "2026-11-09", "notebook_source_sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "engine": "Local DuckDB " + duckdb.__version__,
        "market_fact_rows": 8760, "generation_fact_rows": 105120,
        "checks": ["Executed exact notebook fact SQL against source-derived DECIMAL inputs",
                   "Unique business keys and complete time coverage",
                   "Exact notebook calendar construction preserves UTC chronology, DST folds, ISO weekdays and market-resolution boundary",
                   "Pumping and residual-load balance",
                   "Market mean and load-weighted price independently checked with Decimal",
                   "Capture prices and negative-price volume shares for all eleven observed source categories independently checked with Decimal",
                   "Missing nuclear remains null; valid zero generation remains zero",
                   "Negative, zero, positive and missing price cases preserve matched-volume semantics"],
        "limitations": "Spark helpers, Fabric Lakehouse binding and Delta writes require the first Fabric run; no Fabric execution is claimed",
    }
    (ROOT / "data/validation/gold_build_local.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
