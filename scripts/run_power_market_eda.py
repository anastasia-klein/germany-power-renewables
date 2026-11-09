"""Execute the versioned EDA cells locally against the original SMARD exports.

Local outputs are separate from Fabric run evidence. No lakehouse tables are written.
"""

import base64
import contextlib
import csv
import hashlib
import inspect
import io
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from export_notebooks import export_notebook
from smard_source_checks import profile_sources


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "evidence" / "eda_2025"


def load_hourly(root):
    raw = root / "data" / "raw" / "smard"
    timeline = pd.date_range("2025-01-01", "2026-01-01", freq="h", tz="Europe/Berlin", inclusive="left")
    frame = pd.DataFrame({
        "interval_start_utc": timeline.tz_convert("UTC"),
        "local_date": timeline.tz_localize(None).normalize(),
        "local_hour": timeline.hour,
    })
    frame["time_key"] = frame.interval_start_utc.dt.strftime("%Y%m%d%H").astype("int64")

    def source(category):
        path = raw / f"{category}_202501010000_202601010000_Hour.csv"
        result = pd.read_csv(path, sep=";", thousands=",", na_values="-")
        labels = pd.to_datetime(result["Start date"], format="%b %d, %Y %I:%M %p")
        assert labels.tolist() == timeline.tz_localize(None).tolist(), f"Invalid time sequence: {category}"
        return result

    consumption = source("Actual_consumption")
    generation = source("Actual_generation")
    price = source("Day-ahead_prices")
    frame["grid_load_mwh"] = consumption["grid load [MWh] Calculated resolutions"]
    frame["residual_load_mwh"] = consumption["Residual load [MWh] Calculated resolutions"]
    frame["day_ahead_price_eur_mwh"] = price["Germany/Luxembourg [€/MWh] Calculated resolutions"]
    for name, label in {"wind_onshore": "Wind onshore", "wind_offshore": "Wind offshore", "solar": "Photovoltaics"}.items():
        frame[f"{name}_mwh"] = generation[f"{label} [MWh] Calculated resolutions"]
    renewables = ["Biomass", "Hydropower", "Wind onshore", "Wind offshore", "Photovoltaics", "Other renewable"]
    renewable_columns = [f"{name} [MWh] Calculated resolutions" for name in renewables]
    assert generation[renewable_columns].notna().all().all(), "Missing renewable observations"
    assert generation["Nuclear [MWh] Calculated resolutions"].isna().all(), "Unexpected nuclear observations"
    frame["renewable_generation_mwh"] = generation[renewable_columns].sum(axis=1, min_count=len(renewables))
    frame["reported_generation_mwh"] = generation.iloc[:, 2:].sum(axis=1, min_count=1)
    return frame


def load_generation_mix(root):
    path = root / "data/raw/smard/Actual_generation_202501010000_202601010000_Hour.csv"
    generation = pd.read_csv(path, sep=";", thousands=",", na_values="-")
    codes = {
        "Biomass": "biomass", "Hydropower": "hydropower", "Wind offshore": "wind_offshore",
        "Wind onshore": "wind_onshore", "Photovoltaics": "solar", "Other renewable": "other_renewable",
        "Nuclear": "nuclear", "Lignite": "lignite", "Hard coal": "hard_coal", "Fossil gas": "fossil_gas",
        "Hydro pumped storage": "pumped_storage", "Other conventional": "other_conventional",
    }
    return pd.DataFrame([
        {"generation_source_code": code, "matched_hours": len(generation),
         "valid_hours": int(generation[f"{label} [MWh] Calculated resolutions"].count()),
         "generation_twh": generation[f"{label} [MWh] Calculated resolutions"].sum(min_count=1) / 1e6}
        for label, code in codes.items()
    ])


