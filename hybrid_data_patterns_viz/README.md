# Hybrid Data & AI Patterns — how enterprises actually run data across clouds

An interactive, vendor-neutral reference for the question every hybrid architecture discussion starts with and rarely answers cleanly: **where should the boundary cut, and what is allowed to cross it?**

## Live Demo

[View Live Demo](https://johanesalxd.github.io/random-stuff/hybrid_data_patterns_viz/)

## Overview

Most hybrid conversations start from the application tier, where running in two clouds is a deployment choice and the answer is a load balancer. The data and AI tier behaves nothing like that, and importing the app-tier mental model is the most common source of unworkable hybrid designs.

**You cannot put a load balancer in front of a lakehouse.**

This visualization lays out seven patterns that are actually in production somewhere, **ordered by how much data crosses the boundary** — from "none, the data never moves" to "every change, forever". A framing view sets up why the app-tier analogy fails, and a decision view helps place a specific workload.

Every pattern answers the same five questions:

| Panel field | Answers |
| :--- | :--- |
| **One-line** | What is this pattern |
| **What crosses the boundary** | Your cost, latency and risk |
| **Where it breaks** | The honest failure mode, not the brochure |
| **Proof you can check** | A public link you can go read yourself |
| **Maturity** | GA / Preview / regional limits |

"Where it breaks" is a first-class field. A pattern you cannot articulate the failure mode of is a pattern you have not evaluated.

## The nine views

**Framing**

0. **App hybrid is not data hybrid** — stateless replicates, stateful does not. Side-by-side on gravity, egress, consistency, locks, and why the catalog is itself state.

**Patterns** (ordered by how much data crosses)

1. **Read in place** — data never moves; a federated catalog syncs metadata in, an identity handshake vends read credentials, the engine reads the objects directly. *Preview.*
2. **Bring your own engine** — the inverse. Storage and catalog stay central and open; your own engine connects from anywhere over the Iceberg REST API, with optional pushdown. This is where the portability argument is made concretely.
3. **Compute to data** — the managed engine runs inside the remote region; only results return. Strongest containment, hardest availability constraint.
4. **Plane separation** — operational stays put, analytics and AI standardise elsewhere, data moves continuously. Highest sustained volume, simplest to operate.
5. **Domain separation** — the boundary follows the org chart. Data products cross, raw tables don't. Discovery federates; **enforcement does not**.
6. **Edge and on-premises** — not every boundary is between two public clouds. Private connectivity, local processing, and the real difference between "connected" and "air-gapped".
7. **Serving seam** — dual-speed. The only pattern where latency, not volume, is the binding constraint.

**Decide**

8. **Which pattern am I?** — access pattern × data gravity → federate / materialise / move once / co-locate, with the two patterns that sit outside the grid.

## The visual encoding

| Axis | Meaning |
| :--- | :--- |
| **Zones** | brown = edge / on-prem · orange = other cloud · blue = Google Cloud |
| **Fill** | solid = primary in this pattern · dimmed = available but not the point · grey = not used here |
| **Seam** | the vertical band between zones — its label changes per pattern and states what actually crosses |
| **Lines** | blue = primary flow · orange = local to that cloud · dashed blue = optional / return path · dashed green = metadata and identity |
| **Text** | `*` = Preview or limited availability |
| **Evidence chip** | `Customer-proven` = named public reference · `Runnable code` = working repo · `Docs only` = documented capability, not proof that anyone runs it |

AWS is drawn as the second cloud because the public references use it. Every pattern applies equally to another provider.

The evidence chip is deliberately a separate axis from the GA/Preview chip. A pattern can be GA and unproven, or Preview and already running in production somewhere — those are different questions and conflating them is how architecture decks mislead. There is intentionally **no "recommended pattern" badge**: the whole argument of view 8 is that the unit of decision is the workload, so recommendations live there, conditioned on the workload, rather than as a global endorsement.

## Grounded sources

All claims are traceable to public documentation or published customer references. Grounded as of **20 August 2026**.

### Customer references (all publicly published)

- **talabat** — [Fresher insights, faster decisions: talabat's near-real-time analytics across AWS and Google Cloud](https://aws.amazon.com/blogs/big-data/fresher-insights-faster-decisions-talabats-near-real-time-analytics-across-aws-and-google-cloud/) (AWS Big Data Blog). Under 5 minutes freshness for 95% of events, down from 60–90 minutes; approximately 40% lower data-movement cost; one Iceberg copy read by BigQuery, Athena and Spark. Also documents the pattern they **abandoned** — cross-cloud writes on the streaming hot path — which is the most useful part.
- **Traveloka** — [Journey to stream analytics on Google Cloud](https://cloud.google.com/blog/products/gcp/travelokas-journey-to-stream-analytics-on-google-cloud-platform) and [case study](https://cloud.google.com/customers/traveloka). An explicit cross-cloud AWS–GCP design: DynamoDB operational store, Pub/Sub ingestion, Dataflow stream processing, BigQuery warehouse. **Published August 2017.** The shape has aged well and every service in it is still current, but this is the most widely adopted pattern in the deck resting on the oldest citation — the strongest single improvement anyone could make here is a newer named plane-separation reference.
- **Deutsche Telekom** — [Engineering Deutsche Telekom's sovereign data platform](https://cloud.google.com/blog/topics/customers/engineering-deutsche-telekoms-sovereign-data-platform). Iceberg chosen after POCs as one source of truth serving Python, Spark and SQL; 200+ source systems in six months; one live use case measured **22x** over its legacy predecessor. Note this is a **sovereignty** story, not a multi-cloud one — it is cited here for the open-format and polyglot-engine argument.

Patterns **3, 5, 6 and 7 have no citable public customer reference.** That is stated on each of those panels rather than left for the reader to infer from a list of product docs. The published BigQuery Omni customer stories are anonymised, and edge and sovereign deployments are rarely written up at all.

### Runnable references

- **[bq-cross-cloud-lakehouse](https://github.com/johanesalxd/bq-cross-cloud-lakehouse)** — working implementation of pattern 1: keyless OIDC `AssumeRoleWithWebIdentity` with credential vending, reading AWS S3 and Glue Iceberg tables directly from BigQuery.
- **[spark-hybrid-compute](https://github.com/johanesalxd/spark-hybrid-compute)** — working implementation of pattern 2: Iceberg on the Lakehouse runtime catalog (BigLake Metastore when the repo was written) from both a Dataproc cluster and plain Docker locally, including pushing computation down to BigQuery.

### Google Cloud documentation

- [Set up borderless Lakehouse for AWS Glue](https://docs.cloud.google.com/lakehouse/docs/set-up-borderless-lakehouse-aws-glue) — trust policy, credential vending, refresh interval, Cross-Cloud Interconnect routing
- [Introduction to BigQuery Omni](https://docs.cloud.google.com/bigquery/docs/omni-introduction) — architecture, region pairings, limitations
- [Patterns for connecting other CSPs with Google Cloud](https://docs.cloud.google.com/architecture/patterns-for-connecting-other-csps-with-gcp)
- [Knowledge Catalog](https://docs.cloud.google.com/dataplex/docs/introduction) *(was Dataplex Universal Catalog)* · [BigQuery sharing](https://docs.cloud.google.com/bigquery/docs/analytics-hub-introduction) *(was Analytics Hub)*
- [Google Distributed Cloud overview](https://docs.cloud.google.com/distributed-cloud/hosted/docs/latest/gdcag/overview) · [GDC air-gapped appliance](https://docs.cloud.google.com/distributed-cloud/hosted/docs/latest/appliance/overview)
- [Storage Transfer Service](https://docs.cloud.google.com/storage-transfer/docs/overview) · [Bigtable](https://docs.cloud.google.com/bigtable/docs/overview) · [Feature Store on Gemini Enterprise Agent Platform](https://docs.cloud.google.com/gemini-enterprise-agent-platform/machine-learning/featurestore/latest/overview) *(Vertex AI Feature Store (Legacy) sunsets 17 Feb 2027 — do not build on it)*

## Caveats worth reading before you present this

Three claims are commonly made about hybrid data architecture that this reference deliberately does **not** make.

1. **"Caching means zero ongoing egress."** Local caching helps a *stable* working set. It does nothing for first reads, cache misses, or partitions that keep landing. Read-in-place is **one storage copy, not zero transfer** — the query bytes still cross. Where reads genuinely repeat, materialising a curated slice pays the transfer once per refresh instead of once per query, which is replication with extra steps and belongs in pattern 4's territory.

2. **"A single control plane governs both clouds."** Catalog federation synchronises metadata *inbound* and is read-oriented. It does not propagate policy in either direction. Classifications, column- and row-level rules, masking and grants are redefined at the destination and kept in step by process. Plan for **one enforcement point per platform**.

3. **"Air-gapped, and it syncs to the cloud."** Connected and air-gapped are different products. An uplink from an air-gapped deployment is a contradiction. Check the local AI service list before promising edge inference — the air-gapped appliance ships OCR, Speech-to-Text and Translate plus a deep-learning container, not the full cloud model catalogue.

Preview status and regional availability move. Re-check both before designing against them — particularly borderless Lakehouse (Preview) and BigQuery Omni's region pairings, which exclude several major regions.

## Technical details

Single self-contained `index.html`. No build step, no dependencies, no network calls. Roughly 700 lines including all content.

- **Stage** — CSS Grid, three zones (edge / cloud A / cloud B) with a seam band spanning the content rows. Every grid child is explicitly placed by row and column: the edge and other-cloud zones share column 2 and are never shown together, the seam is pinned to column 3, and Google Cloud occupies column 4. Relying on auto-placement here lets a cells group collide with the seam's reserved column whenever a zone is hidden.
- **Three render modes** — `compare` (view 0), `topology` (views 1–7), `matrix` (view 8).
- **Wires** — SVG bezier overlay computed from live element geometry, so it survives resize and reflow. Routing is obstacle-aware: each edge proposes several candidate paths (direct, then via the row gutter above or below for cross-zone edges, or a vertical lane either side for same-zone ones) and the first one that passes through no intervening lit cell or the seam caption is drawn. Dimmed cells are deliberately not treated as obstacles — at opacity 0.2 they read as background, and routing around them would contort paths for no visual gain.
- **Panel** — driven entirely from the `S` scenario object; add a pattern by adding one entry.

## Local development

```bash
cd hybrid_data_patterns_viz
python3 -m http.server 8000
# http://localhost:8000
```

Or just open `index.html` directly — there is nothing to serve.

## Deployment

Served by GitHub Pages from the repository root (`.nojekyll` is present), at `/random-stuff/hybrid_data_patterns_viz/`.

## Related

- **[bq_dbx_gcp_viz](../bq_dbx_gcp_viz/)** — the same interaction model applied to running Databricks and open engines on Google Cloud
- **[bq_dbx_scaling_viz](../bq_dbx_scaling_viz/)** — serverless vs self-managed scaling behaviour
