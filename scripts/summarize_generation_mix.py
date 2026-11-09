"""Summarize all reported generation categories without treating missing nuclear as zero."""

import csv
import json
from decimal import Decimal
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.patches import Patch


ROOT = Path(__file__).resolve().parents[1]
RENEWABLES = {"Biomass", "Hydropower", "Wind offshore", "Wind onshore", "Photovoltaics", "Other renewable"}


def main():
    source = ROOT / "data/raw/smard/Actual_generation_202501010000_202601010000_Hour.csv"
    with source.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle, delimiter=";")
        columns = reader.fieldnames[2:]
        rows = list(reader)
    totals = {}
    for column in columns:
        valid = [Decimal(row[column].replace(",", "")) for row in rows if row[column] != "-"]
        totals[column] = sum(valid) if valid else None
    denominator = sum(value for value in totals.values() if value is not None)
    records = []
    for column, total in totals.items():
        name = column.split(" [MWh]")[0]
        records.append({
            "generation_source": name,
            "classification": "renewable" if name in RENEWABLES else "storage_output" if name == "Hydro pumped storage" else "other_generation",
            "valid_hours": sum(row[column] != "-" for row in rows),
            "generation_twh": float(total / Decimal(1000000)) if total is not None else None,
            "share_of_reported_generation": float(total / denominator) if total is not None else None,
        })
    frame = pd.DataFrame(records)
    output = ROOT / "evidence/eda_2025"
    frame.to_csv(output / "generation_mix.csv", index=False, float_format="%.10f")
    assert abs(frame.share_of_reported_generation.sum() - 1) < 1e-12
    assert frame.loc[frame.generation_source == "Nuclear", "generation_twh"].isna().all()
    plotted = frame.dropna(subset=["generation_twh"]).sort_values("generation_twh")
    colors = {"renewable": "#22836c", "storage_output": "#2563eb", "other_generation": "#64748b"}
    fig, ax = plt.subplots(figsize=(10, 6.8), constrained_layout=True)
    bars = ax.barh(plotted.generation_source, plotted.generation_twh, color=plotted.classification.map(colors))
    ax.bar_label(bars, fmt="%.2f", padding=4, fontsize=9)
    ax.set_xlim(0, plotted.generation_twh.max() * 1.17)
    ax.set_xlabel("Reported net generation (TWh)")
    ax.set_title("Germany: reported generation by source, 2025\nNuclear unavailable in this export; not plotted as measured zero", loc="left", pad=16)
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.grid(axis="x", alpha=0.15)
    ax.set_axisbelow(True)
    ax.legend(handles=[Patch(color=colors[key], label=label) for key, label in [
        ("renewable", "Renewable"), ("other_generation", "Other reported generation"), ("storage_output", "Pumped-storage output")
    ]], loc="lower right", frameon=False, fontsize=8)
    fig.savefig(output / "generation_mix.png", dpi=160, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    wind_solar = sum(total for column, total in totals.items() if column.split(" [MWh]")[0] in {"Wind onshore", "Wind offshore", "Photovoltaics"})
    renewable_total = sum(total for column, total in totals.items() if column.split(" [MWh]")[0] in RENEWABLES)
    summary = {
        "analysis_date": "2026-11-09", "execution_environment": "Local Python; supplemental source summary",
        "reported_generation_twh": float(denominator / Decimal(1000000)),
        "renewable_share_of_reported_generation": float(renewable_total / denominator),
        "wind_solar_share_of_reported_generation": float(wind_solar / denominator),
        "denominator": "All observed source categories, including pumped-storage output; nuclear unavailable",
    }
    (output / "generation_mix_metadata.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(frame.round(4).to_string(index=False))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
