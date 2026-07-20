#!/usr/bin/env bash
# Phase 2b: create a tiny Apache Iceberg table in Glue via Athena (serverless),
# and insert a handful of rows. Cost is negligible (Athena bills ~$5/TB scanned;
# this scans a few KB).
set -euo pipefail
cd "$(dirname "$0")/.."
source ./config.local.env

ATHENA_OUTPUT="s3://${S3_BUCKET}/athena-results/"
TABLE_LOC="s3://${S3_BUCKET}/warehouse/${ICEBERG_TABLE}"

run_athena() {
  local sql="$1"
  local qid
  qid="$(aws athena start-query-execution \
    --query-string "${sql}" \
    --query-execution-context "Database=${GLUE_DATABASE}" \
    --result-configuration "OutputLocation=${ATHENA_OUTPUT}" \
    --query QueryExecutionId --output text)"
  echo "  submitted ${qid}"
  while true; do
    local state
    state="$(aws athena get-query-execution --query-execution-id "${qid}" \
      --query 'QueryExecution.Status.State' --output text)"
    case "${state}" in
      SUCCEEDED) echo "  SUCCEEDED"; break ;;
      FAILED|CANCELLED)
        echo "  ${state}:" >&2
        aws athena get-query-execution --query-execution-id "${qid}" \
          --query 'QueryExecution.Status.StateChangeReason' --output text >&2
        exit 1 ;;
      *) sleep 2 ;;
    esac
  done
}

echo "== Create Iceberg table ${GLUE_DATABASE}.${ICEBERG_TABLE} =="
run_athena "CREATE TABLE IF NOT EXISTS ${ICEBERG_TABLE} (
  user_id   bigint,
  action    string,
  event_date date
)
LOCATION '${TABLE_LOC}'
TBLPROPERTIES ('table_type'='ICEBERG', 'format'='parquet');"

echo "== Insert sample rows =="
run_athena "INSERT INTO ${ICEBERG_TABLE} VALUES
  (1, 'login',    DATE '2026-04-01'),
  (2, 'purchase', DATE '2026-04-01'),
  (1, 'logout',   DATE '2026-04-01'),
  (3, 'login',    DATE '2026-04-02'),
  (2, 'login',    DATE '2026-04-02'),
  (3, 'purchase', DATE '2026-04-02'),
  (1, 'purchase', DATE '2026-04-03'),
  (4, 'login',    DATE '2026-04-03');"

echo "== Verify from Athena =="
run_athena "SELECT action, COUNT(*) AS n FROM ${ICEBERG_TABLE} GROUP BY action;"
echo "Iceberg table ready at ${TABLE_LOC}"
