# PRD Generator Cookbook

## Overview

This cookbook provides the methodology for generating comprehensive Product Requirements Documents (PRDs) from migration analysis for gold layer migrations.

## Configuration

**CRITICAL**: All project-specific values come from `config/migration_config.yaml`.

Before using this cookbook, ensure the config file is properly set up.

## Purpose

The PRD Generator:
1. Reads migration analysis documents
2. Extracts model recommendations with priorities
3. Generates complete SQL BEFORE/AFTER examples
4. Creates comprehensive PRD with validation tests
5. Documents implementation plan and risks

## Input Requirements

### Required Files
- Migration analysis: `{{ config.outputs.prd }}/{model_name}_migration_analysis.md`
- Configuration file: `config/migration_config.yaml`

### Required Parameters
- Target project.dataset (e.g., `my-project.my_dataset`)

### Required Config Values
```yaml
gcp:
  billing_project: "your-billing-project"
  projects:
    bronze: "your-bronze-project"    # Raw data ingestion
    silver: "your-silver-project"    # Transformed/cleaned data
    gold: "your-gold-project"        # Curated business data

architecture:
  description: "Your data architecture description"
  layers:
    - name: "Bronze"
      project: "your-bronze-project"
      description: "Raw data ingestion"
    - name: "Silver"
      project: "your-silver-project"
      description: "Cleaned/transformed data"
    - name: "Gold"
      project: "your-gold-project"
      description: "Curated business data"
```

## PRD Generation Process

### Phase 1: Load Configuration

```
Read config/migration_config.yaml

Extract:
- BILLING_PROJECT = config.gcp.billing_project
- SILVER_PROJECT = config.gcp.projects.silver
- GOLD_PROJECT = config.gcp.projects.gold
- ARCHITECTURE_DESC = config.architecture.description
- DATA_LAYERS = config.architecture.layers
```

### Phase 2: Parse Target Parameters

```
Input: target_project.dataset
Split on '.'
- target_project = first part
- target_dataset = second part
```

### Phase 3: Read Migration Analysis

Extract from analysis document:
- Total dependencies
- Models to migrate (by priority)
- Complexity classifications
- Business logic descriptions
- Source table mappings

### Phase 4: Read Original SQL

For each model to migrate:
1. Read silver model SQL file
2. Extract complete SQL for BEFORE example
3. Note current location

### Phase 5: Generate PRD Document

**PRD Structure (10 Sections)**:

```markdown
# Gold Layer Migration PRD: {model_name}

## 1. Executive Summary

### Objective
Migrate {N} models to {target_project} gold layer.

### Business Impact
- Priority 1: {X} models - {description}
- Priority 2: {Y} models - {description}
- Priority 3: {Z} models - {description}

### Target
- Project: {target_project}
- Dataset: {target_dataset}
- Source: {{ config.gcp.projects.silver }}

## 2. Background & Context

### Data Architecture
```
{{ config.gcp.projects.bronze }}   → Bronze layer (raw ingestion)
{{ config.gcp.projects.silver }}   → Silver layer (SOURCE - transformed)
{target_project}                   → Gold layer (TARGET - curated)
```

### Architecture Description
{{ config.architecture.description }}

### Current Issues
[From migration analysis]

## 3. Objectives & Success Metrics

### Priority Targets
- Priority 1: {metrics}
- Priority 2: {metrics}
- Priority 3: {metrics}

### Success Criteria
- 100% row count match
- Zero business logic changes
- All validations pass

## 4. Proposed Solution

### Migration Strategy
| Priority | Models | Complexity | Timeline |
|----------|--------|------------|----------|
| 1 | {list} | LOW | Phase 1 |
| 2 | {list} | MEDIUM | Phase 2 |
| 3 | {list} | HIGH | Phase 3 |

### Models to Migrate Table
| Model | Source | Business Logic | Complexity |
|-------|--------|----------------|------------|
| {model_1} | {{ config.gcp.projects.silver }}.{schema}.{table} | {description} | {level} |

## 5. Technical Requirements

### Model: {model_name}

**CURRENT (Silver):**
```sql
-- Location: {{ config.gcp.projects.silver }}.{{ config.gcp.schemas.silver }}.{model_name}
-- Source: {{ source('schema', 'table') }}

