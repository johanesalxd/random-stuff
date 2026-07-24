#!/usr/bin/env bash
# Phase 4 (OPTIONAL): the "real" Knowledge Catalog (Dataplex) extraction path.
#
# This reproduces the keynote/codelab flow that turns the raw recipe/supplier
# PDFs into structured BigQuery tables using AI — WITHOUT Spark:
#   1. Upload assets/pdfs/** to a GCS bucket.
#   2. Create a BigQuery Cloud Resource connection + grant it access.
#   3. Create + run a Dataplex DataScan with semantic (entity) inference, which
#      publishes BigLake object tables and inferred structured data into BigQuery.
#
# The deterministic seed (gcp/05_seed_native_bq.sh) already provides the same
# knowledge tables for a reliable demo; run this only when you want to show the
# live "dark PDF -> structured data" extraction.
#
# Docs:
#   https://docs.cloud.google.com/dataplex/docs/data-insights-unstructured-data
#   https://docs.cloud.google.com/bigquery/docs/create-cloud-resource-connection
set -euo pipefail
cd "$(dirname "$0")/.."
source ./config.local.env

CONN="${GCP_PROJECT}.${GCP_REGION}.${BQ_CONNECTION_ID}"

echo "== 1. GCS bucket for PDFs: gs://${GCS_PDF_BUCKET} (${GCP_REGION}) =="
if gcloud storage buckets describe "gs://${GCS_PDF_BUCKET}" >/dev/null 2>&1; then
  echo "  bucket already exists."
else
  gcloud storage buckets create "gs://${GCS_PDF_BUCKET}" \
    --project="${GCP_PROJECT}" --location="${GCP_REGION}" --uniform-bucket-level-access
fi

echo "== Upload PDFs (one file format per folder, as DataScan requires) =="
gcloud storage rsync --recursive assets/pdfs/recipes   "gs://${GCS_PDF_BUCKET}/recipes"
gcloud storage rsync --recursive assets/pdfs/suppliers "gs://${GCS_PDF_BUCKET}/suppliers"

echo "== 2. BigQuery Cloud Resource connection ${CONN} =="
if bq --project_id="${GCP_PROJECT}" show --connection "${CONN}" >/dev/null 2>&1; then
  echo "  connection already exists."
else
  bq mk --connection --location="${GCP_REGION}" --project_id="${GCP_PROJECT}" \
    --connection_type=CLOUD_RESOURCE "${BQ_CONNECTION_ID}"
fi
CONN_SA="$(bq --project_id="${GCP_PROJECT}" --format=json show --connection "${CONN}" \
  | python3 -c 'import sys,json;print(json.load(sys.stdin)["cloudResource"]["serviceAccountId"])')"
echo "  connection service account: ${CONN_SA}"

echo "== 3. Grant the connection SA the roles the DataScan needs =="
gcloud storage buckets add-iam-policy-binding "gs://${GCS_PDF_BUCKET}" \
  --member="serviceAccount:${CONN_SA}" --role="roles/storage.objectViewer" >/dev/null
for ROLE in roles/aiplatform.user roles/dataplex.serviceAgent roles/bigquery.dataEditor; do
  gcloud projects add-iam-policy-binding "${GCP_PROJECT}" \
    --member="serviceAccount:${CONN_SA}" --role="${ROLE}" --condition=None >/dev/null 2>&1 || true
done

echo "== 4. Create the Dataplex DataScan (semantic inference on) =="
DATAPLEX_API="dataplex.googleapis.com/v1/projects/${GCP_PROJECT}/locations/${GCP_REGION}"
# Payload follows the current documented shape for unstructured-data discovery
# with semantic inference: an OBJECT_TABLE publish + unstructuredDataEventsConfig.
#   https://docs.cloud.google.com/dataplex/docs/use-data-insights-unstructured-data
# If your project is on the Next '26 preview API instead, swap the dataDiscoverySpec for:
#   "bigqueryPublishingConfig": { "tableType": "BIGLAKE", "connection": "..." },
#   "storageConfig": { "unstructuredDataOptions": { "entity_inference_enabled": true } }
if gcloud dataplex datascans describe "${DATASCAN_ID}" --location="${GCP_REGION}" >/dev/null 2>&1; then
  echo "  datascan already exists."
else
  curl -sS -X POST "https://${DATAPLEX_API}/dataScans?dataScanId=${DATASCAN_ID}" \
    -H "Authorization: Bearer $(gcloud auth print-access-token)" \
    -H "Content-Type: application/json" \
    -d '{
      "data": { "resource": "//storage.googleapis.com/projects/'"${GCP_PROJECT}"'/buckets/'"${GCS_PDF_BUCKET}"'" },
      "executionSpec": { "trigger": { "on_demand": {} } },
      "dataDiscoverySpec": {
        "bigqueryPublishingConfig": {
          "tableType": "OBJECT_TABLE",
          "connection": "projects/'"${GCP_PROJECT}"'/locations/'"${GCP_REGION}"'/connections/'"${BQ_CONNECTION_ID}"'"
        },
        "unstructuredDataEventsConfig": { "enabled": true }
      }
    }'
  echo
fi

echo "== Run the DataScan =="
gcloud dataplex datascans run "${DATASCAN_ID}" --location="${GCP_REGION}"

cat <<EOF

Next (console step, ~15-25 min for insights to generate):
  1. Open Knowledge Catalog, find the published dataset for gs://${GCS_PDF_BUCKET}.
  2. On the object table's Insights tab, click Extract > Extract with SQL.
  3. Run the generated SQL to publish inferred structured tables into BigQuery.
The deterministic seed (gcp/05_seed_native_bq.sh) mirrors that output for a
reliable, offline demo.
EOF
