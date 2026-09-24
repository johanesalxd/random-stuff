# Google Cloud Data Contracts: Real-Time Streaming & Storage Governance

[![Open Data Contract Standard](https://img.shields.io/badge/Standard-ODCS%20v3.0-blue.svg)](https://bitol.io/odcs/)
[![Google Cloud](https://img.shields.io/badge/Google%20Cloud-Pub%2FSub%20%7C%20BigQuery%20%7C%20Dataplex-4285F4.svg)](https://cloud.google.com)
[![Status](https://img.shields.io/badge/Status-Production%20Ready-success.svg)]()
[![License](https://img.shields.io/badge/License-Apache%202.0-green.svg)](LICENSE)

An enterprise-grade reference architecture demonstrating **Shift-Left Data Contracts** on Google Cloud Platform. This solution models an electronic stock brokerage / capital markets trading platform, enforcing contracts across four synchronized tiers: **Wire Ingress**, **Storage Write**, **Serverless Data Quality SLAs**, and **Enterprise Catalog Governance**.

> [!TIP]
> **Executive Presentation Deck (Marp):**
> A 10-slide executive walkthrough deck featuring the 4-Gate architecture diagram, regulatory compliance mappings, and demo guide is available in [`slides/data-contracts-presentation.md`](./slides/data-contracts-presentation.md) (with pre-compiled [Interactive HTML](./slides/data-contracts-presentation.html) and [PDF Deck](./slides/data-contracts-presentation.pdf)). See [`slides/README.md`](./slides/README.md) for details.

---

## 🏛️ Executive Summary & The "Shift-Left" Paradigm

In high-throughput financial systems, data quality issues traditionally manifest as **silent semantic corruption**: an upstream trading service renames an attribute, publishes malformed types, or drops a broker identifier. Downstream, risk models miscalculate margin requirements, clearing jobs fail in the middle of the night, and institutions face regulatory penalties.

```
+------------------------------------+    +------------------------------------+
|   TRADITIONAL: REACTIVE & FRAGILE  |    | TARGET: SHIFT-LEFT DATA CONTRACTS  |
|                                    |    |                                    |
| [Trading Engine]                   |    | [Trading Engine]                   |
|        │ (Silent Schema Drift)     |    |        │ (ODCS v3.0 Contract)      |
|        ▼                           |    |        ▼                           |
| [Dirty Data in Storage]            |    | [Perimeter Ingress Gate]           |
|        │                           |    |   * Synchronous Rejection (400)    |
|        ▼                           |    |        │                           |
| [Downstream Pipeline Fails]        |    |        ▼                           |
| [Clearing / Risk Corrupted]        |    | [Storage Write API + DLQ]          |
| [Regulatory Fines & Incident Fire] |    | [Dataplex Auto Data Quality Scans] |
|                                    |    | [Knowledge Catalog Governance]     |
| Cost: High MTTD, Broken Analytics  |    | Result: Shift-Left Protection, Provable|
+------------------------------------+    +------------------------------------+
```

### The Solution: 4 Defense-in-Depth Enforcement Gates

1. **Wire Ingress Gate (Google Cloud Pub/Sub Schema Registry)**:
   Synchronously validates incoming event streams against an authoritative Apache Avro schema. Payloads violating structural types, missing required attributes, or presenting unrecognized enum states are rejected at the network perimeter with HTTP `400 INVALID_ARGUMENT`.
2. **Storage Ingestion Gate (BigQuery Direct Subscription & Storage Write API)**:
   High-throughput streaming writes directly into BigQuery without intermediary worker compute. Messages failing storage-level type conversion or database schema constraints are automatically routed to a **Dead-Letter Queue (DLQ)** for inspection, leaving the main ingestion highway unblocked.
3. **Storage Quality SLA Gate (Dataplex Auto Data Quality DataScan)**:
   Serverless quality scans evaluate batch and partition health directly against the storage layer using isolated serverless Dataplex compute. Evaluates Freshness SLAs (latency <= 2h), Completeness (non-null constraints), Range validity, and Custom SQL Business Rules (Anti-Wash Trading: `buyer_id != seller_id`).
4. **Enterprise Governance Gate (Dataplex Knowledge Catalog)**:
   Certifies data assets with versioned contract aspect metadata (criticality tiers, SLAs, and regulatory compliance standards like FINRA, SEC, and MAS TRM Section 8) in Knowledge Catalog.

---

## 🏗️ Architecture

```
                            [ Equity Trade Producers ]
                                         │
                 (1) Wire-Level Ingress  │ UTF-8 Flat JSON Payload
                     Contract Gate       ▼
          ┌────────────────────────────────────────────────────────┐
          │ Google Cloud Pub/Sub Topic: equity-trades-topic        │
          │ Bound Schema: schemas/trade_event_v1.avsc (AVRO)       │
          │ Encoding: JSON                                         │
          │ (Rejects malformed JSON / types with HTTP 400 INVALID) │
          └──────────────┬───────────────────────────┬─────────────┘
                         │                           │
    (2) Storage Ingestion│                           │ Delivery failures
        Contract Gate    ▼                           ▼ (Max 5 attempts)
        ┌───────────────────────────────┐   ┌───────────────────────────────┐
        │ BigQuery Direct Subscription  │   │ Dead Letter Topic (DLQ)       │
        │ Storage Write API             │   │ equity-trades-dlq-topic       │
        │ --use-table-schema            │   │ (Quarantines un-insertable    │
        │ --write-metadata              │   │  storage-contract failures)   │
        └───────────────┬───────────────┘   └───────────────────────────────┘
                        │
                        ▼
        ┌────────────────────────────────────────────────────────┐
        │ BigQuery Table: market_data.equity_trades              │
        │ Daily Partitioning: DATE(trade_timestamp)              │
        │ Clustering: instrument_code, trade_status              │
        │ Physical Constraints: NOT NULL on 8 core columns       │
        └───────────────────────────────┬────────────────────────┘
                                        │
                   (3) Storage SLA Gate │ Scheduled / On-Demand
                       Quality Scans    ▼
        ┌────────────────────────────────────────────────────────┐
        │ Dataplex Auto Data Quality DataScan                    │
        │ Spec: config/dataplex_dq_spec.yaml                     │
        │ - Rule 1 (Freshness SLA): trade_timestamp <= 2 hours   │
        │ - Rule 2 (Completeness): trade_id, ticker, price, vol  │
        │ - Rule 3 (Validity/Range): price > 0, volume > 0       │
        │ - Rule 4 (Integrity SQL): buyer_id != seller_id        │
        └───────────────┬───────────────────────────┬────────────┘
                        │                           │
                        ▼                           ▼
        ┌───────────────────────────────┐   ┌───────────────────────────────┐
        │ Executive Scorecard SQL Views │   │ Dataplex Knowledge Catalog    │
        │ sql/query_executive_scorecard │   │ Data Product & Contract       │
        │ (RAG status, SLA violations)  │   │ Custom Aspect Types           │
        └───────────────────────────────┘   └───────────────────────────────┘
```

---

## 📁 Repository Structure

```
gcp-data-contracts/
├── contract.odcs.yaml                  # Authoritative Open Data Contract Standard (ODCS v3.0)
├── compile_contract.py                 # Pure Python + PyYAML compiler (CLI with --check drift verification)
├── schemas/
│   └── trade_event_v1.avsc             # Compiled Apache Avro schema for Pub/Sub Schema Registry
├── sql/
│   ├── create_trades_table.sql         # Partitioned/clustered BigQuery DDL with Storage Write API audit columns
│   ├── create_dq_export_results_table.sql # DDL for Dataplex Auto DQ export results table
│   ├── create_v_dq_rule_summary.sql    # View computing compliance % across quality dimensions
│   └── query_executive_scorecard.sql   # Executive KPI dashboard queries (RAG status, forensics)
├── config/
│   ├── dataplex_dq_spec.yaml           # Dataplex Auto DQ YAML specification (9 evaluation rules)
│   ├── aspect_contract_template.yaml   # Dataplex Aspect Type definition for Data Product governance
│   └── table_aspect_payload.yaml       # Aspect attachment payload for BigQuery entry
├── scripts/
│   ├── publish_events.py               # Dual-engine streaming producer (valid, perimeter defense, DLQ modes)
│   └── run_dataplex_scan.py            # Dataplex DataScan runner & executive scorecard reporter
├── setup.sh                            # Idempotent 11-step GCP infrastructure provisioning script
├── run_demo.sh                         # Turnkey 7-stage automated demonstration runner
├── cleanup.sh                          # Clean reverse-dependency infrastructure teardown script
├── DEMO_GUIDE.md                       # 10-Slide executive presentation & speaker guide (with Q&A)
└── tests/                              # Comprehensive defense-in-depth test suite (Tiers 1–5)
```

---

## ⚡ Quickstart

### Prerequisites
* **Python 3.9+** with `pyyaml` (`pip install pyyaml`)
* **Google Cloud SDK (`gcloud`)** installed and authenticated (for live cloud deployment)
* Active GCP project with permissions for BigQuery, Pub/Sub, and Dataplex

---

### Option A: 60-Second Offline Simulation (No GCP Project Required)

Experience the entire 7-stage contract lifecycle instantly without creating any cloud resources:

```bash
# Clone the repository
git clone https://github.com/your-org/gcp-data-contracts.git
cd gcp-data-contracts

# Run simulated end-to-end demo
./run_demo.sh --simulated
```

What the simulation demonstrates:
1. **Compiles ODCS contract** into Avro schema, BigQuery DDL, and Dataplex DQ spec.
2. **Streams conforming equity trades** across global equities (`AAPL`, `GOOGL`, `MSFT`, `NVDA`, `AMZN`).
3. **Tests Wire Perimeter Defense**: Demonstrates synchronous HTTP 400 rejection of missing attributes, invalid enum values, and type mismatches.
4. **Tests Storage Quarantine**: Shows storage-level schema failures routed to Dead-Letter Queue (DLQ).
5. **Injects Quality & SLA Violations**: Simulates stale records (> 2h), negative prices, zero volume, and wash trades.
6. **Executes Dataplex Auto DQ engine** and parses 9 rules.
7. **Renders Executive Scorecard** with KPI metrics and actionable SQL forensics drilldown queries.

---

### Option B: Live Google Cloud Deployment

Deploy the infrastructure, stream live messages, and execute real Dataplex scans in your GCP project:

```bash
# 1. Provision all cloud resources (idempotent, takes ~2 minutes)
./setup.sh --project-id=YOUR_PROJECT_ID --region=asia-southeast1

# 2. Run the live end-to-end demonstration
./run_demo.sh --live --project-id=YOUR_PROJECT_ID

# 3. Clean up all resources when finished
./cleanup.sh --project-id=YOUR_PROJECT_ID
```

> [!TIP]
> Both `setup.sh` and `run_demo.sh` support `--dry-run` so you can preview all `gcloud` and `bq` commands before executing.

---

## 📋 Open Data Contract Standard (`contract.odcs.yaml`)

This repository follows the [Open Data Contract Standard (ODCS) v3.0.0](https://bitol.io/odcs/). The contract specifies:

### 1. Core Trade Event Properties
| Field | Type | Required | Constraints | Description |
| :--- | :--- | :--- | :--- | :--- |
| `trade_id` | `string` | **Yes** | Primary Key | Unique trade execution identifier (e.g. `TR-EQ-20260914-001`) |
| `instrument_code` | `string` | **Yes** | Ticker | Security ticker symbol (e.g. `AAPL`, `GOOGL`, `MSFT`) |
| `price` | `number` | **Yes** | `> 0` | Traded execution price |
| `volume` | `integer` | **Yes** | `> 0` | Number of executed shares |
| `buyer_id` | `string` | **Yes** | Participant ID | Clearing participant ID of purchasing broker |
| `seller_id` | `string` | **Yes** | Participant ID | Clearing participant ID of selling broker |
| `trade_timestamp` | `timestamp` | **Yes** | ISO-8601 UTC | UTC trade execution timestamp |
| `trade_status` | `string` | **Yes** | Enum | State: `EXECUTED`, `CANCELLED`, `AMENDED` |

### 2. Quality & SLA Rules
* **Freshness SLA**: `trade_timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 2 HOUR)`.
* **Completeness**: `nonNullExpectation` on `trade_id`, `instrument_code`, `price`, `volume`.
* **Validity Range**: `price > 0` and `volume > 0` with `strictMinEnabled: true`.
* **Market Integrity (Anti-Wash Trading)**: `buyer_id != seller_id`. Enforces regulatory rules (FINRA Rule 5210 / SEC / MAS TRM) prohibiting transactions where beneficial ownership does not change.

---

## 🛠️ The Contract Compiler (`compile_contract.py`)

The contract compiler is written in pure standard library Python (plus `pyyaml`) to guarantee portability:

```bash
# Check if generated artifacts have drifted from the contract specification
python3 compile_contract.py --check

# Compile contract into target artifacts
python3 compile_contract.py \
  --contract=contract.odcs.yaml \
  --project-id=my-project \
  --dataset=market_data \
  --table=equity_trades
```

---

## 🎯 Industry Presets (Global Brokerage vs Exchange)

The producer script and lifecycle tools support interchangeable presets:

```bash
# Default: Global Tech Stock Equities (AAPL, GOOGL, MSFT, NVDA, AMZN)
python3 scripts/publish_events.py --mode=valid --preset=global

# Singapore Exchange (SGX) Preset (D05.SI, Z74.SI, U11.SI, O39.SI, C6L.SI)
python3 scripts/publish_events.py --mode=valid --preset=sgx

# Or run the demo with the SGX preset:
./run_demo.sh --preset=sgx --simulated
```

---

## 📊 Executive Scorecard & Forensics

When Dataplex Auto DQ runs, results are exported to BigQuery. The included analytics view provides an immediate RAG (Red-Amber-Green) status and actionable debug SQL queries:

```sql
-- Query 1: Executive KPI Dashboard
SELECT * FROM `my-project.market_data.v_dq_rule_summary`;

-- Query 2: Drilldown to failing rows for anti-wash trading breaches
SELECT * FROM `my-project.market_data.equity_trades`
WHERE buyer_id = seller_id;
```

---

## 🧪 Running the Test Suite

This repository includes a multi-tiered test suite (Tiers 1–5):

```bash
# Run all automated tests
bash tests/run_e2e_tests.sh --all

# Or run via Python unittest:
python3 -m unittest discover -s tests -p "*.py"
```

## 🏛️ Native Dataplex Knowledge Catalog Governance (Glossary, EntryLinks & Data Product)

Provision the out-of-the-box Google Cloud Dataplex Knowledge Catalog experience—binding the **8 canonical Upstream Source Dictionary (`v4.2`)** terms via column-level `EntryLinks` across both the raw table and the **Curated Contract View (`equity_trades_curated`)**, alongside a packaged **Dataplex Data Product (`equity-market-trades`)**:

```bash
# Dry-run the 33-step Dataplex Catalog REST plan offline (zero credentials needed)
python3 scripts/provision_catalog.py apply --dry-run

# Provision live Curated View, Business Glossary, 16 Column EntryLinks & Data Product
python3 scripts/provision_catalog.py apply --project-id=my-project

# Or run as part of setup.sh / cleanup.sh
./setup.sh --project-id=my-project --with-catalog
./cleanup.sh --project-id=my-project --with-catalog --force
```

---

## 🏷️ Business Data Contract & Nutri-Grade (`A–E`) Portal

For business consumers and platform stewards who want a single-pane executive scorecard showing the **3-Layer Internal Handshake**, **Nutri-Grade (`A–E`) Quality Badge** (comparing `Curated Contract View — Grade A 100.0%` vs. `Raw Landing Table — Grade E 55.6%`), and **Column Provenance Explorer** (`Inherited: Source Dictionary (8)` vs. `AI-Enriched: Platform Derived (2)`):

```bash
# Export standalone zero-dependency HTML portal (portal/index.html)
python3 scripts/run_contract_portal.py export

# Serve interactive local portal on http://127.0.0.1:8765
python3 scripts/run_contract_portal.py serve --port 8765
```

---

## 🎤 Speaker & Presentation Guide

Delivering this demo to engineering leadership or regulatory stakeholders? Check out [`DEMO_GUIDE.md`](DEMO_GUIDE.md) for a **10-slide executive talk track** complete with:
* Slide objectives & key takeaways
* Verbatim speaking scripts
* Step-by-step console click paths and terminal commands
* Anticipated regulatory and technical Q&A (FINRA, SEC, MAS TRM Section 8)


---

## 📄 License

Licensed under the Apache License, Version 2.0. See [LICENSE](LICENSE) for details.
