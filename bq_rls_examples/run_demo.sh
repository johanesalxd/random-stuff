#!/usr/bin/env bash
# =============================================================================
# run_demo.sh -- End-to-end driver for the BigQuery dynamic Row-Level Security
# demo. Creates a dataset, applies each row access policy variant, and queries
# the table as two different identities to PROVE that filtering is per-user.
#
# Usage:
#   bash run_demo.sh           # run the full end-to-end demo (leaves resources up)
#   bash run_demo.sh cleanup   # drop the dataset/policies and revoke IAM grants
#
# Requirements:
#   - bq + gcloud installed and authenticated for BOTH users below.
#   - ADMIN_USER must be a project owner / BigQuery admin.
#
# The .sql files use placeholders (<PROJECT_ID>, <DATASET>, <ADMIN_USER>,
# <ANALYST_USER>) so they are safe to publish. This script substitutes real
# values at runtime into temp files under /tmp.
# =============================================================================
set -euo pipefail

# ---- Configuration (override via environment if desired) --------------------
PROJECT="${PROJECT:-your-gcp-project}"
DATASET="${DATASET:-bq_rls_examples}"
ADMIN_USER="${ADMIN_USER:-data-admin@example.com}"
ANALYST_USER="${ANALYST_USER:-analyst@example.com}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TMP_DIR="$(mktemp -d /tmp/rls_demo.XXXXXX)"

# Remember the caller's active account and restore it on exit.
ORIG_ACCOUNT="$(gcloud config get-value account 2>/dev/null || true)"
cleanup_tmp() {
  rm -rf "$TMP_DIR"
  if [[ -n "${ORIG_ACCOUNT}" && "${ORIG_ACCOUNT}" != "(unset)" ]]; then
    gcloud config set account "$ORIG_ACCOUNT" >/dev/null 2>&1 || true
  fi
}
trap cleanup_tmp EXIT

hr()  { printf '%s\n' "------------------------------------------------------------"; }
banner() { hr; printf '>>> %s\n' "$1"; hr; }

use_account() { gcloud config set account "$1" >/dev/null 2>&1; }

# Render a .sql file with placeholders substituted -> prints temp path.
render() {
  local src="$1" out="$TMP_DIR/$(basename "$1")"
  sed -e "s|<PROJECT_ID>|${PROJECT}|g" \
      -e "s|<DATASET>|${DATASET}|g" \
      -e "s|<ADMIN_USER>|${ADMIN_USER}|g" \
      -e "s|<ANALYST_USER>|${ANALYST_USER}|g" \
      "$src" > "$out"
  printf '%s' "$out"
}

# Run a rendered .sql file (multi-statement script) under the given account.
run_file_as() {
  local account="$1" file; file="$(render "$2")"
  use_account "$account"
  bq query --project_id="$PROJECT" --use_legacy_sql=false --format=none \
    " $(cat "$file")"
}

# Run an ad-hoc query string under the given account and pretty-print results.
run_query_as() {
  local account="$1" sql="$2"
  sql="${sql//<PROJECT_ID>/$PROJECT}"
  sql="${sql//<DATASET>/$DATASET}"
  use_account "$account"
  bq query --project_id="$PROJECT" --use_legacy_sql=false --format=pretty " $sql"
}

VISIBLE_QUERY='SELECT txn_id, store_code, region, product, amount
FROM `<PROJECT_ID>.<DATASET>.sales` ORDER BY txn_id'
COUNT_QUERY='SELECT SESSION_USER() AS running_as, COUNT(*) AS visible_rows
FROM `<PROJECT_ID>.<DATASET>.sales`'

# =============================================================================
do_cleanup() {
  banner "CLEANUP: dropping dataset/policies and revoking IAM grants"
  use_account "$ADMIN_USER"
  run_file_as "$ADMIN_USER" "$SCRIPT_DIR/99_cleanup.sql" || true
  gcloud projects remove-iam-policy-binding "$PROJECT" \
    --member="user:${ANALYST_USER}" --role="roles/bigquery.jobUser" \
    --quiet >/dev/null 2>&1 || true
  echo "Cleanup complete."
}