def main():
    executed_on = datetime.now(ZoneInfo("Europe/Berlin")).date().isoformat()
    profile = profile_sources(ROOT / "data" / "raw" / "smard", 2025)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    source = (ROOT / "fabric" / "03_explore_power_market.Notebook" / "notebook-content.py").read_text()
    notebook = export_notebook(source)
    outputs = []
    figure_number = 0

    def display(value):
        outputs.append({"output_type": "display_data", "metadata": {}, "data": {
            "text/html": value.to_html(), "text/plain": value.to_string(),
        }})

    def show():
        nonlocal figure_number
        for number in plt.get_fignums():
            figure_number += 1
            figure = plt.figure(number)
            buffer = io.BytesIO()
            figure.savefig(buffer, format="png", dpi=160, bbox_inches="tight", facecolor="white")
            png = buffer.getvalue()
            (OUTPUT / f"figure_{figure_number:02d}.png").write_bytes(png)
            if figure_number == 4:
                (OUTPUT / "generation_mix.png").write_bytes(png)
            outputs.append({"output_type": "display_data", "metadata": {}, "data": {
                "image/png": base64.b64encode(png).decode(), "text/plain": "<Matplotlib figure>",
            }})
            plt.close(figure)

    plt.show = show
    namespace = {"pd": pd, "np": np, "display": display}
    setup = "from pathlib import Path\nimport pandas as pd\n\n" + inspect.getsource(load_hourly) + "\n\n" + inspect.getsource(load_generation_mix)
    setup += "\nroot = Path.cwd()\nif not (root / 'data/raw/smard').exists():\n    root = root.parent\neda_hourly = load_hourly(root)\neda_generation_mix = load_generation_mix(root)\n"
    with contextlib.chdir(ROOT):
        exec(compile(setup, "local_input", "exec"), namespace)
    evidence_cells = [{"cell_type": "markdown", "metadata": {}, "source": [
        "# Germany power market: local EDA execution\n",
        f"\nExecuted locally on {executed_on} using the original SMARD CSV exports. ",
        "The analytical cells match the Fabric notebook source. These outputs do not represent a Fabric run.\n",
    ]}, {"cell_type": "code", "metadata": {}, "source": setup.splitlines(keepends=True),
         "execution_count": 1, "outputs": []}]
    execution_count = 1
    started = False
    for item in notebook["cells"]:
        content = "".join(item["source"])
        if item["cell_type"] == "markdown" and "## Renewable generation, price exposure" in content:
            started = True
        if not started:
            continue
        if item["cell_type"] == "code" and "# EDA_INPUT:" in content:
            continue
        if item["cell_type"] == "markdown":
            evidence_cells.append(item)
            continue
        outputs = []
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            exec(compile(content, f"eda_cell_{execution_count + 1}", "exec"), namespace)
        if stdout.getvalue():
            outputs.insert(0, {"output_type": "stream", "name": "stdout", "text": stdout.getvalue()})
        execution_count += 1
        evidence_cells.append({**item, "execution_count": execution_count, "outputs": outputs})

    tables = ["annual_summary", "annual_capture", "monthly_capture", "negative_by_month", "negative_by_hour",
              "negative_conditions", "negative_episodes", "daily_price_spread", "associations",
              "conditional_associations", "price_regimes", "resolution_period_summary", "generation_mix"]
    for name in tables:
        value = namespace[name]
        value.to_csv(OUTPUT / f"{name}.csv", index=value.index.name is not None, float_format="%.10f")
    metadata = {
        "executed_on": executed_on, "execution_environment": "Local Python; not Fabric",
        "analysis_source_sha256": hashlib.sha256(source.encode()).hexdigest(),
        "source_profile": profile,
        "rounding_policy": "Float64 for exploratory statistics; silver retains fixed-precision decimals",
        "hourly_coverage": int(namespace["annual_summary"].matched_hours.iloc[0]),
        "limitations": ["Single observed year; association is not causal",
                        "Hourly averaged products cannot reconstruct sub-hourly settlements",
                        "Generation excludes behind-the-meter self-consumption; missing nuclear is not zero"],
    }
    (OUTPUT / "execution_metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")
    mix = namespace["generation_mix"]
    mix_summary = {
        "analysis_date": executed_on, "execution_environment": "Local execution of notebook 03 generation-mix cells",
        "analysis_source_sha256": metadata["analysis_source_sha256"],
        "reported_generation_twh": float(mix.generation_twh.sum()),
        "renewable_share_of_reported_generation": float(mix.loc[mix.classification == "renewable", "share_of_reported_generation"].sum()),
        "wind_solar_share_of_reported_generation": float(mix.loc[mix.generation_source_code.isin(["wind_onshore", "wind_offshore", "solar"]), "share_of_reported_generation"].sum()),
        "denominator": "All observed generation categories including pumped-storage output; nuclear unavailable",
    }
    (OUTPUT / "generation_mix_metadata.json").write_text(json.dumps(mix_summary, indent=2) + "\n")
    evidence = {**notebook, "cells": evidence_cells}
    (OUTPUT / "03_power_market_eda_local.ipynb").write_text(json.dumps(evidence, indent=1) + "\n")
    print(namespace["annual_summary"].round(4).to_string(index=False))
    print(namespace["annual_capture"].round(4).to_string(index=False))
    print(namespace["associations"].round(4).to_string(index=False))
    print(namespace["conditional_associations"].round(4).to_string(index=False))
    print("Local EDA complete; source inputs unchanged and no lakehouse tables written")


if __name__ == "__main__":
    main()
