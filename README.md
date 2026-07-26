# Random Stuff

A collection of random, ad-hoc code and projects built over time.

## Project Structure

```
random-stuff/
├── agent_stuff/
│   ├── AGENTS.md                           # Agent behavioral directives
│   └── CODE_STANDARDS.md                   # Code style standards (multi-language)
├── bq_caapi_ge/                            # Conversational Analytics API + Gemini Enterprise ADK demo
├── bq_cross_cloud_lakehouse/               # Cross-cloud BigLake Iceberg federation (AWS S3/Glue) demo
├── bq_data_product/                        # Dataplex Data Products orchestration demo on public data
├── bq_dbx_gcp_viz/                         # Databricks on Google Cloud open data platform visualization
├── bq_dbx_scaling_viz/                     # BigQuery vs Databricks scaling visualization
├── bq_discovery/                           # BigQuery IAM/ACL audit CLI tool
├── bq_finops_cookbook/                     # BigQuery slot optimization framework
├── bq_firebase/                            # Firebase Analytics with BigQuery integration
├── bq_geospatial_demo/                     # BigQuery geospatial routing optimization demo
├── bq_kubernetes_comparison/               # BigQuery vs Kubernetes resource management comparison
├── bq_places_insights/                     # BigQuery Places Insights competitive analysis
├── bq_prompt_engineering/                  # BigQuery Data Science Agent prompts and context templates
├── bq_pykx_copy/                           # kdb+ HDB to Parquet to BigQuery migration PoC (PyKX)
├── bq_rls_cls_dataform/                    # BigQuery RLS/CLS demo with Dataform
├── bq_rls_examples/                        # Dynamic row-level security mapping examples
├── bq_spark_serverless_etl/                # Dataproc Serverless PySpark to BigQuery ETL
├── bq_streaming_cdc/                       # BigQuery Streaming CDC with Storage Write API
├── bq_swapi_stress_test/                   # BigQuery Storage Write API stress test
├── composer_concurrency_stress_test/       # Cloud Composer 3 concurrency stress test & deferrable operators
├── dbt_migration_agents/                   # dbt migration toolkit with AI agents
├── dbt_spark_bq/                           # dbt Spark on Dataproc with BigQuery
├── others/                                 # Agent rule sync scripts (Claude, Cline, Gemini, OpenClaw)
├── remote_docker/                          # Docker SSH tunnel management
└── samba_management/                       # Samba service management
```

## Projects

### BigQuery Tools

