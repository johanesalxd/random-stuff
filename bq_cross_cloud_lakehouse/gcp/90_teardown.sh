#!/usr/bin/env bash
# Phase 5 (GCP): delete the federated catalog. Run AFTER the demo.
set -uo pipefail
cd "$(dirname "$0")/.."
source ./config.local.env

echo "== Delete federated catalog ${FEDERATED_CATALOG} =="
gcloud alpha biglake iceberg catalogs delete "${FEDERATED_CATALOG}" \
  --project="${GCP_PROJECT}" --quiet 2>/dev/null || true

echo "Done. (BigQuery shows the federated catalog automatically; no separate BQ dataset to delete.)"
