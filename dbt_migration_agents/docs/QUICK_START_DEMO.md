# Quick Start Demo Guide

This guide provides a "Quick Win" copy-pasteable script to set up the entire environment from scratch. 
It hydrates the sample project in BigQuery and configures the agents, so you can immediately test the migration workflow.

## Prerequisites

1.  **Google Cloud Project**: You need a project ID (e.g., `my-playground-123`).
2.  **Authentication**: Ensure you are logged in locally:
    ```bash
    gcloud auth application-default login
    ```
3.  **uv**: Install uv if you haven't already:
    ```bash
    curl -LsSf https://astral.sh/uv/install.sh | sh
    ```

## The "Golden Path" Script

Copy the following script, replace `YOUR_PROJECT_ID` with your actual GCP project ID, and run it in your terminal.

```bash
# --- CONFIGURATION ---
export PROJECT_ID="YOUR_PROJECT_ID"
export LOCATION="US"

# 1. Install Dependencies
echo "Installing dependencies..."
uv sync --all-extras

# 2. Configure DBT Profile
echo "Configuring DBT profile..."
cd sample_project
mkdir -p ~/.dbt

cat <<EOF > profiles.yml
sample_project:
  target: dev
  outputs:
    dev:
      type: bigquery
      method: oauth
      project: ${PROJECT_ID}
      dataset: sample_gold
      threads: 4
      timeout_seconds: 300
      location: ${LOCATION}
      priority: interactive
EOF

# 3. Hydrate BigQuery (Build Tables)
echo "Hydrating BigQuery environment..."
uv run dbt deps
uv run dbt seed --profiles-dir . --full-refresh
uv run dbt run --profiles-dir . --full-refresh
uv run dbt parse --profiles-dir .

# 4. Configure Migration Agents
echo "Configuring Migration Agents..."
cd ..
mkdir -p config

cat <<EOF > config/migration_config.yaml
project:
  name: "sample_project"
  manifest_path: "sample_project/target/manifest.json"

gcp:
  billing_project: "${PROJECT_ID}"
  projects:
    bronze: "${PROJECT_ID}"
    silver: "${PROJECT_ID}"
    gold: "${PROJECT_ID}"
  schemas:
    bronze: "sample_bronze"
    silver: "sample_silver"
    gold: "sample_gold"

dbt:
  bronze_models: "sample_project/models/bronze"
  silver_models: "sample_project/models/silver"
  gold_models: "sample_project/models/gold"
  seeds: "sample_project/seeds"

outputs:
  base_path: "migration_outputs"
  lineage: "lineage_analyzer/outputs"
  prd: "prd_generator/outputs"
  validation: "migration_validator/outputs"
  cookbooks: "code_refactor/outputs"

validation:
  row_count_threshold: 0.001
  null_threshold: 0.05
EOF

echo "✅ Setup Complete! You are ready to run the agent."
echo "Try asking: 'Follow the workflow in .agents/commands/migration_workflow.md to migrate sample_project/models/gold/fct_orders_broken.sql targeting ${PROJECT_ID}.sample_gold'"
```