{complete_sql_from_silver}
```

**NEW (Gold Layer):**
```sql
-- Location: {target_project}.{target_dataset}.{model_name}
-- Source: {{ config.gcp.projects.silver }}.{schema}.{table}

{{ config(
    materialized='table',
    partition_by={...},
    cluster_by=[...],
    project="{target_project}",
    schema="{target_dataset}"
) }}

WITH source AS (
    SELECT *
    FROM `{{ config.gcp.projects.silver }}.{schema}.{table}`
),

{all_business_logic_ctes}

renamed AS (
    SELECT
        {all_fields},
        CURRENT_TIMESTAMP() AS gold_loaded_at,
        '{source_system}' AS gold_source_system
    FROM {final_cte}
)

SELECT * FROM renamed
```

**UPDATE Downstream:**
```sql
-- OLD
{{ ref('{model_name}') }}

-- NEW
{{ source('gold_{category}', '{model_name}') }}
```

[Repeat for each model]

## 6. Implementation Steps

### Phase 1: Gold Layer Setup
- Create directory structure
- Migrate Priority 1 models
- Validate each model

### Phase 2: Validation
- Run validation subagent
- Review reports
- Apply refinements

### Phase 3: Downstream Updates
- Update source references
- Validate end-to-end

## 7. Validation Tests

### Row Count Validation
```sql
SELECT
  'row_count' AS test,
  (SELECT COUNT(*) FROM `{{ config.gcp.projects.silver }}.{{ config.gcp.schemas.silver }}.{model_name}`) AS silver,
  (SELECT COUNT(*) FROM `{target_project}.{target_dataset}.{model_name}`) AS gold
```

### Primary Key Uniqueness
```sql
SELECT COUNT(*) AS duplicates
FROM (
  SELECT {pk_column}, COUNT(*) AS cnt
  FROM `{target_project}.{target_dataset}.{model_name}`
  GROUP BY {pk_column}
  HAVING cnt > 1
)
```

### Business Logic Validation
[Model-specific validation queries]

## 8. Risk Assessment & Mitigation

| Risk | Severity | Mitigation |
|------|----------|------------|
| Data discrepancy | HIGH | Validation before deployment |
| Performance degradation | MEDIUM | Optimize partitioning/clustering |
| Downstream breaks | HIGH | Phased rollout with testing |

## 9. Success Criteria

### Phase Completion Checklist
- [ ] All models migrated
- [ ] All validations pass
- [ ] Documentation complete
- [ ] Downstream updated

### Metrics
| Metric | Before | After |
|--------|--------|-------|
| Silver models | {X} | 0 |
| Gold models | 0 | {X} |

## 10. Next Steps

### Immediate (Week 1)
- Review and approve PRD
- Generate migration cookbook
- Begin Phase 1 migration

### Future
- Monitor gold layer performance
- Deprecate staging models
- Update documentation
```

## Output

**File**: `{{ config.outputs.prd }}/{model_name}_dbt_refactoring_prd.md`

## SQL Generation Guidelines

### BEFORE SQL
- Copy exact SQL from staging model
- Include all CASE statements verbatim
- Preserve all CTEs and logic

### AFTER SQL
- Use config-based project references
- Add partition_by and cluster_by
- Add audit fields (gold_loaded_at, gold_source_system)
- Read from silver layer

### Config Block Template
```sql
{{ config(
    materialized='table',
    partition_by={
        "field": "{timestamp_field}",
        "data_type": "timestamp",
        "granularity": "day"
    },
    cluster_by=["{field_1}", "{field_2}"],
    tags=["gold", "{category}", "{source}"],
    project="{target_project}",
    database="{target_project}",
    schema="{target_dataset}"
) }}
```

## Best Practices

1. **Use Config Values**: All project references from config
2. **Complete SQL**: Provide full working SQL
3. **Preserve Logic**: Copy business logic exactly
4. **Clear Validation**: Include testable criteria
5. **Phased Approach**: Group by priority

---

**Cookbook Version**: 2.0 (Generic)
**Configuration**: config/migration_config.yaml
**Output**: PRD document
