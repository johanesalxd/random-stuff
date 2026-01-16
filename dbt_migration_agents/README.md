# DBT Migration Agents (OpenCode Edition)

A generic, configurable framework for migrating DBT silver models to the gold layer using AI agents and the Bronze/Silver/Gold medallion architecture.

## TL;DR

**Goal**: Simplify DBT data pipelines by consolidating unnecessary intermediate Silver layers

**Demo**: Shows migration from a 4-hop pipeline to a 2-hop pipeline:
- Before: Bronze → Silver_1 → Silver_2 → Silver_3 → Gold (complex)
- After: Bronze → Silver → Gold (simplified)

**How**: Ask the agent to run the migration workflow to generate analysis, PRD, and migration cookbook

---

## Prerequisites

### Required Tools
1. **OpenCode Agent** running **Gemini 3 Pro**
   * This framework is optimized for the reasoning capabilities of Gemini 3 Pro.
2. **DBT Project** with BigQuery connection
3. **Python 3.8+**

---

## Migration Goal

This framework helps you **bypass unnecessary intermediate layers** in your data pipeline:

| Before (Broken) | After (Correct) |
|-----------------|-----------------|
| Bronze → int_cleaned → int_enriched → int_final → Gold | Bronze → stg_orders → Gold |
| 4 hops, 4 tables, complex lineage | 2 hops, 2 tables, simple lineage |

**Benefits**:
- Fewer intermediate tables to maintain
- Simpler data lineage
- Reduced compute costs
- Easier debugging

---

## Demo Scenarios

The `sample_project/` includes broken scenarios for testing:

| Scenario | Pattern | Files |
|----------|---------|-------|
| Broken (4 hops) | Bronze → int_1 → int_2 → int_3 → Gold | `int_orders_*_broken.sql`, `fct_orders_broken.sql` |
| Correct (2 hops) | Bronze → stg_orders → Gold | `stg_orders.sql`, `fct_orders.sql` |

Use these to demonstrate the validation and migration workflow.

---

## How to Execute

### Step 1: Setup

```bash
cd dbt_migration_agents/sample_project

# Copy and configure
cp ../config/migration_config.example.yaml ../config/migration_config.yaml
# Edit with your GCP project details

# Generate DBT manifest
dbt parse
```

### Step 2: Run Migration Generator

Ask OpenCode (using Gemini 3 Pro):

> "Follow the workflow in .agents/commands/migration_workflow.md to migrate models/gold/fct_orders_broken.sql targeting my-project.my_dataset"

This generates:
1. Migration Analysis (lineage and complexity)
2. PRD (implementation plan with SQL examples)
3. Migration Cookbook (step-by-step guide)

### Step 3: Review and Approve PRD

Review the generated PRD at:
```
prd_generator/outputs/fct_orders_broken_dbt_refactoring_prd.md
```

When satisfied, respond to the agent: "Approved, proceed with cookbook generation"

### Step 4: Execute Migration

```
Execute migration following @code_refactor/outputs/gold_fct_orders_broken_cookbook.md
```

The agent will:
1. Create consolidated gold model (stg_orders → fct_orders pattern)
2. Compile and run
3. Validate against the broken model
4. Apply automatic SQL refinement if validation fails
5. Document results

### Step 5: Validate Results

Both models should produce equivalent data:
- `fct_orders_broken` (4 hops, reading from int_orders_final_broken)
- `fct_orders` (2 hops, reading from stg_orders)

The migration demonstrates that we can consolidate the intermediate chain without losing any business logic or data quality.

---

## Overview

This template provides 5 specialized AI agents that work together to:

1. **Analyze dependencies** - Understand your DBT model lineage
2. **Generate PRD** - Create comprehensive migration plan
3. **Generate cookbook** - Step-by-step migration guide
4. **Validate migrations** - Intelligent testing with RCA
5. **Execute migrations** - One model at a time with feedback loops

## Quick Start

### 1. Clone or Copy to Your Project

Copy the `dbt_migration_agents/` directory to your DBT project root.

### 2. Configure

```bash
cd dbt_migration_agents

# Copy and edit the configuration file
cp config/migration_config.example.yaml config/migration_config.yaml

# Edit with your project-specific values
vim config/migration_config.yaml
```

### 3. Validate Configuration

```bash
python config/config_loader.py
```

### 4. Run Your First Migration

Ask your agent:
> "Analyze dependencies for models/marts/my_model.sql using config/migration_config.yaml"

## Configuration

All project-specific values are stored in `config/migration_config.yaml`.

### Required Settings

