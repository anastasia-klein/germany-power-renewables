"""Run in Fabric with lh_power_renewables attached; archive existing tables only."""

import hashlib
import json
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import notebookutils
import pyarrow.parquet as pq

spark.conf.set("spark.sql.session.timeZone", "UTC")
archive_started = datetime.now(timezone.utc)
archive_id = archive_started.strftime("onelake_silver_gold_%Y%m%dT%H%M%SZ")
archive_root = Path(tempfile.mkdtemp(prefix=archive_id + "_")) / archive_id
archive_root.mkdir()
manifest = {
    "archive_id": archive_id,
    "started_at_utc": archive_started.isoformat(),
    "lakehouse": "lh_power_renewables",
    "scope": "All permanent tables in silver and gold; original Delta directories and current Parquet snapshots",
    "timestamp_interpretation": "Spark session UTC; local calendar columns retained as stored",
    "tables": [],
}


def copy_delta_files(source, destination):
    """Copy Delta storage, excluding Fabric's virtual Iceberg metadata directory."""
    destination.mkdir(parents=True, exist_ok=True)
    excluded = []
    for entry in notebookutils.fs.ls(source):
        if entry.isDir and entry.name.rstrip("/") == "metadata":
            excluded.append({"path": entry.path, "reason": "Auxiliary virtual Iceberg metadata; not part of the Delta transaction log"})
            continue
        assert notebookutils.fs.cp(entry.path, "file:" + str(destination / entry.name.rstrip("/")), entry.isDir), entry.path
    return excluded


for schema_name in ("silver", "gold"):
    tables = [t for t in spark.catalog.listTables(schema_name) if not t.isTemporary]
    assert tables, f"No tables found in {schema_name}"
    for table in sorted(tables, key=lambda t: t.name):
        name = f"{schema_name}.{table.name}"
        quoted = f"`{schema_name}`.`{table.name}`"
        detail = spark.sql(f"DESCRIBE DETAIL {quoted}").first().asDict()
        assert detail["format"] == "delta", f"Unexpected format for {name}"
        before = spark.sql(f"DESCRIBE HISTORY {quoted} LIMIT 1").first().asDict()
        version = int(before["version"])
        frame = spark.read.format("delta").option("versionAsOf", version).load(detail["location"])
        count = frame.count()
        delta_relative = Path("delta") / schema_name / table.name
        delta_local = archive_root / delta_relative
        delta_local.parent.mkdir(parents=True, exist_ok=True)
        excluded = copy_delta_files(detail["location"], delta_local)
        assert (delta_local / "_delta_log").is_dir(), f"Missing Delta log: {name}"
        parquet_relative = Path("parquet") / schema_name / (table.name + ".parquet")
        parquet_local = archive_root / parquet_relative
        parquet_local.parent.mkdir(parents=True, exist_ok=True)
        frame.toPandas().to_parquet(parquet_local, engine="pyarrow", index=False)
        assert pq.read_metadata(parquet_local).num_rows == count, f"Parquet row mismatch: {name}"
        schema_relative = Path("schemas") / schema_name / (table.name + ".json")
        schema_local = archive_root / schema_relative
        schema_local.parent.mkdir(parents=True, exist_ok=True)
        schema_local.write_text(frame.schema.json(), encoding="utf-8")
        after_version = int(spark.sql(f"DESCRIBE HISTORY {quoted} LIMIT 1").first()["version"])
        assert version == after_version, f"Source changed during copy: {name}"
        manifest["tables"].append({
            "name": name, "rows": count, "columns": len(frame.columns),
            "delta_version": version, "source_location": detail["location"],
            "delta_path": delta_relative.as_posix(),
            "parquet_path": parquet_relative.as_posix(),
            "schema_path": schema_relative.as_posix(),
            "excluded_auxiliary_paths": excluded,
            "delta_history": [json.loads(x) for x in spark.sql(f"DESCRIBE HISTORY {quoted}").toJSON().collect()],
            "detail": {k: str(v) if not isinstance(v, (str, int, float, bool, list, dict, type(None))) else v for k, v in detail.items()},
        })
        print(f"Archived {name}: {count:,} rows, {len(frame.columns)} columns, Delta v{version}")

assert len(manifest["tables"]) == 9, "Unexpected number of silver/gold tables"
manifest["completed_at_utc"] = datetime.now(timezone.utc).isoformat()
manifest["files"] = []
for path in sorted(archive_root.rglob("*")):
    if path.is_file():
        manifest["files"].append({
            "path": path.relative_to(archive_root).as_posix(),
            "bytes": path.stat().st_size,
            "sha256": hashlib.file_digest(path.open("rb"), "sha256").hexdigest(),
        })
(archive_root / "manifest.json").write_text(json.dumps(manifest, indent=2, default=str), encoding="utf-8")
zip_path = archive_root.parent / (archive_id + ".zip")
with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
    for path in sorted(archive_root.rglob("*")):
        if path.is_file():
            archive.write(path, path.relative_to(archive_root.parent))
with zipfile.ZipFile(zip_path) as archive:
    assert archive.testzip() is None, "Archive integrity check failed"
zip_hash = hashlib.file_digest(zip_path.open("rb"), "sha256").hexdigest()
destination = "Files/preservation/" + zip_path.name
notebookutils.fs.mkdirs("Files/preservation")
assert notebookutils.fs.cp("file:" + str(zip_path), destination), "Archive upload failed"
print(f"ARCHIVE_READY: {destination}")
print(f"ARCHIVE_BYTES: {zip_path.stat().st_size}")
print(f"ARCHIVE_SHA256: {zip_hash}")
print(f"TABLES: {len(manifest['tables'])}; FILES: {len(manifest['files'])}")
