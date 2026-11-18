# Preservation status — 18 November 2026

## Retained independently of Fabric capacity

- The original three public SMARD CSV files, their source dictionary and hashes.
- The profiling, silver, exploration and gold notebook source definitions, plus the shared source-validation helper.
- Authentic executed Fabric notebook exports with outputs for all four current notebooks, under [evidence/fabric_runs/2026-11-18](../evidence/fabric_runs/2026-11-18/). All 31 code cells executed successfully and retain outputs. The [inventory](../evidence/fabric_runs/output_inventory.json) distinguishes these from output-free source exports and independent local execution evidence.
- The historical combined notebook and HTML export, retained unchanged.
- The five-page native PBIR report, TMDL semantic model, relationships, core and presentation measures, source colours/icons and lakehouse item metadata.
- Existing report screenshots and numerical controls, together with the public SVG web counterpart and its validated 8,760-hour snapshot. The web snapshot was derived from source CSVs; it is not a direct OneLake export.
- Public-site analytical tests covering headline controls, filters, missing-value rules, physical DST hours, correlations and all 624 hourly-profile groups.
- [Physical OneLake archive](../evidence/onelake/README.md): nine original Delta directories with transaction logs, version-pinned Parquet snapshots, schemas, history and file hashes. All 2,530 payload files verified; every current Delta table reopened locally and every row compared with its Parquet snapshot. Fabric's unavailable auxiliary virtual Iceberg metadata is explicitly excluded and recorded.
- [Original Power BI PDF and silent walkthrough](../evidence/powerbi/archive_2026-11-18/): all five default-value pages exported directly to PDF, visually checked; approximately 57-second sampled browser walkthrough covers all pages and filters. Capture method and its frame-rate limitations are documented.
- The authentic executed `05_archive_onelake` notebook, retaining the successful physical-export output. Its completed Spark session has expired.

## Still dependent on, or not exported from, Fabric

**Full workspace restoration.** Physical silver/gold data is now archived independently of OneLake and locally verified. Live SQL endpoints, workspace configuration and identities are not restored by copying Delta files. The auxiliary virtual Iceberg metadata was not backed up; the current Delta snapshots were verified without it. Older retained Delta versions were not individually tested.

**Offline Power BI package.** Native PBIR/TMDL definitions are retained. An independently opened, data-containing Import-mode PBIX has not been archived or validated. A thin Direct Lake report package alone would still depend on the unavailable lakehouse.

**Continuous screen recording.** The saved MP4 is an actual sampled browser walkthrough with compressed idle gaps, not a high-frame-rate desktop recording; native QuickTime recording failed. The direct PDF and independent interactive HTML/SVG counterpart are both retained.

**Pipeline execution.** No Data Factory pipeline was created or executed in this project; no pipeline-run evidence is claimed. The notebook build flow is versioned.

**Permissions and credentials.** No personal Tibber records, tokens, Fabric authentication credentials or reusable connection secrets belong in the public archive. Live identities and permissions are not preserved as portable credentials.

## Trial retention boundary

Microsoft states that trial capacity access ends on expiry and non-Power-BI Fabric items become unavailable without supported paid capacity; its documented OneLake retention window is seven days. That window is not treated here as a backup strategy. See [Fabric trial capacity](https://learn.microsoft.com/en-us/fabric/get-started/fabric-trial).

Fabric Git integration excludes notebook cell outputs; see [Notebook source control and deployment](https://learn.microsoft.com/en-us/fabric/data-engineering/notebook-source-control-deployment). The separately downloaded execution exports above address that gap.
