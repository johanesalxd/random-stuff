# Setup Guide

Detailed instructions for setting up DBT Migration Agents in your project.

## Prerequisites

### Required Tools

1. **OpenCode Agent**
   - Verified access to an LLM (Gemini 3 Pro recommended)

2. **DBT**
   - Version 1.0+
   - With BigQuery adapter
   - Verify: `dbt --version`

3. **Python 3.8+**
   - With pip or poetry
   - Verify: `python --version`

4. **Google Cloud SDK**
   - Authenticated for BigQuery
   - Verify: `gcloud auth list`

### Required Python Packages

```bash
pip install google-cloud-bigquery pyyaml
```

### Required Access

| Resource | Permission Level |
|----------|------------------|
| Source BigQuery project | Data Viewer |
| Target BigQuery project | Data Editor |
| Billing project | BigQuery Job User |

## Installation

### Step 1: Copy Template

```bash
# From your DBT project root
cp -r /path/to/dbt_migration_agents ./dbt_migration_agents
```

Or clone directly:

```bash
git clone https://github.com/your-org/dbt-migration-agents.git dbt_migration_agents
```

### Step 2: Create Configuration

```bash
cd dbt_migration_agents

# Copy example config
cp config/migration_config.example.yaml config/migration_config.yaml
```

### Step 3: Edit Configuration

Open `config/migration_config.yaml` and fill in your values:

```yaml
# PROJECT SETTINGS
project:
  name: "your_dbt_project"          # Your dbt_project.yml name
  manifest_path: "target/manifest.json"

# GCP SETTINGS - Bronze/Silver/Gold Medallion Architecture
gcp:
  billing_project: "my-billing-project"  # Project for BQ query costs

  projects:
    bronze: "my-bronze-project"         # Raw data ingestion
    silver: "my-silver-project"         # Cleaned/transformed data (source for migration)
    gold: "my-gold-project"             # Target for curated business data

  schemas:
    bronze: "bronze"                    # Bronze layer schema
    silver: "silver"                    # Silver layer schema
    gold: "gold"                        # Gold layer schema

# DBT PATHS
dbt:
  bronze_models: "models/bronze"        # Raw source models
  silver_models: "models/silver"        # Transformed models
  gold_models: "models/gold"            # Curated gold models
  seeds: "seeds"
```

### Step 4: Validate Configuration

```bash
python config/config_loader.py
```

Expected output:

```
============================================================
DBT Migration Agents Configuration Summary
============================================================
Project: your_dbt_project
Billing Project: my-billing-project

GCP Projects (Bronze/Silver/Gold):
  bronze: my-bronze-project
  silver: my-silver-project
  gold: my-gold-project

DBT Paths:
  bronze_models: models/bronze
  silver_models: models/silver
  gold_models: models/gold
  seeds: seeds
============================================================

Configuration is valid.
```

### Step 5: Generate DBT Manifest

```bash
# From your DBT project root
dbt parse
```

Verify manifest exists:

```bash
ls target/manifest.json
```

### Step 6: Test Agent Access

Verify the agents directory is accessible:

```bash
ls .agents/agents/
```

You should see files like `lineage_analyzer.md`, `prd_generator.md`, etc.

## Configuration Reference

### Project Settings

| Key | Description | Example |
|-----|-------------|---------|
| `project.name` | Your DBT project name | `"my_dbt_project"` |
| `project.manifest_path` | Path to manifest.json | `"target/manifest.json"` |

### GCP Settings (Bronze/Silver/Gold)

| Key | Description | Example |
|-----|-------------|---------|
| `gcp.billing_project` | Project for BQ API billing | `"my-billing-project"` |
| `gcp.projects.bronze` | Bronze layer (raw data) | `"my-bronze-project"` |
| `gcp.projects.silver` | Silver layer (transformed data) | `"my-silver-project"` |
| `gcp.projects.gold` | Gold layer (curated data) | `"my-gold-project"` |

### DBT Paths

| Key | Description | Example |
|-----|-------------|---------|
| `dbt.bronze_models` | Path to bronze models | `"models/bronze"` |
| `dbt.silver_models` | Path to silver models | `"models/silver"` |
| `dbt.gold_models` | Path to gold models | `"models/gold"` |
| `dbt.seeds` | Path to seed files | `"seeds"` |

### Validation Settings

| Key | Description | Default |
|-----|-------------|---------|
| `validation.row_count_threshold` | Max row count difference | `0.001` (0.1%) |
| `validation.null_threshold` | Max NULL increase | `0.05` (5%) |

## Common Setup Issues

### Issue: Config Loader ImportError

```
ImportError: No module named 'yaml'
```

**Solution**:
```bash
pip install pyyaml
```

### Issue: Manifest Not Found

```
Manifest file not found at target/manifest.json
```

**Solution**:
```bash
dbt parse
```

### Issue: BigQuery Permission Denied

```
Permission denied accessing project
```

**Solution**:
1. Verify authentication: `gcloud auth application-default login`
2. Check IAM permissions on the project
3. Verify billing is enabled

### Issue: Agents Not Found

**Solution**:
1. Ensure `.agents` directory exists and is not ignored by your editor
2. Verify agent files are valid markdown

## Verification Checklist

- [ ] Configuration file created at `config/migration_config.yaml`
- [ ] Configuration validation passes
- [ ] DBT manifest exists at configured path
- [ ] BigQuery authentication works
- [ ] Python dependencies installed

## Next Steps

1. Read the [README](../README.md) for usage examples
2. Review [CUSTOMIZATION.md](CUSTOMIZATION.md) for extending the framework
3. Run your first migration by asking OpenCode to follow the migration workflow
