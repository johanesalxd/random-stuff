# Validation Cookbook

## Overview

This cookbook provides the methodology for intelligently validating migrated BigQuery tables with comprehensive test generation, execution, and Root Cause Analysis (RCA).

## Configuration

**CRITICAL**: All project-specific values come from `config/migration_config.yaml`.

Before using this cookbook, ensure the config file is properly set up.

## Purpose

The Validation Agent:
1. Analyzes both tables (optimized and current)
2. Designs intelligent validation tests
3. Generates validation metrics document
4. Creates Python validation script
5. Executes validation
6. Generates comprehensive report with RCA for failures

## Input Requirements

### Required Parameters
- Optimized/New table path (e.g., `gold-project.gold_dataset.my_model`)
- Current/Existing table path (e.g., `silver-project.silver.my_model`)

### Required Config Values
```yaml
gcp:
  billing_project: "your-billing-project"

validation:
  row_count_threshold: 0.001
  null_threshold: 0.05
  enforce_priorities:
    - "CRITICAL"
    - "HIGH"

outputs:
  validation: "migration_validator/outputs"
```

## 6-Phase Validation Workflow

### Phase 1: Load Configuration

```
Read config/migration_config.yaml

Extract:
- BILLING_PROJECT = config.gcp.billing_project
- ROW_THRESHOLD = config.validation.row_count_threshold
- NULL_THRESHOLD = config.validation.null_threshold
- OUTPUT_PATH = config.outputs.validation
```

### Phase 2: Table Analysis

Generate Python script to analyze both tables.

**Analysis Script Template**:
```python
from google.cloud import bigquery
import json

# Use billing project from config
BILLING_PROJECT = "{BILLING_PROJECT}"
client = bigquery.Client(project=BILLING_PROJECT)

def analyze_table(table_path):
    """Analyze table schema, row count, and key columns."""
    project, dataset, table = table_path.split('.')

    # Get schema
    table_ref = client.get_table(f"{project}.{dataset}.{table}")
    schema = [{"name": f.name, "type": f.field_type, "mode": f.mode}
              for f in table_ref.schema]

    # Get row count
    query = f"SELECT COUNT(*) as cnt FROM `{table_path}`"
    result = client.query(query, project=BILLING_PROJECT).result()
    row_count = list(result)[0].cnt

    return {
        "table": table_path,
        "schema": schema,
        "row_count": row_count,
        "column_count": len(schema)
    }

# Analyze both tables
optimized = analyze_table("{OPTIMIZED_TABLE}")
current = analyze_table("{CURRENT_TABLE}")

# Save results
with open("{OUTPUT_PATH}/{model_name}/{model_name}_table_analysis.json", "w") as f:
    json.dump({"optimized": optimized, "current": current}, f, indent=2)
```

**Output**: `{OUTPUT_PATH}/{model_name}/{model_name}_table_analysis.json`

### Phase 3: Validation Test Design

Design tests based on table complexity:

| Table Complexity | Column Count | Test Count |
|------------------|--------------|------------|
| Simple | < 10 | 5-8 tests |
| Moderate | 10-30 | 8-12 tests |
| Complex | 30+ | 12-20 tests |

**Test Priority Levels**:

| Priority | Tests | Must Pass |
|----------|-------|-----------|
| CRITICAL | Row count, PK uniqueness, Date ranges | Yes |
| HIGH | Metric statistics, Distributions | 90%+ |
| MEDIUM | Secondary dimensions, Optional fields | Recommended |

**Standard Tests**:

1. **Row Count Comparison** (CRITICAL)
   - Threshold: `{ROW_THRESHOLD}` (from config)

2. **Primary Key Uniqueness** (CRITICAL)
   - Zero duplicates expected

3. **Date Range Validation** (CRITICAL)
   - Exact match expected

4. **NULL Value Analysis** (HIGH)
   - Threshold: `{NULL_THRESHOLD}` (from config)

5. **Metric Statistics** (HIGH)
   - SUM, AVG, MIN, MAX comparisons

6. **Categorical Distribution** (HIGH)
   - Top N value distributions

7. **Temporal Trends** (MEDIUM)
   - Monthly/daily counts

8. **Schema Comparison** (CRITICAL)
   - Column names and types

### Phase 4: Generate Validation Metrics Document

**Output**: `{OUTPUT_PATH}/{model_name}/validation_metrics_{model_name}.md`

