# Random Stuff

A collection of random, ad-hoc code and projects built over time.

## Project Structure

```
random-stuff/
├── agent_stuff/
│   ├── AGENTS.md                           # Agent behavioral directives
│   └── CODE_STANDARDS.md                   # Code style standards (multi-language)
├── bq_caapi_ge/                            # Conversational Analytics API + Gemini Enterprise ADK demo
├── bq_discovery/                           # BigQuery IAM/ACL audit CLI tool
├── bq_firebase/                            # Firebase Analytics with BigQuery integration
├── bq_finops_cookbook/                     # BigQuery slot optimization framework
├── bq_geospatial_demo/                     # BigQuery geospatial routing optimization demo
├── bq_kubernetes_comparison/               # BigQuery vs Kubernetes resource management comparison
├── bq_places_insights/                     # BigQuery Places Insights competitive analysis
├── bq_prompt_engineering/                  # BigQuery Data Science Agent prompts and context templates
├── bq_rls_cls_dataform/                    # BigQuery RLS/CLS demo with Dataform
├── bq_scaling_viz/                         # BigQuery scaling visualization
├── bq_streaming_cdc/                       # BigQuery Streaming CDC with Storage Write API
├── bq_swapi_stress_test/                   # BigQuery Storage Write API stress test
├── dbt_migration_agents/                   # dbt migration toolkit with AI agents
├── dbt_spark_bq/                           # dbt Spark on Dataproc with BigQuery
├── others/                                 # Agent rule sync scripts (Claude, Cline, Gemini, OpenClaw)
├── remote_docker/                          # Docker SSH tunnel management
└── samba_management/                       # Samba service management
```

## Projects

### BigQuery Tools

- **bq_caapi_ge**: Conversational Analytics API + Gemini Enterprise demo using Google ADK. Deploys two ADK agents (`orders` and `inventory`) that bridge the Conversational Analytics API with Gemini Enterprise via OAuth identity passthrough. Includes operational scripts for deployment and registration, a Flask OAuth test harness, and reference implementations for chart visualization.
- **bq_discovery**: CLI tool (`bq-discovery`) for auditing BigQuery access across a GCP organization. Scans Cloud Asset Inventory IAM policies at project, dataset, and table/view level; dataset legacy ACLs (READER/WRITER/OWNER, specialGroups, domains, authorized views); and optionally expands Google Group memberships via Cloud Identity. Outputs JSON, JSONL, or CSV for direct `bq load` import.
- **bq_firebase**: Firebase Analytics with BigQuery integration. Includes Jupyter notebook for querying and analyzing Firebase Analytics data (event tracking, user behavior analysis, conversion funnel analysis) and a complete Flask web application demonstrating Google SSO with Firebase Authentication, YouTube Data API integration, and GA4 event tracking with BigQuery export.
- **bq_finops_cookbook**: Comprehensive framework for analyzing BigQuery slot utilization and optimizing workload performance. Provides data-driven recommendations for choosing between on-demand, baseline reservations, autoscaling, or hybrid strategies. Includes Cline agent configurations and sample analysis results across six analytical stages.
- **bq_geospatial_demo**: Delivery route optimization using BigQuery geospatial functions. Includes geohash clustering, nearest neighbor solving, and Maps API integration with both geohash and K-means approaches.
- **bq_kubernetes_comparison**: Visual comparison of BigQuery and Kubernetes workload management strategies.
- **bq_places_insights**: Competitive intelligence framework using BigQuery Places Insights for banking/finance sector. Includes Jakarta banking demo with 7 analytical queries (market landscape, geographic heatmap, quality analysis, white space opportunities, regional performance, operating hours, payment adoption) and comprehensive field reference guide covering 70+ data fields with use cases for market analysis and strategic expansion planning.
- **bq_prompt_engineering**: Example prompts and context initialization templates for the BigQuery Data Science Agent, categorized by complexity level (simple one-shot to complex multi-step analytical tasks) and including BigFrames workflow initialization prompts.
- **bq_rls_cls_dataform**: Comprehensive demonstration of BigQuery Row Level Security (RLS) and Column Level Security (CLS) using Dataform with SQL-based data policy approach. Includes both quick SQL demo and production Dataform setup with workflow_settings.yaml configuration.
- **bq_scaling_viz**: Interactive visualization demonstrating BigQuery slot scaling and workload distribution.
- **bq_streaming_cdc**: Change Data Capture (CDC) demonstration using BigQuery Storage Write API with Protobuf serialization. Shows how to stream CDC operations (INSERT, UPDATE, DELETE) using `_CHANGE_TYPE` and `_CHANGE_SEQUENCE_NUMBER` pseudo-columns with tables configured for primary keys and max_staleness. Includes dynamic Protobuf schema generation, table creation script, and complete demo runner.
- **bq_swapi_stress_test**: Apache Beam streaming pipeline that stress-tests BigQuery Storage Write API throughput by generating synthetic e-commerce data in-memory (eliminating read I/O bottlenecks). Targets the 300 MB/s regional limit. Includes Dataflow job management scripts and documented test results.

### dbt Tools

- **dbt_migration_agents**: AI-assisted dbt migration toolkit with lineage analysis, PRD generation, code refactoring, and validation. Includes sample Bronze/Silver/Gold project with intentional errors for testing migration workflows.
- **dbt_spark_bq**: Jupyter notebook demonstrating dbt Spark on Dataproc with BigQuery integration.

### AI/Agent Tools

- **agent_stuff**: Agent behavioral directives (`AGENTS.md`) and multi-language code style standards (`CODE_STANDARDS.md`) based on Google style guides. These files are the single source of truth distributed to AI coding agents via the `others/` sync scripts.

- **others**: Scripts for distributing agent rule files to various AI coding agent platforms:
  - `claude/` — Syncs `AGENTS.md` and `CODE_STANDARDS.md` to `~/.claude/` and patches OpenCode config
  - `cline/` — Copies rule files to Cline's Rules directory with read-only protection
  - `gemini/` — Syncs rule files to `~/.gemini/` and patches Gemini CLI `settings.json`
  - `openclaw/` — Setup guides for running OpenClaw with Anthropic, Gemini, and local model providers

### Infrastructure

- **remote_docker**: SSH tunnel management for remote Docker daemon access.

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
