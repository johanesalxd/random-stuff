# Open Data Platform — Databricks on Google Cloud Visualization

An interactive visualization of how **Databricks and open engines run on Google Cloud**, stepping from a Databricks-only stack to a GCP-native one **without lock-in** — one open dataset, many engines.

## Live Demo

[View Live Demo](https://johanesalxd.github.io/random-stuff/bq_dbx_gcp_viz/)

## Overview

The diagram is a layered capability matrix (UX → Engines → Catalog → Storage → Process, on the shared AI Hypercomputer foundation). Selecting a scenario traces one path through the layers, showing who owns each step and how the open catalog (Knowledge Catalog / Iceberg REST) keeps data portable across engines and clouds.

The core message: **data lands once as open Iceberg on GCS, governed by an open catalog, so any engine — BigQuery, Serverless for Apache Spark, or Databricks — can attach to the same tables.** Value can progressively move to GCP-native (BigQuery) while the storage and catalog stay open.

### The four scenarios (orange → blue)

1. **DBX full** — Native Databricks on Google Cloud: UX, compute and Unity Catalog govern Delta (GA) / Iceberg (Databricks Preview, marked `*`) on GCS (still on Google's AI Hypercomputer VMs).
2. **DBX led** — Same Databricks experience, but data is written as open Iceberg on GCS with Knowledge Catalog ↔ Unity Catalog sync; GCP serverless engines are available as alternative compute (reachable from a notebook via Spark Connect).
3. **GCP led** — GCP runs the engine layer (BigQuery + Serverless for Apache Spark on open Iceberg, governed by Knowledge Catalog); Databricks stays a primary UX, and Databricks engine/UC on other clouds read the same data read-only via the Iceberg REST catalog.
4. **GCP full** — All-GCP: BigQuery + serverless engines + AlloyDB, governed by Knowledge Catalog with Gemini/Agent Engine in BQ Studio; AlloyDB also reads analytical Iceberg via Lakehouse Federation / BigQuery Views (Preview); the Iceberg REST catalog stays open outward so Databricks on other clouds can still read.

## Assumptions & scope

This map shows **what runs inside — and is owned within — your Google Cloud tenant.** Databricks is therefore modeled as **self-managed**: classic compute (SQL warehouses / job clusters) provisioned on **GCE VMs in your own project / VPC**, so you own the capacity, autoscaling policy, networking, and cost.

**Databricks Serverless is intentionally out of scope.** Per Databricks' own [high-level architecture](https://docs.databricks.com/aws/en/getting-started/high-level-architecture), serverless compute runs in a **Databricks-managed serverless compute plane inside the Databricks account** — not your Google Cloud tenant. Its scaling, capacity, and networking are governed by the **Databricks control plane, not by you**: it isn't a resource you provision, size, or place in your VPC. Because this diagram is about **ownership and control on Google Cloud**, serverless Databricks falls outside the boundary. (Its scaling mechanics are covered in the companion **scaling viz**.)

## The visual encoding (2×2 + color)

| Axis | Meaning |
| :--- | :--- |
| **Color** | blue = GCP · yellow = Databricks / non-GCP |
| **Fill** | solid = primary · dimmed = alternative |
| **Lines** | solid = primary flow · dotted = alternative / optional · green dashed = catalog sync |
| **Badges** | green **serverless** = serverless / managed service · red **self-managed** = self-managed compute (VMs in your tenant) |
| **Text** | *italic ( )* = capability · `*` = preview / upcoming · *(other CSPs)* = another cloud |

Preview / upcoming items are marked with a trailing `*` (e.g. Databricks Iceberg output, AlloyDB↔Iceberg, private-cloud catalog/storage) rather than a border style — every box uses a solid border.

A vertical **Cross-cloud Lakehouse · AWS + Azure · interconnect + caching** band spans Catalog→Storage to represent the connectivity layer (off in DBX-full and DBX-led — no other cloud is active — and dimmed-blue "alternative" in the GCP scenarios).

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

- **BigQuery managed Iceberg (V2) tables are GA**; the BigQuery Iceberg REST catalog / catalog federation (`bq://`) is **read-only** for external OSS engines (Spark, Trino, Databricks), read-write from BigQuery.
- **BigQuery ↔ AlloyDB federated query** via `EXTERNAL_QUERY` + the BigQuery Connection API (BQ Studio path, GA); Gemini reaches AlloyDB via agent / MCP.
- **AlloyDB ↔ Iceberg** via Lakehouse Federation / BigQuery Views (AlloyDB reads analytical Iceberg) and BigQuery reverse-ETL back into AlloyDB are **Preview** (marked `*`).
- **Serverless for Apache Spark** interactive sessions via **Spark Connect** (`dataproc-spark-connect`) let a notebook (including Databricks) drive GCP compute — works off-GCP with ADC.
- **Cross-cloud Lakehouse** connects Google Cloud to **remote Iceberg REST catalogs — AWS Glue and Databricks Unity Catalog** — to query other-cloud data (AWS S3 / Azure ADLS) without copying, via cross-cloud interconnect + intelligent caching; bidirectional federation is **Preview**. Databricks reading GCP's open Iceberg is **read-only foreign Iceberg** (still **Databricks Preview**, marked `*`).
- **Pub/Sub → BigQuery Storage Write API** streams into managed Iceberg tables.
- **Knowledge Catalog** is the current name for the governance/catalog layer (formerly Dataplex Universal Catalog).
- **Databricks compute planes**: classic compute runs in the **customer VPC** (self-managed, in scope); **serverless** compute runs in a **Databricks-managed plane inside the Databricks account** ([docs](https://docs.databricks.com/aws/en/getting-started/high-level-architecture)) — not the customer's tenant, so it's out of scope for this ownership map.
- Private-cloud catalog/storage are shown as **upcoming** (`*`); these are directional, not commitments.

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
