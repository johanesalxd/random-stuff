# Open Data Platform — Databricks on Google Cloud Visualization

An interactive visualization of how **Databricks and open engines run on Google Cloud**, stepping from a Databricks-only stack to a GCP-native one **without lock-in** — one open dataset, many engines.

## Live Demo

[View Live Demo](https://johanesalxd.github.io/random-stuff/bq_dbx_gcp_viz/)

## Overview

The diagram is a layered capability matrix (UX → Engines → Catalog → Storage → Process, on the shared AI Hypercomputer foundation). Selecting a scenario traces one path through the layers, showing who owns each step and how the open catalog (Knowledge Catalog / Iceberg REST) keeps data portable across engines and clouds.

The core message: **data lands once as open Iceberg on GCS, governed by an open catalog, so any engine — BigQuery, Serverless Spark, or Databricks — can attach to the same tables.** Value can progressively move to GCP-native (BigQuery) while the storage and catalog stay open.

### The four scenarios (orange → blue)

1. **DBX full** — Native Databricks on Google Cloud: UX, compute and Unity Catalog govern Delta/Iceberg on GCS (still on Google's AI Hypercomputer VMs).
2. **DBX led** — Same Databricks experience, but data is written as open Iceberg on GCS with Knowledge Catalog ↔ Unity Catalog sync; GCP serverless engines are available as alternative compute (reachable from a notebook via Spark Connect).
3. **GCP led** — GCP runs the engine layer (BigQuery + Serverless Spark on open Iceberg, governed by Knowledge Catalog); Databricks stays a primary UX, and Databricks engine/UC on other clouds read the same data read-only via the Iceberg REST catalog.
4. **GCP full** — All-GCP: BigQuery + serverless engines + AlloyDB, governed by Knowledge Catalog with Gemini/Antigravity in BQ Studio; the Iceberg REST catalog stays open outward so Databricks on other clouds can still read.

## The visual encoding (2×2 + color)

| Axis | Meaning |
| :--- | :--- |
| **Color** | blue = GCP · yellow = Databricks / non-GCP |
| **Fill** | solid = primary · dimmed = alternative |
| **Border** | solid = available (GA) · dotted = preview / upcoming |
| **Lines** | solid = primary flow · dotted = alternative / optional · green dashed = catalog sync |
| **Text** | *italic ( )* = capability (e.g. serverless) · **VM** = self-managed · *(other CSPs)* = another cloud |

A vertical **Cross-cloud Lakehouse (network)** band spans Catalog→Storage to represent the connectivity layer (off in DBX-full, dimmed in DBX-led, on in the GCP scenarios).

## Features

- **Scenario switcher**: Overview + four scenarios; non-active cells grey out so one path stays in focus.
- **Grounded side panel**: each scenario shows the flow, the narrative, and a docs-grounded note with the honest caveats (what's GA vs Preview, read-only federation, etc.).
- **Self-contained**: pure HTML/CSS/JavaScript, no dependencies, no build step.
- **Responsive**: reflows to a single column on narrower screens; wiring recomputes on resize.

## How to Use

1. Open the page — it starts on **Overview** (the full matrix).
2. Click a scenario button (**DBX full → DBX led → GCP led → GCP full**) to focus one path.
3. Read the side panel for the flow, narrative, and grounded note.
4. Use the legend to decode fill/border/line/color semantics.

## Grounded sources & caveats

Illustrative reference — grounded to Google Cloud & Databricks documentation as of **25 Jul 2026**. Key facts encoded in the diagram:

- **BigQuery managed Iceberg (V2) tables are GA**; the BigQuery Iceberg REST catalog / catalog federation (`bq://`) is **read-only** for external OSS engines (Spark, Trino, Databricks).
- **BigQuery ↔ AlloyDB federated query** via `EXTERNAL_QUERY` + the BigQuery Connection API (BQ Studio path); Gemini reaches AlloyDB via agent / MCP.
- **Serverless for Apache Spark** interactive sessions via **Spark Connect** (`dataproc-spark-connect`) let a notebook (including Databricks) drive GCP compute — works off-GCP with ADC.
- **Cross-cloud Lakehouse** federates **Databricks Unity Catalog** (metadata sync, UC external tables); Databricks reading foreign Iceberg is **read-only with limited support**, and the UC catalog-federation connector for Google Cloud Lakehouse is **Preview** (hence the dotted "Databricks Preview" edges).
- **Pub/Sub → BigQuery Storage Write API** streams into managed Iceberg tables.
- Private-cloud catalog/storage are shown as **upcoming** (dotted); these are directional, not commitments.

## Technical Details

- **Pure HTML/CSS/JavaScript**: single `index.html`, runs entirely in the browser.
- **SVG wiring**: edges and catalog-sync arcs are drawn from an explicit per-scenario edge list and repositioned on resize.
- **No dependencies / no build**.

## Local Development

Simply open `index.html` in a web browser. No build process required.

## Deployment

Deployed via GitHub Pages (folder-based):

1. Settings → Pages
2. Source: Deploy from branch
3. Branch: `main`
4. Folder: `/bq_dbx_gcp_viz`

Live at: `https://[username].github.io/[repo-name]/bq_dbx_gcp_viz/`

## License

MIT License — feel free to use and modify for your own purposes.

## Credits

Based on research of official Google Cloud and Databricks documentation.
