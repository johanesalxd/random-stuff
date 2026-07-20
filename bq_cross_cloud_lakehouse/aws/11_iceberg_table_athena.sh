#!/usr/bin/env bash
# Phase 2b: create a tiny Apache Iceberg table in Glue via Athena (serverless),
# and insert a handful of rows. Cost is negligible (Athena bills ~$5/TB scanned;
# this scans a few KB). Safe to re-run: the insert is guarded by a row-count check.
set -euo pipefail
cd "$(dirname "$0")/.."
source ./config.local.env

ATHENA_OUTPUT="s3://${S3_BUCKET}/athena-results/"
TABLE_LOC="s3://${S3_BUCKET}/warehouse/${ICEBERG_TABLE}"

# Submit a query, poll to completion, print the QueryExecutionId on stdout.
# All human-readable progress goes to stderr so stdout stays capturable.
_athena_run() {
  local sql="$1" qid state
  qid="$(aws athena start-query-execution \
    --query-string "${sql}" \
    --query-execution-context "Database=${GLUE_DATABASE}" \
    --result-configuration "OutputLocation=${ATHENA_OUTPUT}" \
    --query QueryExecutionId --output text)"
  echo "  submitted ${qid}" >&2
  while true; do
    state="$(aws athena get-query-execution --query-execution-id "${qid}" \
      --query 'QueryExecution.Status.State' --output text)"
    case "${state}" in
      SUCCEEDED) echo "  SUCCEEDED" >&2; break ;;
      FAILED|CANCELLED)
        echo "  ${state}:" >&2
        aws athena get-query-execution --query-execution-id "${qid}" \
          --query 'QueryExecution.Status.StateChangeReason' --output text >&2
        exit 1 ;;
      *) sleep 2 ;;
    esac
  done
  echo "${qid}"
}

# Run a query, discard results.
run_athena() { _athena_run "$1" >/dev/null; }

# Run a query and return the first result cell (Rows[0] is the header row).
athena_scalar() {
  local qid; qid="$(_athena_run "$1")"
  aws athena get-query-results --query-execution-id "${qid}" \
    --query 'ResultSet.Rows[1].Data[0].VarCharValue' --output text
}

echo "== Create Iceberg table ${GLUE_DATABASE}.${ICEBERG_TABLE} =="
run_athena "CREATE TABLE IF NOT EXISTS ${ICEBERG_TABLE} (
  user_id   bigint,
  action    string,
  event_date date
)
LOCATION '${TABLE_LOC}'
TBLPROPERTIES ('table_type'='ICEBERG', 'format'='parquet');"

echo "== Insert sample rows (idempotent: skipped if table already populated) =="
CURRENT_ROWS="$(athena_scalar "SELECT COUNT(*) FROM ${ICEBERG_TABLE};")"
if [[ "${CURRENT_ROWS}" == "0" ]]; then
  run_athena "INSERT INTO ${ICEBERG_TABLE} VALUES
    (1, 'login',    DATE '2026-04-01'),
    (2, 'purchase', DATE '2026-04-01'),
    (1, 'logout',   DATE '2026-04-01'),
    (3, 'login',    DATE '2026-04-02'),
    (2, 'login',    DATE '2026-04-02'),
    (3, 'purchase', DATE '2026-04-02'),
    (1, 'purchase', DATE '2026-04-03'),
    (4, 'login',    DATE '2026-04-03');"
else
  echo "  table already has ${CURRENT_ROWS} rows; skipping insert."
fi

echo "== Verify from Athena =="
run_athena "SELECT action, COUNT(*) AS n FROM ${ICEBERG_TABLE} GROUP BY action;"
echo "Iceberg table ready at ${TABLE_LOC}"
