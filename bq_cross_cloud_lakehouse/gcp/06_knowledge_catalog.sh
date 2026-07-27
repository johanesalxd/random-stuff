#!/usr/bin/env bash
# Optional Knowledge Catalog PDF discovery and semantic-inference path.
set -euo pipefail
cd "$(dirname "$0")/.."
source ./config.local.env

CONN="${GCP_PROJECT}.${GCP_REGION}.${BQ_CONNECTION_ID}"

retry() {
  local attempt=0
  until "$@"; do
    attempt=$((attempt + 1))
    [[ ${attempt} -ge 8 ]] && return 1
    echo "  retry ${attempt}/8"
    sleep 15
  done
}

echo "== Enable Knowledge Catalog APIs =="
gcloud services enable --project="${GCP_PROJECT}" \
  dataplex.googleapis.com \
  datacatalog.googleapis.com \
  aiplatform.googleapis.com \
  bigqueryconnection.googleapis.com \
  bigquery.googleapis.com \
  storage.googleapis.com

echo "== Upload PDFs to gs://${GCS_PDF_BUCKET} =="
if ! gcloud storage buckets describe "gs://${GCS_PDF_BUCKET}" >/dev/null 2>&1; then
  gcloud storage buckets create "gs://${GCS_PDF_BUCKET}" \
    --project="${GCP_PROJECT}" --location="${GCP_REGION}" \
    --uniform-bucket-level-access
fi
gcloud storage rsync --recursive assets/pdfs/recipes \
  "gs://${GCS_PDF_BUCKET}/recipes"
gcloud storage rsync --recursive assets/pdfs/suppliers \
  "gs://${GCS_PDF_BUCKET}/suppliers"

echo "== BigQuery Cloud Resource connection: ${CONN} =="
if ! bq --project_id="${GCP_PROJECT}" show --connection "${CONN}" >/dev/null 2>&1; then
  bq mk --connection --location="${GCP_REGION}" \
    --project_id="${GCP_PROJECT}" --connection_type=CLOUD_RESOURCE \
    "${BQ_CONNECTION_ID}"
fi
CONN_SA="$(bq --project_id="${GCP_PROJECT}" --format=json show \
  --connection "${CONN}" | python3 -c \
  'import json,sys; print(json.load(sys.stdin)["cloudResource"]["serviceAccountId"])')"
PROJECT_NUMBER="$(gcloud projects describe "${GCP_PROJECT}" \
  --format='value(projectNumber)')"
DATAPLEX_SA="service-${PROJECT_NUMBER}@gcp-sa-dataplex.iam.gserviceaccount.com"

echo "== Grant discovery and semantic-inference roles =="
retry gcloud storage buckets add-iam-policy-binding "gs://${GCS_PDF_BUCKET}" \
  --member="serviceAccount:${CONN_SA}" \
  --role=roles/storage.objectViewer >/dev/null
retry gcloud projects add-iam-policy-binding "${GCP_PROJECT}" \
  --member="serviceAccount:${CONN_SA}" --role=roles/aiplatform.user \
  --condition=None >/dev/null
for role in roles/aiplatform.user roles/bigquery.jobUser roles/bigquery.dataViewer \
  roles/dataplex.discoveryPublishingServiceAgent; do
  retry gcloud projects add-iam-policy-binding "${GCP_PROJECT}" \
    --member="serviceAccount:${DATAPLEX_SA}" --role="${role}" \
    --condition=None >/dev/null
done
retry gcloud storage buckets add-iam-policy-binding "gs://${GCS_PDF_BUCKET}" \
  --member="serviceAccount:${DATAPLEX_SA}" \
  --role=roles/dataplex.discoveryServiceAgent >/dev/null
retry bq --project_id="${GCP_PROJECT}" add-iam-policy-binding --connection \
  --member="serviceAccount:${DATAPLEX_SA}" \
  --role=roles/dataplex.discoveryBigLakePublishingServiceAgent "${CONN}" \
  >/dev/null

echo "== Create the DataScan if needed =="
DATAPLEX_API="dataplex.googleapis.com/v1/projects/${GCP_PROJECT}/locations/${GCP_REGION}"
if ! gcloud dataplex datascans describe "${DATASCAN_ID}" \
    --project="${GCP_PROJECT}" --location="${GCP_REGION}" >/dev/null 2>&1; then
  curl --fail-with-body --silent --show-error --request POST \
    "https://${DATAPLEX_API}/dataScans?dataScanId=${DATASCAN_ID}" \
    --header "Authorization: Bearer $(gcloud auth print-access-token)" \
    --header "Content-Type: application/json" \
    --data '{
      "description": "Froyo PDF discovery with semantic inference",
      "data": {"resource": "//storage.googleapis.com/'"${GCS_PDF_BUCKET}"'"},
      "executionSpec": {"trigger": {"onDemand": {}}},
      "dataDiscoverySpec": {
        "bigqueryPublishingConfig": {
          "tableType": "OBJECT_TABLE",
          "connection": "projects/'"${GCP_PROJECT}"'/locations/'"${GCP_REGION}"'/connections/'"${BQ_CONNECTION_ID}"'"
        },
        "unstructuredDataEventsConfig": {"enabled": true}
      }
    }'
  echo
fi

echo "== Wait for the DataScan and run discovery =="
scan_state=""
for attempt in $(seq 1 24); do
  scan_state="$(gcloud dataplex datascans describe "${DATASCAN_ID}" \
    --project="${GCP_PROJECT}" --location="${GCP_REGION}" \
    --format='value(state)' 2>/dev/null)"
  [[ "${scan_state}" == "ACTIVE" ]] && break
  sleep 10
done
if [[ "${scan_state}" != "ACTIVE" ]]; then
  echo "ERROR: DataScan did not become active." >&2
  exit 1
fi

job="$(gcloud dataplex datascans run "${DATASCAN_ID}" \
  --project="${GCP_PROJECT}" --location="${GCP_REGION}" \
  --format='value(job.name)')"
job_id="${job##*/}"
for attempt in $(seq 1 40); do
  state="$(gcloud dataplex datascans jobs describe "${job_id}" \
    --project="${GCP_PROJECT}" --datascan="${DATASCAN_ID}" \
    --location="${GCP_REGION}" --format='value(state)' 2>/dev/null)"
  echo "  [$((attempt * 30))s] job=${state:-unknown}"
  case "${state}" in
    SUCCEEDED)
      echo "Knowledge Catalog discovery and semantic inference succeeded."
      exit 0
      ;;
    SUCCEEDED_WITH_ERRORS|FAILED|CANCELLED)
      message="$(gcloud dataplex datascans jobs describe "${job_id}" \
        --project="${GCP_PROJECT}" --datascan="${DATASCAN_ID}" \
        --location="${GCP_REGION}" \
        --format='value(partialFailureMessage,message)' 2>/dev/null)"
      echo "ERROR: DataScan ${state}: ${message:-no details}" >&2
      echo "Use gcp/05_seed_native_bq.sh for the reliable event demo." >&2
      exit 1
      ;;
  esac
  sleep 30
done

echo "ERROR: DataScan job timed out." >&2
exit 1