**Structure**:
```markdown
# Validation Metrics: {model_name}

## Tables
- Optimized: `{optimized_table}`
- Current: `{current_table}`

## Configuration
- Billing Project: {BILLING_PROJECT}
- Row Count Threshold: {ROW_THRESHOLD}
- NULL Threshold: {NULL_THRESHOLD}

## Tests

### Test 1: Row Count Comparison (CRITICAL)

**Purpose**: Verify row counts match within threshold

**Optimized Query**:
```sql
SELECT COUNT(*) as cnt FROM `{optimized_table}`
```

**Current Query**:
```sql
SELECT COUNT(*) as cnt FROM `{current_table}`
```

**Threshold**: ±{ROW_THRESHOLD}%
**Pass Criteria**: abs(opt - curr) / curr <= {ROW_THRESHOLD}

[Continue for all tests...]
```

### Phase 5: Generate Python Validation Script

**Output**: `migration_validator/scripts/{model_name}/validation_script_{model_name}.py`

**Script Template**:
```python
#!/usr/bin/env python3
"""
Validation Script: {model_name}
Generated for migration validation.
"""

from google.cloud import bigquery
from datetime import datetime

# Configuration from config/migration_config.yaml
BILLING_PROJECT = "{BILLING_PROJECT}"
OPTIMIZED_TABLE = "{optimized_table}"
CURRENT_TABLE = "{current_table}"

# Thresholds from config
ROW_THRESHOLD = {ROW_THRESHOLD}
NULL_THRESHOLD = {NULL_THRESHOLD}

client = bigquery.Client(project=BILLING_PROJECT)

def run_query(sql):
    """Execute query using billing project."""
    return client.query(sql, project=BILLING_PROJECT).result()

def test_row_count():
    """Test 1: Row Count Comparison (CRITICAL)"""
    opt_count = list(run_query(f"SELECT COUNT(*) as cnt FROM `{OPTIMIZED_TABLE}`"))[0].cnt
    curr_count = list(run_query(f"SELECT COUNT(*) as cnt FROM `{CURRENT_TABLE}`"))[0].cnt

    diff_pct = abs(opt_count - curr_count) / curr_count if curr_count > 0 else 0
    passed = diff_pct <= ROW_THRESHOLD

    return {
        "test": "Row Count Comparison",
        "priority": "CRITICAL",
        "optimized": opt_count,
        "current": curr_count,
        "difference": f"{diff_pct:.4%}",
        "threshold": f"±{ROW_THRESHOLD:.4%}",
        "passed": passed
    }

# [Additional test functions...]

def main():
    results = []

    print("=" * 60)
    print(f"Validation: {OPTIMIZED_TABLE.split('.')[-1]}")
    print("=" * 60)

    # Run all tests
    tests = [
        test_row_count,
        # Add more tests...
    ]

    for test_func in tests:
        result = test_func()
        results.append(result)
        status = "✅" if result["passed"] else "❌"
        print(f"{status} {result['test']}: {result.get('difference', 'N/A')}")

    # Summary
    passed = sum(1 for r in results if r["passed"])
    total = len(results)
    print("=" * 60)
    print(f"Results: {passed}/{total} passed ({passed/total:.1%})")

    return results

if __name__ == "__main__":
    main()
```

### Phase 6: Execute and Generate Report

Run the validation script and generate comprehensive report.

**Output**: `{OUTPUT_PATH}/{model_name}/validation_report_{model_name}_{timestamp}.md`

**Report Structure**:
```markdown
# Validation Report: {model_name}

## Execution Info
- Date: {timestamp}
- Billing Project: {BILLING_PROJECT}
- Optimized Table: {optimized_table}
- Current Table: {current_table}

## Validation Status: {✅ PASSED | ❌ FAILED}
## Deployment Decision: {✅ APPROVED FOR DEPLOYMENT | ❌ NOT READY FOR DEPLOYMENT}

## Executive Summary
- Total Tests: {N}
- Passed: {X} ✅
- Failed: {Y} ❌
- Pass Rate: {X/N}%

## Test Breakdown by Priority
- **Critical**: {X}/{Y} passed
- **High**: {X}/{Y} passed
- **Medium**: {X}/{Y} passed

## Detailed Results

### ✅ Test 1: Row Count Comparison (CRITICAL)
- Optimized: {X} rows
- Current: {Y} rows
- Difference: {Z}%
- Threshold: ±{threshold}%
- Status: PASSED

### ❌ Test N: [Failed Test] (PRIORITY)
- [Test details]
- Status: FAILED

**Root Cause Analysis (RCA)**:

**Likely Causes** (ranked by probability):
1. [Primary hypothesis with explanation]
2. [Secondary hypothesis]
3. [Other potential causes]

**Supporting Evidence**:
- [Data patterns observed]
- [Specific metrics]

**Severity**: {CRITICAL | HIGH | MEDIUM}

**Investigation SQL**:
```sql
-- Query to diagnose root cause
SELECT ...
```

**Remediation SQL**:
```sql
-- Query or code change to fix issue
ALTER TABLE ...
-- OR SQL pattern to apply in model
```

**Process Fixes**:
- [ETL changes needed]
- [Monitoring to add]

**Timeline**: {X hours/days}
**Owner**: {Team responsible}

## Recommendations
[Summary of next steps]
```