- **bq_caapi_ge**: Conversational Analytics API + Gemini Enterprise demo using Google ADK. Deploys two ADK agents (`orders` and `inventory`) that bridge the Conversational Analytics API with Gemini Enterprise via OAuth identity passthrough. Includes operational scripts for deployment and registration, a Flask OAuth test harness, and reference implementations for chart visualization.
- **bq_cross_cloud_lakehouse**: Self-contained version of the Google Cloud Next '26 keynote demo ("Raw data to forecasting in seconds with AI agents") that restores the AWS cross-cloud arm the public codelab omits. Uses BigLake Iceberg REST catalog federation with keyless OIDC (`AssumeRoleWithWebIdentity`) and credential vending to read AWS S3/Glue Iceberg tables directly from BigQuery, joins them with native BQ allergen knowledge, and forecasts Q3 revenue with BQML `ARIMA_PLUS` on AWS-resident data. No Databricks or Cross-Cloud Interconnect required.
- **bq_data_product**: Orchestration framework that automates the deployment of three Dataplex Data Products (Sales, Catalog, and Customers) on the public `thelook_ecommerce` dataset. Solves metadata cataloging limitations by implementing secure authorized views, attaching documentation contracts/SLAs, and running asynchronous BigQuery Data Profile scans.
- **bq_dbx_gcp_viz**: Interactive HTML visualization of how Databricks and open engines run on Google Cloud, stepping from a Databricks-only stack to a GCP-native one without lock-in. Renders a layered capability matrix (UX → Engines → Catalog → Storage → Process) with four scenarios (DBX full → DBX led → GCP led → GCP full) showing how an open catalog (Knowledge Catalog / Iceberg REST) keeps data portable across engines and clouds.
- **bq_dbx_scaling_viz**: Interactive visualization comparing serverless vs self-managed scaling across two workloads: query compute (Databricks SQL warehouses vs BigQuery slots, including the "stuffing effect" and the "1 to 11" query problem) and agentic catalog metadata serving (self-managed Unity Catalog vs serverless Knowledge Catalog). Documents IWM behavior, Fluid Scaling billing, and cluster startup caveats.
- **bq_discovery**: CLI tool (`bq-discovery`) for auditing BigQuery access across a GCP organization. Scans Cloud Asset Inventory IAM policies at project, dataset, and table/view level; dataset legacy ACLs (READER/WRITER/OWNER, specialGroups, domains, authorized views); and optionally expands Google Group memberships via Cloud Identity. Outputs JSON, JSONL, or CSV for direct `bq load` import.
- **bq_finops_cookbook**: Comprehensive framework for analyzing BigQuery slot utilization and optimizing workload performance. Provides data-driven recommendations for choosing between on-demand, baseline reservations, autoscaling, or hybrid strategies. Includes Cline agent configurations and sample analysis results across six analytical stages.
- **bq_firebase**: Firebase Analytics with BigQuery integration. Includes Jupyter notebook for querying and analyzing Firebase Analytics data (event tracking, user behavior analysis, conversion funnel analysis) and a complete Flask web application demonstrating Google SSO with Firebase Authentication, YouTube Data API integration, and GA4 event tracking with BigQuery export.
- **bq_geospatial_demo**: Delivery route optimization using BigQuery geospatial functions. Includes geohash clustering, nearest neighbor solving, and Maps API integration with both geohash and K-means approaches.
- **bq_kubernetes_comparison**: Visual comparison of BigQuery and Kubernetes workload management strategies.
- **bq_places_insights**: Competitive intelligence framework using BigQuery Places Insights for banking/finance sector. Includes Jakarta banking demo with 7 analytical queries (market landscape, geographic heatmap, quality analysis, white space opportunities, regional performance, operating hours, payment adoption) and comprehensive field reference guide covering 70+ data fields with use cases for market analysis and strategic expansion planning.
- **bq_prompt_engineering**: Example prompts and context initialization templates for the BigQuery Data Science Agent, categorized by complexity level (simple one-shot to complex multi-step analytical tasks) and including BigFrames workflow initialization prompts.
- **bq_pykx_copy**: Python-first proof of concept for migrating a historical kdb+ HDB into BigQuery using only free tooling (PyKX, no commercial kdb+ add-ons). Reproduces a wide (~450-column), very sparse, date-partitioned order-book table with nanosecond timestamps and streams each partition to Parquet in bounded memory before loading into a partitioned/clustered BigQuery table. All data is synthetic and the schema anonymised.
- **bq_rls_cls_dataform**: Comprehensive demonstration of BigQuery Row Level Security (RLS) and Column Level Security (CLS) using Dataform with SQL-based data policy approach. Includes both quick SQL demo and production Dataform setup with workflow_settings.yaml configuration.
- **bq_rls_examples**: Reference implementation and test suites for building dynamic, scalable Row Access Policies (RLS) in BigQuery using `SESSION_USER()` and non-correlated subqueries against external mapping/lookup tables. Compares dynamic allowlists with legacy hardcoded anti-patterns and documents live-tested service boundaries and limitations.
- **bq_spark_serverless_etl**: Native Dataproc Serverless PySpark pipeline demonstrating end-to-end JDBC-to-BigQuery ETL. Performs parallelized Postgres reads, executes native BigQuery writes (supporting full overwrite, watermarked incremental append, or MERGE upsert), and wraps the pipeline inside a BigQuery Spark Stored Procedure triggered with plain SQL `CALL` statements.
- **bq_streaming_cdc**: Change Data Capture (CDC) demonstration using BigQuery Storage Write API with Protobuf serialization. Shows how to stream CDC operations (INSERT, UPDATE, DELETE) using `_CHANGE_TYPE` and `_CHANGE_SEQUENCE_NUMBER` pseudo-columns with tables configured for primary keys and max_staleness. Includes dynamic Protobuf schema generation, table creation script, and complete demo runner.
- **bq_swapi_stress_test**: Apache Beam streaming pipeline that stress-tests BigQuery Storage Write API throughput by generating synthetic e-commerce data in-memory (eliminating read I/O bottlenecks). Targets the 300 MB/s regional limit. Includes Dataflow job management scripts and documented test results.

