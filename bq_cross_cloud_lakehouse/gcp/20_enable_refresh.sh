#!/usr/bin/env bash
# Phase 3c: after the AWS trust policy is finalized + propagated, turn on
# background metadata refresh (>= 300s).
set -euo pipefail
cd "$(dirname "$0")/.."
source ./config.local.env

echo "== Enable 300s metadata refresh on ${FEDERATED_CATALOG} =="
gcloud alpha biglake iceberg catalogs update "${FEDERATED_CATALOG}" \
  --project="${GCP_PROJECT}" \
  --refresh-interval="300s"
echo "Done."
