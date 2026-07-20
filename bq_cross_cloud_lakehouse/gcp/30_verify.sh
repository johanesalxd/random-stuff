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
