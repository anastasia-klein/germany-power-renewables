# Preservation status — 18 November 2026

## Retained independently of Fabric capacity

- The original three public SMARD CSV files, their source dictionary and hashes.
- The profiling, silver, exploration and gold notebook source definitions, plus the shared source-validation helper.
- Authentic executed Fabric notebook exports with outputs for all four current notebooks, under [evidence/fabric_runs/2026-11-18](../evidence/fabric_runs/2026-11-18/). All 31 code cells executed successfully and retain outputs. The [inventory](../evidence/fabric_runs/output_inventory.json) distinguishes these from output-free source exports and independent local execution evidence.
- The historical combined notebook and HTML export, retained unchanged.
- The five-page native PBIR report, TMDL semantic model, relationships, core and presentation measures, source colours/icons and lakehouse item metadata.
- Existing report screenshots and numerical controls, together with the public SVG web counterpart and its validated 8,760-hour snapshot. The web snapshot was derived from source CSVs; it is not a direct OneLake export.
- Public-site analytical tests covering headline controls, filters, missing-value rules, physical DST hours, correlations and all 624 hourly-profile groups.

## Still dependent on, or not exported from, Fabric

**Physical lakehouse data backup.** Git stores lakehouse definitions and metadata, not the silver/gold Delta files or `_delta_log` history. A direct Parquet/Delta export of the silver and gold tables would preserve the exact materialized lakehouse snapshot. The original data and build logic are retained for reconstruction, but this archive does not claim to contain the physical OneLake tables.

**Offline Power BI package.** Native PBIR/TMDL definitions are retained. An independently opened, data-containing Import-mode PBIX has not been archived or validated. A thin Direct Lake report package alone would still depend on the unavailable lakehouse.

**Walkthrough recording and PDF.** Static report screenshots are retained. A complete walkthrough video and a PDF export of all report pages have not been captured in this preservation pass. The live HTML/SVG counterpart remains independently usable.

**Pipeline execution.** No Data Factory pipeline was created or executed in this project; no pipeline-run evidence is claimed. The notebook build flow is versioned.

**Permissions and credentials.** No personal Tibber records, tokens, Fabric authentication credentials or reusable connection secrets belong in the public archive. Live identities and permissions are not preserved as portable credentials.

## Trial retention boundary

Microsoft states that trial capacity access ends on expiry and non-Power-BI Fabric items become unavailable without supported paid capacity; its documented OneLake retention window is seven days. That window is not treated here as a backup strategy. See [Fabric trial capacity](https://learn.microsoft.com/en-us/fabric/get-started/fabric-trial).

Fabric Git integration excludes notebook cell outputs; see [Notebook source control and deployment](https://learn.microsoft.com/en-us/fabric/data-engineering/notebook-source-control-deployment). The separately downloaded execution exports above address that gap.
