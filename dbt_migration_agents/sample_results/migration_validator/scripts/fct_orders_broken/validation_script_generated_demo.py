#!/usr/bin/env python3
import sys

from google.api_core.exceptions import GoogleAPICallError
from google.cloud import bigquery


def run_validation():
    # Configuration
    # PROD = Baseline (Existing/Broken), PR = Candidate (New/Fix)
    PROD_TABLE_ID = "sample-project.sample_gold.fct_orders_broken"
    PR_TABLE_ID = "sample-project.sample_gold.fct_orders"

    # Thresholds
    ROW_COUNT_THRESHOLD = 0.01  # 1%
    METRIC_THRESHOLD = 0.01     # 1%
    PRIMARY_KEY = "order_id"
    NUMERIC_COLUMNS = ["order_total_usd", "total_line_items"]

    print("=" * 50)
    print(f"Starting Validation")
    print(f"Baseline (PROD): {PROD_TABLE_ID}")
    print(f"Candidate (PR):  {PR_TABLE_ID}")
    print("=" * 50)

    client = bigquery.Client()
    errors = []

    # Helper function to get table info
    def get_table_details(table_id):
        try:
            table = client.get_table(table_id)
            return table
        except Exception as e:
            print(f"Failed to fetch table {table_id}: {e}")
            sys.exit(1)

    # 1. Schema Validation
    print("\n[Test 1] Schema Validation...")
    prod_table = get_table_details(PROD_TABLE_ID)
    pr_table = get_table_details(PR_TABLE_ID)

    prod_schema = {f.name: f.field_type for f in prod_table.schema}
    pr_schema = {f.name: f.field_type for f in pr_table.schema}

    # Check for missing columns
    missing_cols = set(prod_schema.keys()) - set(pr_schema.keys())
    if missing_cols:
        msg = f"Schema mismatch: Columns in PROD but missing in PR: {missing_cols}"
        print(f"  ❌ {msg}")
        errors.append(msg)

    # Check for type mismatches
    type_mismatch = []
    for col in set(prod_schema.keys()).intersection(set(pr_schema.keys())):
        if prod_schema[col] != pr_schema[col]:
            type_mismatch.append(f"{col} ({prod_schema[col]} != {pr_schema[col]})")

    if type_mismatch:
        msg = f"Schema mismatch: Column type differences: {type_mismatch}"
        print(f"  ❌ {msg}")
        errors.append(msg)

    if not missing_cols and not type_mismatch:
        print("  ✅ Schema columns and types match.")

    # 2. Row Count Validation
    print("\n[Test 2] Row Count Comparison...")
    prod_rows = prod_table.num_rows
    pr_rows = pr_table.num_rows

    print(f"  PROD Rows: {prod_rows}")
    print(f"  PR Rows:   {pr_rows}")

    if prod_rows == 0:
        print("  ⚠️ PROD table is empty. Skipping percentage comparison.")
    else:
        diff_pct = abs(prod_rows - pr_rows) / prod_rows
        if diff_pct > ROW_COUNT_THRESHOLD:
            msg = f"Row count difference {diff_pct:.2%} exceeds threshold {ROW_COUNT_THRESHOLD:.0%}"
            print(f"  ❌ {msg}")
            errors.append(msg)
        else:
            print(f"  ✅ Row count difference {diff_pct:.2%} is within threshold.")

    # 3. Primary Key Uniqueness (PR Table)
    print(f"\n[Test 3] Primary Key Uniqueness ({PRIMARY_KEY})...")
    pk_query = f"""
        SELECT
            COUNT(*) as total_rows,
            COUNT(DISTINCT {PRIMARY_KEY}) as unique_keys
        FROM `{PR_TABLE_ID}`
    """
    try:
        pk_job = client.query(pk_query)
        pk_res = list(pk_job.result())[0]

        if pk_res.total_rows != pk_res.unique_keys:
            duplicates = pk_res.total_rows - pk_res.unique_keys
            msg = f"Found {duplicates} duplicate records based on PK '{PRIMARY_KEY}' in PR table."
            print(f"  ❌ {msg}")
            errors.append(msg)
        else:
            print(f"  ✅ Primary key '{PRIMARY_KEY}' is unique.")
    except Exception as e:
        msg = f"Failed to run PK check: {e}"
        print(f"  ❌ {msg}")
        errors.append(msg)

    # 4. Numeric Metrics Comparison
    print("\n[Test 4] Numeric Metrics Comparison (SUM)...")

    # Construct query to get sums for both tables
    metric_cols_select = ", ".join([f"SUM({c}) as {c}" for c in NUMERIC_COLUMNS])

    def get_metrics(table_id):
        sql = f"SELECT {metric_cols_select} FROM `{table_id}`"
        return list(client.query(sql).result())[0]

    try:
        prod_metrics = get_metrics(PROD_TABLE_ID)
        pr_metrics = get_metrics(PR_TABLE_ID)

        for col in NUMERIC_COLUMNS:
            val_prod = getattr(prod_metrics, col) or 0
            val_pr = getattr(pr_metrics, col) or 0

            # Avoid division by zero
            if val_prod == 0:
                if val_pr == 0:
                    diff = 0
                else:
                    diff = 1.0 # 100% diff if baseline is 0 and new is not
            else:
                diff = abs(val_prod - val_pr) / abs(val_prod)

            status_icon = "✅" if diff <= METRIC_THRESHOLD else "❌"
            print(f"  Column: {col}")
            print(f"    PROD: {val_prod:,.2f}")
            print(f"    PR:   {val_pr:,.2f}")
            print(f"    Diff: {diff:.2%} {status_icon}")

            if diff > METRIC_THRESHOLD:
                errors.append(f"Metric {col} difference {diff:.2%} exceeds threshold {METRIC_THRESHOLD:.0%}")

    except Exception as e:
        msg = f"Failed to compare metrics: {e}"
        print(f"  ❌ {msg}")
        errors.append(msg)

    # Final Summary
    print("\n" + "=" * 50)
    if not errors:
        print("✅ Validation Passed")
        sys.exit(0)
    else:
        print("❌ Validation Failed")
        print("Failures:")
        for err in errors:
            print(f" - {err}")
        sys.exit(1)

if __name__ == "__main__":
    run_validation()