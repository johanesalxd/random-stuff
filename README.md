# Random Stuff

A collection of random, ad-hoc code and projects built over time.

## Project Structure

```
random-stuff/
├── agent_stuff/
│   ├── AGENTS.md                           # Coding standards for AI-generated code
│   ├── MEMORY_BANK.md                      # Context management for complex projects
│   └── cline_gemini_mcp/                   # BigQuery MCP server management for Cline
├── bq_firebase/                            # Firebase Analytics with BigQuery integration
├── bq_finops_cookbook/                     # BigQuery slot optimization framework
├── bq_geospatial_demo/                     # BigQuery geospatial routing optimization demo
├── bq_kubernetes_comparison/               # BigQuery vs Kubernetes resource management comparison
├── bq_places_insights/                     # BigQuery Places Insights competitive analysis
├── bq_prompt_engineering/                  # BigQuery Data Science Agent example prompts
├── bq_rls_cls_dataform/                    # BigQuery RLS/CLS demo with Dataform
├── bq_scaling_viz/                         # BigQuery scaling visualization
├── bq_streaming_cdc/                       # BigQuery Streaming CDC with Storage Write API
├── dbt_migration_agents/                   # dbt migration toolkit with AI agents
├── dbt_spark_bq/                           # dbt Spark on Dataproc with BigQuery
├── remote_docker/                          # Docker SSH tunnel management
└── samba_management/                       # Samba service management
```

## Projects

### BigQuery Tools

- **bq_firebase**: Firebase Analytics with BigQuery integration. Includes Jupyter notebook for querying and analyzing Firebase Analytics data (event tracking, user behavior analysis, conversion funnel analysis) and a complete Flask web application demonstrating Google SSO with Firebase Authentication, YouTube Data API integration, and GA4 event tracking with BigQuery export.
- **bq_finops_cookbook**: Comprehensive framework for analyzing BigQuery slot utilization and optimizing workload performance. Provides data-driven recommendations for choosing between on-demand, baseline reservations, autoscaling, or hybrid strategies.
- **bq_geospatial_demo**: Delivery route optimization using BigQuery geospatial functions. Includes geohash clustering, nearest neighbor solving, and Maps API integration with both geohash and K-means approaches.
- **bq_kubernetes_comparison**: Visual comparison of BigQuery and Kubernetes workload management strategies.
- **bq_places_insights**: Competitive intelligence framework using BigQuery Places Insights for banking/finance sector. Includes Jakarta banking demo with 7 analytical queries (market landscape, geographic heatmap, quality analysis, white space opportunities, regional performance, operating hours, payment adoption) and comprehensive field reference guide covering 70+ data fields with use cases for market analysis and strategic expansion planning.
- **bq_prompt_engineering**: Example prompts for BigQuery Data Science Agent, categorized by complexity level (simple one-shot to complex multi-step analytical tasks).
- **bq_rls_cls_dataform**: Comprehensive demonstration of BigQuery Row Level Security (RLS) and Column Level Security (CLS) using Dataform with SQL-based data policy approach. Includes both quick SQL demo and production Dataform setup with workflow_settings.yaml configuration.
- **bq_scaling_viz**: Interactive visualization demonstrating BigQuery slot scaling and workload distribution.
- **bq_streaming_cdc**: Change Data Capture (CDC) demonstration using BigQuery Storage Write API with Protobuf serialization. Shows how to stream CDC operations (INSERT, UPDATE, DELETE) using `_CHANGE_TYPE` and `_CHANGE_SEQUENCE_NUMBER` pseudo-columns with tables configured for primary keys and max_staleness. Includes dynamic Protobuf schema generation, table creation script, and complete demo runner.

### dbt Tools

- **dbt_migration_agents**: AI-assisted dbt migration toolkit with lineage analysis, PRD generation, code refactoring, and validation. Includes sample Bronze/Silver/Gold project with intentional errors for testing migration workflows.
- **dbt_spark_bq**: Jupyter notebook demonstrating dbt Spark on Dataproc with BigQuery integration.

### AI/Agent Tools

- **agent_stuff**: Coding standards based on Google style guides (AGENTS.md), context management guidelines (MEMORY_BANK.md), and Cline MCP server configurations for BigQuery integration.

### Infrastructure

- **remote_docker**: SSH tunnel management for remote Docker daemon access.

## Shell Integration

Add the following aliases to your `.zshrc` or `.bashrc` for quick access to management scripts:

```bash
# Docker SSH Tunnel Management
export DOCKER_HOST=tcp://localhost:2375
alias manage-docker='~/Developer/git/random-stuff/remote_docker/manage_docker_tunnel.sh'

# Cline MCP Management
alias manage-mcp='~/Developer/git/random-stuff/agent_stuff/cline_gemini_mcp/manage_mcp_servers.sh'

# Samba Management
alias manage-samba='~/Developer/git/random-stuff/samba_management/manage_samba.sh'
```

**Usage:**
- `manage-docker`: Start, stop, or check status of Docker SSH tunnel
- `manage-mcp`: Manage Cline MCP server configurations (see `agent_stuff/README.md`)
- `manage-samba`: Manage Samba services (smbd and nmbd) on MacOS
