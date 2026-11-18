"""Validate a downloaded OneLake archive independently of Microsoft Fabric."""

import argparse
import hashlib
import json
import tempfile
import zipfile
from pathlib import Path

import duckdb
import pyarrow.compute as pc
import pyarrow.parquet as pq
from deltalake import DeltaTable

parser = argparse.ArgumentParser()
parser.add_argument("archive", type=Path)
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
connection = duckdb.connect(config={"extension_directory": "/private/tmp/power-archive-duckdb-extensions"})
connection.execute("INSTALL delta FROM core; LOAD delta")
expected_sha256 = "34b72e22c8df47fcbfbb6f428713d130ee83edd55905fab29ac78f4efc67c889"
digest = hashlib.sha256(args.archive.read_bytes()).hexdigest()
assert digest == expected_sha256, "Downloaded archive hash differs from Fabric output"
with tempfile.TemporaryDirectory(prefix="verify-onelake-") as temporary:
    with zipfile.ZipFile(args.archive) as archive:
        assert archive.testzip() is None
        for member in archive.infolist():
            target = (Path(temporary) / member.filename).resolve()
            assert target.is_relative_to(Path(temporary).resolve()), "Unsafe archive path"
        archive.extractall(temporary)
    root = next(Path(temporary).iterdir())
    manifest = json.loads((root / "manifest.json").read_text())
    for entry in manifest["files"]:
        path = root / entry["path"]
        assert path.stat().st_size == entry["bytes"], entry["path"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == entry["sha256"], entry["path"]
    results = []
    for entry in manifest["tables"]:
        restored = DeltaTable(str(root / entry["delta_path"]), version=entry["delta_version"])
        assert DeltaTable(str(root / entry["delta_path"])).version() == entry["delta_version"]
        delta = connection.execute("SELECT * FROM delta_scan(?)",
                                   [str(root / entry["delta_path"])]).fetch_arrow_table()
        parquet = pq.read_table(root / entry["parquet_path"])
        assert delta.num_rows == parquet.num_rows == entry["rows"], entry["name"]
        assert delta.column_names == parquet.column_names, entry["name"]
        parquet = parquet.cast(delta.schema)
        keys = [(name, "ascending") for name in delta.column_names]
        delta_sorted = delta.take(pc.sort_indices(delta, sort_keys=keys)).combine_chunks()
        parquet_sorted = parquet.take(pc.sort_indices(parquet, sort_keys=keys)).combine_chunks()
        assert delta_sorted.equals(parquet_sorted, check_metadata=False), entry["name"]
        result = {"table": entry["name"], "rows": delta.num_rows, "columns": delta.num_columns,
                  "delta_version": restored.version(), "delta_reopened_offline": True,
                  "all_rows_equal_parquet_snapshot": True}
        results.append(result)
        print(json.dumps(result), flush=True)
    assert len(results) == 9
    report = {"archive": args.archive.name, "sha256": digest, "files_hash_verified": len(manifest["files"]),
              "validation": "Restored each original Delta table locally using DuckDB Delta Kernel (including deletion-vector support) and compared every row with its pinned-version Parquet snapshot; no Fabric credentials used",
              "tables": results, "source_manifest": manifest}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