# =============================================================================
do_demo() {
  banner "STEP 0: Create dataset, fact table, and mapping tables (as ADMIN)"
  run_file_as "$ADMIN_USER" "$SCRIPT_DIR/00_setup.sql"
  echo "Setup complete."

  banner "STEP 1: Grant the analyst permission to run jobs and read the table"
  use_account "$ADMIN_USER"
  gcloud projects add-iam-policy-binding "$PROJECT" \
    --member="user:${ANALYST_USER}" --role="roles/bigquery.jobUser" \
    --quiet >/dev/null
  bq add-iam-policy-binding \
    --member="user:${ANALYST_USER}" --role="roles/bigquery.dataViewer" \
    "${PROJECT}:${DATASET}.sales" >/dev/null
  echo "Granted roles/bigquery.jobUser (project) + roles/bigquery.dataViewer (sales)."

  banner "STEP 2 (BEFORE): Hardcoded OFFSET policy -- 2 ranges hardcoded"
  run_file_as "$ADMIN_USER" "$SCRIPT_DIR/01_current_approach_hardcoded.sql"
  echo "[ADMIN sees all rows -- TRUE filter]"
  run_query_as "$ADMIN_USER" "$COUNT_QUERY"
  echo "[ANALYST sees only mapped ranges A010-A020 and 4077-4085]"
  run_query_as "$ANALYST_USER" "$VISIBLE_QUERY"
  run_query_as "$ANALYST_USER" "$COUNT_QUERY"

  banner "STEP 3: Documented IN-subquery policy (discrete allowlist)"
  run_file_as "$ADMIN_USER" "$SCRIPT_DIR/02_solution_in_subquery.sql"
  echo "[ANALYST allowlist = {A010, 4079} -> expect 2 rows]"
  run_query_as "$ANALYST_USER" "$VISIBLE_QUERY"

  banner "STEP 4 (AFTER): Dynamic range policy via dimension expansion (one policy, N ranges)"
  run_file_as "$ADMIN_USER" "$SCRIPT_DIR/03_solution_dynamic_range.sql"
  echo "[ANALYST sees ranges A010-A020 and 4077-4085 -> expect 7 rows]"
  run_query_as "$ANALYST_USER" "$VISIBLE_QUERY"
  run_query_as "$ANALYST_USER" "$COUNT_QUERY"

  banner "STEP 5: Add a THIRD range (Z010-Z020) -- DATA change only, no DDL"
  use_account "$ADMIN_USER"
  bq query --project_id="$PROJECT" --use_legacy_sql=false --format=none \
    "INSERT INTO \`${PROJECT}.${DATASET}.access_map\`
       (email, column_name, low_value, high_value)
     VALUES ('${ANALYST_USER}', 'store_code', 'Z010', 'Z020')"
  echo "Inserted range Z010-Z020 for the analyst."
  echo "[Dynamic policy is still in force -> analyst should NOW also see Z014, Z015 -> expect 9 rows]"
  run_query_as "$ANALYST_USER" "$VISIBLE_QUERY"
  run_query_as "$ANALYST_USER" "$COUNT_QUERY"

  banner "STEP 6: Prove the hardcoded policy does NOT scale"
  run_file_as "$ADMIN_USER" "$SCRIPT_DIR/01_current_approach_hardcoded.sql"
  echo "[Hardcoded policy only evaluates 2 ranges -> Z014/Z015 are MISSED -> still 7 rows]"
  run_query_as "$ANALYST_USER" "$COUNT_QUERY"
  echo
  echo "Re-applying the dynamic range policy as the recommended end state..."
  run_file_as "$ADMIN_USER" "$SCRIPT_DIR/03_solution_dynamic_range.sql"

  banner "DONE"
  echo "Resources left standing in ${PROJECT}.${DATASET}."
  echo "Log in as ${ANALYST_USER} in the BigQuery console to verify visually,"
  echo "or run:  bash run_demo.sh cleanup"
}

# =============================================================================
case "${1:-demo}" in
  demo)    do_demo ;;
  cleanup) do_cleanup ;;
  *) echo "Usage: bash run_demo.sh [demo|cleanup]" >&2; exit 1 ;;
esac
