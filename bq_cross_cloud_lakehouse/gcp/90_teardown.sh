#!/usr/bin/env bash
# Phase 5 (GCP): delete the federated catalog. Run AFTER the demo.
set -uo pipefail
cd "$(dirname "$0")/.."
source ./config.local.env

echo "== Delete native BigQuery dataset ${FROYO_NATIVE_DATASET} (tables + BQML model) =="
bq --project_id="${GCP_PROJECT}" rm -r -f --dataset "${GCP_PROJECT}:${FROYO_NATIVE_DATASET}" 2>/dev/null || true

echo "== Delete Knowledge Catalog DataScan (if created) =="
gcloud dataplex datascans delete "${DATASCAN_ID}" --location="${GCP_REGION}" --quiet 2>/dev/null || true

echo "== Revoke + delete BigQuery Cloud Resource connection (if created) =="
CONN="${GCP_PROJECT}.${GCP_REGION}.${BQ_CONNECTION_ID}"
CONN_SA="$(bq --project_id="${GCP_PROJECT}" --format=json show --connection "${CONN}" 2>/dev/null \
  | python3 -c 'import sys,json;d=json.load(sys.stdin);print(d["cloudResource"]["serviceAccountId"])' 2>/dev/null || true)"
if [[ -n "${CONN_SA:-}" ]]; then
  for ROLE in roles/bigquery.user roles/bigquery.dataEditor roles/aiplatform.user roles/dataplex.discoveryPublishingServiceAgent; do
    gcloud projects remove-iam-policy-binding "${GCP_PROJECT}" \
      --member="serviceAccount:${CONN_SA}" --role="${ROLE}" --condition=None --quiet >/dev/null 2>&1 || true
  done
fi
bq --project_id="${GCP_PROJECT}" rm --connection --force "${CONN}" 2>/dev/null || true

echo "== Delete GCS PDF bucket (if created) =="
gcloud storage rm --recursive "gs://${GCS_PDF_BUCKET}" --quiet 2>/dev/null || true

echo "== Delete federated catalog ${FEDERATED_CATALOG} =="
gcloud alpha biglake iceberg catalogs delete "${FEDERATED_CATALOG}" \
  --project="${GCP_PROJECT}" --quiet 2>/dev/null || true

echo "Done. (BigQuery shows the federated catalog automatically; no separate BQ dataset to delete for it.)"