## Deployment Decision Logic

**APPROVED FOR DEPLOYMENT**:
- All CRITICAL tests passed (100%)
- HIGH tests passed (>90%)
- Failed tests have clear mitigation

**NOT READY FOR DEPLOYMENT**:
- Any CRITICAL test failed
- Multiple HIGH tests failed (>10%)
- Unexplained discrepancies

## RCA Template

For every failed test, provide:

1. **Likely Causes** - Ranked by probability
2. **Supporting Evidence** - Data patterns
3. **Severity** - CRITICAL/HIGH/MEDIUM
4. **Investigation SQL** - Diagnostic query
5. **Remediation SQL** - Fix to apply
6. **Process Fixes** - Workflow changes
7. **Timeline & Owner** - Responsibility

## Output Directory Structure

```
migration_validator/
├── outputs/{model_name}/
│   ├── {model_name}_table_analysis.json
│   ├── validation_metrics_{model_name}.md
│   └── validation_report_{model_name}_{timestamp}.md
└── scripts/{model_name}/
    ├── analyze_{model_name}_tables.py
    └── validation_script_{model_name}.py
```

## Best Practices

1. **Use Config Values**: Billing project and thresholds from config
2. **Appropriate Tests**: Match test count to complexity
3. **RCA for Every Failure**: Never skip root cause analysis
4. **Executable Scripts**: All scripts must run standalone
5. **Clear Decision**: Explicit APPROVED or NOT READY

## Common SQL Refinement Patterns

When validation fails, the SQL Refinement Loop may be required. Here are common patterns and solutions:

### Pattern 1: Primary Key Deduplication

**Symptom**: Primary Key Uniqueness test fails
- Error: "N duplicate rows found for primary key column"

**Root Cause**: Source data contains exact row duplicates

**Solution**:
1. Rename original CTE to preserve business logic:
   ```sql
   src_data_raw as (
     select * from `source.table`
   )
   ```

2. Add deduplication CTE with window function:
   ```sql
   src_data as (
     select
       *,
       ROW_NUMBER() OVER(PARTITION BY primary_key ORDER BY timestamp_col DESC) as rn
     from src_data_raw
   )
   ```

3. Filter to keep only unique records:
   ```sql
   final as (
     select * from src_data WHERE rn = 1
   )
   ```

**When to Use**:
- Primary Key Uniqueness test fails
- Source system has known duplicate issues

### Pattern 2: Partition Data Type Mismatch

**Symptom**: Partition configuration error during dbt run
- Error: "PARTITION BY expression must be DATE(...)"

**Root Cause**: Partition config specifies wrong data type

**Solution**:
Use MCP `get_table_info` to inspect source schema, then update partition config:
```sql
{{ config(
    partition_by={
        "field": "date_field",
        "data_type": "date",  -- Match actual source type
        "granularity": "day"
    }
) }}
```

### Pattern 3: Dataset Location Mismatch

**Symptom**: BigQuery 404 error during validation
- Error: "Dataset was not found in location"

**Root Cause**: Table exists in different dataset than expected

**Solution**:
Use MCP `list_table_ids` or `search_catalog` to find correct table path:
```python
mcp__bigquery-data-analytics__search_catalog(
  prompt="table_name",
  types=["TABLE", "VIEW"]
)
```

## Success Criteria

- Configuration loaded and applied from config file
- Appropriate number of tests designed based on table complexity
- Validation tests tailored to specific table structure
- All critical data quality dimensions covered
- Python scripts complete, executable, use config billing project
- Deployment decision clear and justified
- Every failed test includes:
  - Root Cause Analysis with likely causes
  - Investigation SQL to diagnose
  - Remediation SQL to fix
  - Timeline and owner estimates
- All files saved to correct directories
- Clear next steps provided

## Example Usage

**User prompt**:
```
Validate my-project.my_dataset.my_model against
staging-project.staging.my_model
Using config: config/migration_config.yaml
```

**Agent will produce**:
1. `validation_metrics_my_model.md` - Test specifications with SQL
2. `validation_script_my_model.py` - Executable validation script
3. `validation_report_my_model_<timestamp>.md` - Comprehensive report with RCA

**All saved to**:
- Outputs: `migration_validator/outputs/my_model/`
- Scripts: `migration_validator/scripts/my_model/`

---

**Cookbook Version**: 2.0 (Generic)
**Configuration**: config/migration_config.yaml
**Output**: Validation reports, scripts, analysis
