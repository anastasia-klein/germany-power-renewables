"""Derive portable, output-free notebooks from the versioned Fabric source.

Fabric source is authoritative. Existing execution snapshots remain separate.
"""

import argparse
import ast
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
NAMES = (
    "01_profile_sources",
    "02_build_silver",
    "03_explore_power_market",
    "04_build_gold",
)


def export_notebook(source):
    sections = re.split(r"^# (MARKDOWN|CELL|METADATA) \*+\s*$", source, flags=re.M)
    cells = []
    for kind, body in zip(sections[1::2], sections[2::2]):
        if kind == "METADATA":
            continue
        body = body.strip()
        if kind == "MARKDOWN":
            lines = body.splitlines()
            if any(line != "#" and not line.startswith("# ") for line in lines):
                raise ValueError("Invalid Fabric markdown section")
            body = "\n".join(line[2:] if line != "#" else "" for line in lines)
        else:
            ast.parse(body)
        item = {
            "cell_type": "markdown" if kind == "MARKDOWN" else "code",
            "metadata": {},
            "source": (body + "\n").splitlines(keepends=True),
        }
        if kind == "CELL":
            item.update(execution_count=None, outputs=[])
        cells.append(item)
    return {
        "cells": cells,
        "metadata": {
            "kernelspec": {
                "display_name": "Synapse PySpark",
                "language": "python",
                "name": "synapse_pyspark",
            },
            "language_info": {"name": "python"},
        },
        "nbformat": 4,
        "nbformat_minor": 4,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    for name in NAMES:
        source = (ROOT / "fabric" / f"{name}.Notebook" / "notebook-content.py").read_text()
        content = json.dumps(export_notebook(source), indent=1, ensure_ascii=False) + "\n"
        target = ROOT / "notebooks" / f"{name}.ipynb"
        if args.check:
            if target.read_text() != content:
                raise ValueError(f"Portable notebook differs from Fabric source: {name}")
        else:
            target.write_text(content)
    print("Portable notebooks match Fabric source" if args.check else "Exported portable notebooks")


if __name__ == "__main__":
    main()
