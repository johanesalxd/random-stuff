# Froyo Cross-Cloud Lakehouse — "Midnight Swirl" Agent Demo Rundown

This demo shows how a Froyo brand analyst uses a single **Conversational
Analytics (CA) API** data agent, published to **Gemini Enterprise**, to answer
questions that silently span **Google Cloud** (native allergen/recipe knowledge)
and **AWS** (customer loyalty + sales history in Apache Iceberg) — in one
natural-language conversation, with no data movement between clouds.

> **Rundown structure** follows the canonical template used by the `bq_caapi_ge`
> demos (business + high-level architecture only — **no deployment commands**).
> For deployment, see [`README.md`](README.md). Sections this demo does not cover
> are marked **N/A**.

---

## 1. Executive Overview & Audience

A Froyo commercial/marketing analyst preparing a launch push for the hero product
**Midnight Swirl**. Audience: Google Cloud account teams + data/analytics
leadership evaluating cross-cloud analytics and agentic BI.

**The hook.** One agent answers "what's in this product?", "who should we target?",
and "how is it selling?" — and the target-list answer quietly joins Google-Cloud
allergen knowledge with customer data that physically lives in **AWS S3/Glue**,
inside a single BigQuery query. No replication, no AWS keys stored in Google Cloud.

---

## 2. Business Context & Real-World Research

