#!/usr/bin/env bash
# Phase 4: query the remote AWS Glue Iceberg table from BigQuery.
# 4-part path: project.federated_catalog.namespace.table
set -euo pipefail
cd "$(dirname "$0")/.."
source ./config.local.env

FQTN="${GCP_PROJECT}.${FEDERATED_CATALOG}.${GLUE_DATABASE}.${ICEBERG_TABLE}"

echo "== SELECT * (LIMIT 10) from ${FQTN} =="
bq --location="${GCP_REGION}" --project_id="${GCP_PROJECT}" query --use_legacy_sql=false \
  "SELECT * FROM \`${FQTN}\` LIMIT 10"

echo
echo "== Aggregate demo: actions per day =="
bq --location="${GCP_REGION}" --project_id="${GCP_PROJECT}" query --use_legacy_sql=false \
  "SELECT event_date, action, COUNT(*) AS total
   FROM \`${FQTN}\`
   GROUP BY 1,2 ORDER BY 1,2"
