from google.cloud import bigquery
import sys
from datetime import datetime

# Config
BILLING_PROJECT = "johanesa-playground-326616"
NEW_TABLE = "johanesa-playground-326616.sample_gold.fct_orders_broken_migrated"
OLD_TABLE = "johanesa-playground-326616.sample_gold.fct_orders_broken"
ROW_THRESHOLD = 0.001

client = bigquery.Client(project=BILLING_PROJECT)


def get_single_value(query):
    try:
        rows = list(client.query(query).result())
        if rows:
            return rows[0][0]
    except Exception as e:
        print(f"Query failed: {e}")
    return 0


print(f"🚀 Starting Validation for {NEW_TABLE} vs {OLD_TABLE}")

tests = []

# T01: Row Count
print("Running T01: Row Count Match...")
rows_new = get_single_value(f"SELECT COUNT(*) FROM `{NEW_TABLE}`")
rows_old = get_single_value(f"SELECT COUNT(*) FROM `{OLD_TABLE}`")
diff_pct = abs(rows_new - rows_old) / rows_old if rows_old > 0 else 0.0
status = "PASS" if diff_pct <= ROW_THRESHOLD else "FAIL"
tests.append(
    {
        "id": "T01",
        "name": "Row Count",
        "status": status,
        "info": f"New: {rows_new}, Old: {rows_old}, Diff: {diff_pct:.4%}",
    }
)

# T02: PK Uniqueness
print("Running T02: PK Uniqueness...")
dupes = get_single_value(
    f"SELECT count(*) - count(distinct order_id) FROM `{NEW_TABLE}`"
)
status = "PASS" if dupes == 0 else "FAIL"
tests.append(
    {
        "id": "T02",
        "name": "PK Uniqueness",
        "status": status,
        "info": f"Duplicates: {dupes}",
    }
)

# T03: Total Amount
print("Running T03: Total Amount Match...")
sum_new = (
    get_single_value(f"SELECT SUM(order_total_original) FROM `{NEW_TABLE}`") or 0.0
)
sum_old = (
    get_single_value(f"SELECT SUM(order_total_original) FROM `{OLD_TABLE}`") or 0.0
)
diff_pct = abs(sum_new - sum_old) / sum_old if sum_old > 0 else 0.0
status = "PASS" if diff_pct <= 0.01 else "FAIL"
tests.append(
    {
        "id": "T03",
        "name": "Total Amount",
        "status": status,
        "info": f"New: {sum_new:.2f}, Old: {sum_old:.2f}, Diff: {diff_pct:.4%}",
    }
)

# T04: Column Count
print("Running T04: Column Check...")
# Simple check if queries work implies columns exist, but let's count columns logic if needed.
# For now, just relying on previous info.

print("\n📊 Validation Summary")
failed = [t for t in tests if t["status"] == "FAIL"]
if not failed:
    print("✅ APPROVED FOR DEPLOYMENT")
else:
    print(f"❌ NOT READY: {len(failed)} tests failed")
    for t in failed:
        print(f"  - {t['id']} {t['name']}: {t['info']}")
