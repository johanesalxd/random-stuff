#!/usr/bin/env bash
# Phase 4b: forecast Q3 revenue for Midnight Swirl with BigQuery ML ARIMA_PLUS,
# trained DIRECTLY on the AWS-federated sales_history Iceberg table.
#
# This is the BigQuery-native forecast (keynote beat 7). The Serverless Spark /
# Lightning Engine notebook version is a later fidelity upgrade; the analytical
# result is equivalent.
#
# ARIMA_PLUS reference:
#   https://docs.cloud.google.com/bigquery/docs/reference/standard-sql/bigqueryml-syntax-create-time-series
#   https://docs.cloud.google.com/bigquery/docs/reference/standard-sql/bigqueryml-syntax-forecast
set -euo pipefail
cd "$(dirname "$0")/.."
source ./config.local.env

SALES="${GCP_PROJECT}.${FEDERATED_CATALOG}.${GLUE_DATABASE}.${FROYO_SALES_TABLE}"
MODEL="${GCP_PROJECT}.${FROYO_NATIVE_DATASET}.midnight_swirl_arima"
HORIZON="${1:-90}"   # forecast horizon in days (~ one quarter)

bq_query() { bq --location="${GCP_REGION}" --project_id="${GCP_PROJECT}" query --use_legacy_sql=false "$1"; }

echo "== Train ARIMA_PLUS on AWS-federated ${SALES} (per-region) =="
bq_query "
CREATE OR REPLACE MODEL \`${MODEL}\`
OPTIONS(
  model_type            = 'ARIMA_PLUS',
  time_series_timestamp_col = 'sale_date',
  time_series_data_col      = 'revenue',
  time_series_id_col        = 'region',
  data_frequency        = 'DAILY',
  horizon               = ${HORIZON}
) AS
SELECT sale_date, region, revenue
FROM \`${SALES}\`
WHERE product_name = 'Midnight Swirl'"

echo
echo "== Forecast next ${HORIZON} days per region =="
bq_query "
SELECT
  region,
  forecast_timestamp,
  ROUND(forecast_value, 2)        AS forecast_revenue,
  ROUND(prediction_interval_lower_bound, 2) AS lo,
  ROUND(prediction_interval_upper_bound, 2) AS hi
FROM ML.FORECAST(MODEL \`${MODEL}\`, STRUCT(${HORIZON} AS horizon, 0.9 AS confidence_level))
ORDER BY region, forecast_timestamp
LIMIT 20"

echo
echo "== Projected Midnight Swirl revenue over the next ${HORIZON} days (the 'Q3' number) =="
bq_query "
SELECT
  region,
  ROUND(SUM(forecast_value), 2) AS projected_revenue
FROM ML.FORECAST(MODEL \`${MODEL}\`, STRUCT(${HORIZON} AS horizon, 0.9 AS confidence_level))
GROUP BY region
ORDER BY projected_revenue DESC"