Froyo's recipe and supplier documents are "dark data" (PDFs). The structured
allergen knowledge extracted from them lives in Google Cloud BigQuery, while the
customer loyalty program and point-of-sale history are operated on AWS. A launch
campaign needs all three at once: the recipe (what's in it), the allergen risk
(who to protect), and the customers/sales (who to target and how it trends).

*External research: N/A — the storyline uses the demo's synthetic, deterministic
seed data so results are reproducible on stage.*

---

## 3. Executive Storyline & Narrative Flow

Ask these in the Gemini Enterprise app using the **Froyo Lakehouse Analyst** agent.

### Step 0 — Warm-up: regional revenue (AWS data, rendered as a chart)
- **Prompt:** *"Show total Midnight Swirl revenue by region, highest first."*
- **What the tech does:** aggregates the AWS-resident `sales_history` Iceberg
  table read cross-cloud from BigQuery; GE renders a chart.
- **Expected:** **APAC** leads, then **EMEA**, then **AMER** (by design in the
  seeded daily series).
- **Talking point:** the very first answer is already reading data that lives in
  AWS — the analyst never leaves the BigQuery/GE surface.

### Step 1 — Dark data → knowledge: allergen discovery (native)
- **Prompt:** *"What allergens are in Midnight Swirl, and which supplier document
  reveals each one?"*
- **What the tech does:** queries the native `product_allergens` view (recipes ×
  ingredient allergen datasheets).
- **Expected:** **Soy**, contributed by the ingredient **Midnight Base 204**,
  supplier *Prestige Molecular Additives*, source
  `midnight_base_204_manual.pdf`.
- **Talking point:** structured knowledge grounded in the original PDFs — the
  agent cites the exact source document.

### Step 2 — Cross-cloud target list (the payoff)
- **Prompt:** *"Build a Midnight Swirl campaign target list from our loyalty
  customers whose favorite flavor is Midnight Swirl, excluding soy-sensitive
  customers. Show customer_id, region, loyalty_tier, and avg_monthly_spend,
  ordered by avg_monthly_spend descending."*
- **What the tech does:** a single BigQuery query joining **native** allergen
  knowledge (`us-east4`) with the **AWS-federated** `global_loyalty` Iceberg
  table, applying the soy-safety rule.
- **Expected:** **8 customers** survive (soy-sensitive Midnight Swirl fans 1002
  and 1010 are excluded). Top of the list: **1006 (EMEA, Platinum, 96.0)** and
  **1009 (AMER, Platinum, 88.3)**.
- **Talking point:** this is the cross-cloud moment — one query, two clouds, no
  copy, no AWS credentials in Google Cloud, and an allergen-safety guardrail
  applied automatically.

### Step 3 — Regional performance & trend (AWS data)
- **Prompt:** *"Which region has the highest total Midnight Swirl revenue over the
  last 12 months, and show the monthly revenue trend per region."*
- **What the tech does:** time-bucketed aggregation over `sales_history`.
- **Expected:** **APAC** highest; an upward trend with weekly seasonality per
  region.
- **Talking point:** the agent does ad-hoc analytics; the deterministic
  `ARIMA_PLUS` **forecast** is a separate scripted step of the demo
  (`gcp/50_forecast_bqml.sh`) — the agent complements it, it doesn't replace it.

### Step 4 — Executive synthesis (grand finale)
- **Prompt:** *"Summarize today's findings into an executive-ready slide outline:
  (1) allergen risk for Midnight Swirl, (2) the cross-cloud soy-safe target list,
  and (3) regional revenue performance. End with a slide on the data governance
  guardrails."*
- **Expected:** a tidy slide outline weaving together the Soy finding, the 8-name
  soy-safe target list, the APAC-led regional revenue, and the security posture.
- **Talking point:** the "mic-drop" — the agent is both analyst and strategic
  partner.

---

## 4. Data Engineering & Design Rationale

Deterministic signals baked into the seed data:

1. **Allergen truth:** Midnight Swirl's recipe includes **Midnight Base 204**,
   whose supplier datasheet declares **Soy** — so any Midnight Swirl targeting
   must exclude `soy_sensitive_flag = TRUE`.
2. **Soy-sensitive fans (excluded):** loyalty customers **1002** and **1010**
   love Midnight Swirl but are soy-sensitive, leaving **8** eligible targets.
3. **Regional revenue skew:** the synthesized daily `sales_history` adds a
   per-region base offset (**APAC +20, EMEA +10, AMER +0**) on top of an upward
   trend and weekly seasonality, so **APAC** is always the revenue leader.

---

## 5. Technical Architecture & Setup

Six objects, spanning two clouds, joined in one BigQuery query surface:

**Native BigQuery (`froyo_demo_ue4`, `us-east4`):**
- `products` — product_id, product_name, category, launch_date, status
- `recipes` — product_id, product_name, ingredient_id, ingredient_name, quantity_g
- `ingredient_allergens` — ingredient_id, ingredient_name, allergen, supplier, source_doc
- `product_allergens` (view) — product_id, product_name, allergen, ingredient_name, supplier, source_doc

**AWS-federated Iceberg (`demo_glue_cat.froyo_lakehouse`, physically in AWS S3/Glue):**
- `global_loyalty` — customer_id, region, loyalty_tier, favorite_flavor, avg_monthly_spend, soy_sensitive_flag, last_order_date
- `sales_history` — sale_date, product_name, region, units_sold, revenue

The agent references the federated tables with the CA API four-part **P.C.N.T**
syntax (`dataset_id = demo_glue_cat.froyo_lakehouse`). Cross-cloud reads use
BigLake OIDC trust + short-lived vended S3 credentials — no persistent copy, no
AWS keys in Google Cloud. *(Illustrative; not run commands.)*

---

## 6. Deployment

Deployment steps (install → create agent → register in GE → validate) live in the
technical runbook: **[`README.md`](README.md)**. Configuration is read from the
demo's `../config.local.env` plus this package's `.env`.

**Before the demo:** if the agent answers in BigQuery Studio but every Gemini
Enterprise chat fails with `A2A request failed: async generator raised
StopAsyncIteration`, re-register it — the stored A2A card is frozen at
registration time and may carry declarations GE cannot negotiate. See
[A2A card compatibility](README.md#a2a-card-compatibility-gemini-enterprise).

---

## 7. 10-Minute C-Level Presentation Guide

Run Steps 0 → 4 in order (~2 minutes each). Open on the AWS-backed revenue chart
(Step 0) to establish cross-cloud immediately, land the payoff at Step 2
(one-query, two-cloud, soy-safe target list), and close on Step 4's executive
synthesis and governance slide.

---

## 8. Enterprise Readiness & FAQ / Security

1. **Per-user OAuth passthrough** — Gemini Enterprise routes each request with the
   signed-in user's token; SQL runs with that user's BigQuery/BigLake permissions.
2. **No AWS keys in Google Cloud** — cross-cloud reads use OIDC trust and
   short-lived vended credentials, scoped to the demo's bucket and Glue account.
3. **No replication** — AWS data is read in place at query time; nothing is copied
   into Google Cloud.
4. **Contextual isolation** — the agent is scoped to exactly these six objects,
   reducing hallucination and over-broad access.
5. **Allergen guardrail** — the soy-exclusion rule is encoded in the agent's
   instructions so customer-safety logic is applied consistently.
6. **Automated metadata is already there** — BigQuery + Knowledge Catalog can
   auto-generate data profiles, table/column documentation, and lineage for these
   tables via Dataplex ([`scripts/enrich_bigquery_metadata.py`](README.md#metadata-enrichment-showcase)).
   Show the **Insights** tab on a native table (full column descriptions) next to
   a federated Glue-catalog table (profile, insights, and lineage, but no
   schema-level column descriptions — the external Iceberg schema is read-only to
   BigQuery DDL). The talking point: the components already exist; feeding this
   catalog metadata into the agent's context is the remaining wiring, not new
   engineering.
