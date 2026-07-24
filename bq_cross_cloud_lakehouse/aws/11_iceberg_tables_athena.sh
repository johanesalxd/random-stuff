#!/usr/bin/env bash
# Phase 2b: create the two Froyo Apache Iceberg tables in Glue via Athena
# (serverless) and populate them. These physically live in AWS S3; BigQuery
# reads them cross-cloud via the federated Lakehouse catalog.
#
#   - global_loyalty : customer loyalty (joined with allergen knowledge in BQ)
#   - sales_history  : historical daily sales (BQML ARIMA_PLUS forecast source)
#
# Cost is negligible (Athena bills ~$5/TB scanned; this scans a few KB/MB).
# Safe to re-run: inserts are guarded by a row-count check.
set -euo pipefail
cd "$(dirname "$0")/.."
source ./config.local.env

ATHENA_OUTPUT="s3://${S3_BUCKET}/athena-results/"
LOYALTY_LOC="s3://${S3_BUCKET}/warehouse/${FROYO_LOYALTY_TABLE}"
SALES_LOC="s3://${S3_BUCKET}/warehouse/${FROYO_SALES_TABLE}"

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

# ---------------------------------------------------------------------------
# 1) global_loyalty
# ---------------------------------------------------------------------------
echo "== Create Iceberg table ${GLUE_DATABASE}.${FROYO_LOYALTY_TABLE} =="
run_athena "CREATE TABLE IF NOT EXISTS ${FROYO_LOYALTY_TABLE} (
  customer_id       bigint,
  region            string,
  loyalty_tier      string,
  favorite_flavor   string,
  avg_monthly_spend double,
  soy_sensitive_flag boolean,
  last_order_date   date
)
LOCATION '${LOYALTY_LOC}'
TBLPROPERTIES ('table_type'='ICEBERG', 'format'='parquet');"

echo "== Seed global_loyalty (idempotent) =="
LOYALTY_ROWS="$(athena_scalar "SELECT COUNT(*) FROM ${FROYO_LOYALTY_TABLE};")"
if [[ "${LOYALTY_ROWS}" == "0" ]]; then
  run_athena "INSERT INTO ${FROYO_LOYALTY_TABLE} VALUES
    (1001, 'APAC', 'Platinum', 'Midnight Swirl',       82.50, false, DATE '2026-03-28'),
    (1002, 'APAC', 'Gold',     'Midnight Swirl',       47.00, true,  DATE '2026-03-30'),
    (1003, 'APAC', 'Silver',   'Midnight Papaya Halo', 23.75, false, DATE '2026-02-14'),
    (1004, 'EMEA', 'Gold',     'Midnight Swirl',       55.20, false, DATE '2026-04-01'),
    (1005, 'EMEA', 'Bronze',   'Arctic Basil Flow',    12.10, true,  DATE '2026-01-22'),
    (1006, 'EMEA', 'Platinum', 'Midnight Swirl',       96.00, false, DATE '2026-04-03'),
    (1007, 'AMER', 'Gold',     'Aura Berry Impact',    61.40, true,  DATE '2026-03-11'),
    (1008, 'AMER', 'Silver',   'Midnight Swirl',       29.90, false, DATE '2026-03-19'),
    (1009, 'AMER', 'Platinum', 'Midnight Swirl',       88.30, false, DATE '2026-04-02'),
    (1010, 'APAC', 'Gold',     'Midnight Swirl',       44.65, true,  DATE '2026-03-27'),
    (1011, 'EMEA', 'Silver',   'Midnight Swirl',       31.20, false, DATE '2026-03-05'),
    (1012, 'AMER', 'Bronze',   'Midnight Papaya Halo', 15.00, false, DATE '2026-02-28'),
    (1013, 'APAC', 'Platinum', 'Midnight Swirl',       74.80, false, DATE '2026-04-04'),
    (1014, 'EMEA', 'Gold',     'Aura Berry Impact',    52.10, true,  DATE '2026-03-21'),
    (1015, 'AMER', 'Gold',     'Midnight Swirl',       58.40, false, DATE '2026-03-30');"
else
  echo "  table already has ${LOYALTY_ROWS} rows; skipping insert."
fi

# ---------------------------------------------------------------------------
# 2) sales_history  (synthesized daily series: trend + weekly seasonality)
# ---------------------------------------------------------------------------
echo "== Create Iceberg table ${GLUE_DATABASE}.${FROYO_SALES_TABLE} =="
run_athena "CREATE TABLE IF NOT EXISTS ${FROYO_SALES_TABLE} (
  sale_date    date,
  product_name string,
  region       string,
  units_sold   int,
  revenue      double
)
LOCATION '${SALES_LOC}'
TBLPROPERTIES ('table_type'='ICEBERG', 'format'='parquet');"

echo "== Seed sales_history (idempotent; 2024-07-01..2026-06-30 daily x 3 regions) =="
SALES_ROWS="$(athena_scalar "SELECT COUNT(*) FROM ${FROYO_SALES_TABLE};")"
if [[ "${SALES_ROWS}" == "0" ]]; then
  run_athena "INSERT INTO ${FROYO_SALES_TABLE}
  SELECT
    dt AS sale_date,
    'Midnight Swirl' AS product_name,
    r  AS region,
    u  AS units_sold,
    round(u * 6.50, 2) AS revenue
  FROM (
    SELECT dt, r,
      CAST(GREATEST(5, round(
          40
        + 0.04 * date_diff('day', DATE '2024-07-01', dt)          -- upward trend
        + 12   * sin(2 * pi() * day_of_week(dt) / 7.0)            -- weekly seasonality
        + 8    * (rand() - 0.5)                                    -- noise
        + (CASE r WHEN 'APAC' THEN 20 WHEN 'EMEA' THEN 10 ELSE 0 END)
      )) AS integer) AS u
    FROM UNNEST(sequence(DATE '2024-07-01', DATE '2026-06-30', INTERVAL '1' day)) AS t(dt)
    CROSS JOIN (VALUES ('APAC'), ('EMEA'), ('AMER')) AS x(r)
  );"
else
  echo "  table already has ${SALES_ROWS} rows; skipping insert."
fi

echo "== Verify from Athena =="
echo "  ${FROYO_LOYALTY_TABLE} rows: $(athena_scalar "SELECT COUNT(*) FROM ${FROYO_LOYALTY_TABLE};")"
echo "  ${FROYO_SALES_TABLE} rows:  $(athena_scalar "SELECT COUNT(*) FROM ${FROYO_SALES_TABLE};")"
echo "Iceberg tables ready:"
echo "  ${LOYALTY_LOC}"
echo "  ${SALES_LOC}"