```yaml
project:
  name: "your_dbt_project"
  manifest_path: "target/manifest.json"

gcp:
  billing_project: "your-billing-project"
  projects:
    bronze: "your-bronze-project"    # Raw data ingestion
    silver: "your-silver-project"    # Transformed/cleaned data
    gold: "your-gold-project"        # Curated business data
```

See `config/migration_config.example.yaml` for all available options.

## Directory Structure

```
dbt_migration_agents/
├── .agents/
│   ├── agents/                 # Agent definitions
│   │   ├── dbt_lineage_generator.md
│   │   ├── lineage_analyzer.md
│   │   ├── prd_generator.md
│   │   ├── validation_subagent.md
│   │   └── migration_cookbook_generator.md
│   └── commands/
│       └── migration_workflow.md
├── config/
│   ├── migration_config.yaml   # Your configuration
│   ├── migration_config.example.yaml
│   └── config_loader.py        # Python config utilities
├── lineage_analyzer/
│   ├── dbt_based/
│   │   └── analyze_dbt_lineage.py
│   ├── outputs/                # Generated lineage files
│   └── LINEAGE_ANALYZER_COOKBOOK.md
├── prd_generator/
│   ├── outputs/                # Generated PRDs
│   └── PRD_GENERATOR_COOKBOOK.md
├── migration_validator/
│   ├── scripts/                # Generated validation scripts
│   ├── outputs/                # Validation reports
│   └── VALIDATION_COOKBOOK.md
├── code_refactor/
│   ├── outputs/                # Generated cookbooks
│   └── DBT_MIGRATION_COOKBOOK_TEMPLATE.md
└── docs/
    ├── SETUP_GUIDE.md
    └── CUSTOMIZATION.md
```

## Workflow

```
Migration Workflow
    │
    ├── Step 0: Load config, validate/generate lineage
    │
    ├── Step 1: Analyze dependencies (lineage_analyzer)
    │   └── Output: migration_analysis.md
    │
    ├── Step 2: Generate PRD (prd_generator)
    │   └── Output: dbt_refactoring_prd.md
    │
    ├── Step 3: User reviews and approves PRD
    │
    └── Step 4: Generate cookbook (migration_cookbook_generator)
        └── Output: migration_cookbook.md

"Execute migration following @cookbook.md"
    │
    └── For each model:
        ├── Create gold model
        ├── Compile and run
        ├── Validate (validation_subagent)
        │   └── If failed: RCA → Refine SQL → Re-validate
        └── Document and confirm
```

## Agent Descriptions

### 1. DBT Lineage Generator

Generates DBT lineage documentation from `manifest.json`.

**Trigger**: Automatically when lineage files are missing

### 2. Lineage Analyzer

Analyzes dependencies and classifies complexity.

**Output**: `{model}_migration_analysis.md`

### 3. PRD Generator

Creates comprehensive Product Requirements Document.

**Output**: `{model}_dbt_refactoring_prd.md`

### 4. Migration Cookbook Generator

Generates step-by-step migration guide.

**Output**: `gold_{model}_cookbook.md`

### 5. Validation Subagent

Validates migrated tables with intelligent tests and RCA.

**Output**: Validation reports with deployment decisions

## Manual Agent Invocation

You can run agents individually by prompting OpenCode:

```
# Analyze dependencies
"Use the Task tool with .agents/agents/lineage_analyzer.md to analyze models/gold/my_model.sql"

# Generate PRD
"Use the Task tool with .agents/agents/prd_generator.md to generate a PRD from..."
```

## Customization

### Adding Custom Validation Tests

Edit `migration_validator/VALIDATION_COOKBOOK.md` to add custom test patterns.

### Modifying Agent Behavior

Edit the agent definitions in `.agents/agents/` to customize behavior.

### Extending the Template

See `docs/CUSTOMIZATION.md` for detailed extension guide.

## Troubleshooting

### Configuration Not Found

```bash
# Verify config exists
ls config/migration_config.yaml

# Validate config
python config/config_loader.py
```

### Manifest Not Found

```bash
# Generate manifest
dbt parse

# Verify manifest exists
ls target/manifest.json
```

### BigQuery Permission Denied

Verify you have:
- BigQuery Data Viewer on source project
- BigQuery Data Editor on target project
- BigQuery Job User for running queries

### Validation Fails

1. Review the RCA in the validation report
2. Apply the remediation SQL
3. Re-run validation

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## License

MIT License - See LICENSE file for details.

---

**Version**: 2.0 (OpenCode Edition)
**Last Updated**: 2025

