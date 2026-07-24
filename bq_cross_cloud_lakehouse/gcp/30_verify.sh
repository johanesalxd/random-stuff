#!/usr/bin/env bash
# Phase 3d: verify the catalog refreshed successfully and namespaces synced.
set -euo pipefail
cd "$(dirname "$0")/.."
source ./config.local.env

echo "== Catalog status =="
gcloud alpha biglake iceberg catalogs describe "${FEDERATED_CATALOG}" \
  --project="${GCP_PROJECT}"

echo
echo "== Synced namespaces (expect: ${GLUE_DATABASE}) =="
gcloud alpha biglake iceberg namespaces list \
  --project="${GCP_PROJECT}" \
  --catalog="${FEDERATED_CATALOG}"

echo
echo "== Confirm the Froyo Iceberg tables are queryable from BigQuery =="
for T in "${FROYO_LOYALTY_TABLE}" "${FROYO_SALES_TABLE}"; do
  FQTN="${GCP_PROJECT}.${FEDERATED_CATALOG}.${GLUE_DATABASE}.${T}"
  echo "-- ${FQTN}"
  bq --location="${GCP_REGION}" --project_id="${GCP_PROJECT}" query --use_legacy_sql=false \
    "SELECT COUNT(*) AS rows FROM \`${FQTN}\`" || echo "  (not synced yet; re-run until it appears)"
done