### dbt Tools

- **dbt_migration_agents**: AI-assisted dbt migration toolkit with lineage analysis, PRD generation, code refactoring, and validation. Includes sample Bronze/Silver/Gold project with intentional errors for testing migration workflows.
- **dbt_spark_bq**: Jupyter notebook demonstrating dbt Spark on Dataproc with BigQuery integration.

### Orchestration Tools

- **composer_concurrency_stress_test**: Comprehensive testing framework and guide for resolving concurrency bottlenecks in Cloud Composer 3. Demonstrates how to remove Airflow core parallelism limits and use Deferrable Operators (`AirbyteTriggerSyncOperator(deferrable=True)`) to offload tasks to the asynchronous Triggerer, freeing up worker slots. Includes a local mock Airbyte server setup and comparative DAG stress-test runners.

### AI/Agent Tools

- **agent_stuff**: Agent behavioral directives (`AGENTS.md`) and multi-language code style standards (`CODE_STANDARDS.md`) based on Google style guides. These files are the single source of truth distributed to AI coding agents via the `others/` sync scripts.

- **others**: Scripts for distributing agent rule files to various AI coding agent platforms:
  - `claude/` — Syncs `AGENTS.md` and `CODE_STANDARDS.md` to `~/.claude/` and patches OpenCode config
  - `cline/` — Copies rule files to Cline's Rules directory with read-only protection
  - `gemini/` — Syncs rule files to `~/.gemini/` and patches Gemini CLI `settings.json`
  - `openclaw/` — Setup guides for running OpenClaw with Anthropic, Gemini, and local model providers

### Infrastructure

- **remote_docker**: SSH tunnel management for remote Docker daemon access.
- **samba_management**: Management script for manual coordination of Homebrew-installed Samba services (`smbd`/`nmbd`) on macOS. Handles system directory setup, process monitoring, user database configuration, and log inspection.

## Shell Integration

Add the following aliases to your `.zshrc` or `.bashrc` for quick access to management scripts:

```bash
# Docker SSH Tunnel Management
export DOCKER_HOST=tcp://localhost:2375
alias manage-docker='~/Developer/git/random-stuff/remote_docker/manage_docker_tunnel.sh'

# Samba Management
alias manage-samba='~/Developer/git/random-stuff/samba_management/manage_samba.sh'

# Agent Rule Sync
alias sync-rules-claude='~/Developer/git/random-stuff/others/claude/sync_rules.sh'
alias sync-rules-cline='~/Developer/git/random-stuff/others/cline/sync_rules.sh'
alias sync-rules-gemini='~/Developer/git/random-stuff/others/gemini/sync_rules.sh'
```

**Usage:**
- `manage-docker`: Start, stop, or check status of Docker SSH tunnel
- `manage-samba`: Manage Samba services (smbd and nmbd) on MacOS
- `sync-rules-claude`: Sync agent rule files to `~/.claude/` (also patches OpenCode config)
- `sync-rules-cline`: Sync agent rule files to Cline's Rules directory
- `sync-rules-gemini`: Sync agent rule files to `~/.gemini/` (also patches Gemini CLI settings)
