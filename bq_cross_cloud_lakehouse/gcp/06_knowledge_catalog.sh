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
      "data": {"resource": "//storage.googleapis.com/projects/'"${GCP_PROJECT}"'/buckets/'"${GCS_PDF_BUCKET}"'"},
      "executionSpec": {"trigger": {"onDemand": {}}},
      "dataDiscoverySpec": {
        "bigqueryPublishingConfig": {
          "tableType": "BIGLAKE",
          "connection": "projects/'"${GCP_PROJECT}"'/locations/'"${GCP_REGION}"'/connections/'"${BQ_CONNECTION_ID}"'"
        },
        "storageConfig": {
          "unstructuredDataOptions": {"semanticInferenceEnabled": true}
        }
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

# The published dataset name mirrors the bucket (non-alphanumerics -> "_").
PUBLISHED_DATASET="$(printf '%s' "${GCS_PDF_BUCKET}" | tr -c 'a-zA-Z0-9' '_')"

# True once the discovery-managed object table is published. The object table
# appears within a few minutes, but the job's state can stay RUNNING much longer
# while per-file semantic inference finishes -- so this is the real success gate.
object_table_published() {
  [[ -n "$(bq --location="${GCP_REGION}" --project_id="${GCP_PROJECT}" \
    ls --max_results=50 "${GCP_PROJECT}:${PUBLISHED_DATASET}" 2>/dev/null)" ]]
}

# Start a discovery job; echo the job id, or return 1 if the run command fails.
start_scan_job() {
  local job
  job="$(gcloud dataplex datascans run "${DATASCAN_ID}" \
    --project="${GCP_PROJECT}" --location="${GCP_REGION}" \
    --format='value(job.name)' 2>&1)" || { echo "${job}" >&2; return 1; }
  printf '%s\n' "${job##*/}"
}

echo "== Run discovery =="
job_id=""
for run_attempt in 1 2; do
  if job_id="$(start_scan_job)"; then break; fi
  echo "== Discovery run failed to start (often transient); retry in 60s =="
  sleep 60
  job_id=""
done
[[ -z "${job_id}" ]] && { echo "ERROR: could not start DataScan discovery." >&2; exit 1; }
echo "  scan job: ${job_id}"

# Poll up to ~30 min. Exit success as soon as the job reaches a terminal state
# OR the object table is published. Retry once on the transient "unable to
# acquire necessary resources" capacity error (documented in the codelab).
retried_transient="false"
for attempt in $(seq 1 60); do
  state="$(gcloud dataplex datascans jobs describe "${job_id}" \
    --project="${GCP_PROJECT}" --datascan="${DATASCAN_ID}" \
    --location="${GCP_REGION}" --format='value(state)' 2>/dev/null)"
  echo "  [$((attempt * 30))s] job=${state:-unknown}"
  case "${state}" in
    SUCCEEDED|SUCCEEDED_WITH_ERRORS)
      break
      ;;
    FAILED|CANCELLED)
      message="$(gcloud dataplex datascans jobs describe "${job_id}" \
        --project="${GCP_PROJECT}" --datascan="${DATASCAN_ID}" \
        --location="${GCP_REGION}" \
        --format='value(partialFailureMessage,message)' 2>/dev/null)"
      if [[ "${retried_transient}" == "false" \
            && "${message}" == *"unable to acquire necessary resources"* ]]; then
        echo "  transient: ${message}; retrying in 60s" >&2
        retried_transient="true"
        sleep 60
        job_id="$(start_scan_job)" || { echo "ERROR: retry failed to start." >&2; exit 1; }
        echo "  scan job: ${job_id}"
        continue
      fi
      if object_table_published; then
        echo "  job ${state} but object table already published; continuing." >&2
        break
      fi
      echo "  DataScan ${state}: ${message:-no details}" >&2
      echo "ERROR: discovery failed. Fall back to gcp/05_seed_native_bq.sh." >&2
      exit 1
      ;;
  esac
  if object_table_published; then
    echo "  object table published; semantic inference continues asynchronously."
    break
  fi
  sleep 30
done

if ! object_table_published; then
  echo "ERROR: object table was not published before the timeout." >&2
  echo "Fall back to gcp/05_seed_native_bq.sh for the deterministic demo." >&2
  exit 1
fi

cat <<EOF
Knowledge Catalog discovery complete: a BigLake object table over the PDFs in
gs://${GCS_PDF_BUCKET} is published to BigQuery dataset ${PUBLISHED_DATASET}
(one row per document). Semantic inference may keep finishing in the background.

For teardown of the generated dataset, set in config.local.env:
  export DISCOVERY_DATASET="${PUBLISHED_DATASET}"

Structured "Extract with SQL" (dark PDF -> allergen columns) is a console step
and is region-gated in preview; where it is unavailable, gcp/05_seed_native_bq.sh
provides the same grounded knowledge (e.g. Midnight Base 204 -> Soy) for a
reliable demo. See the Roadmap in README.md.
EOF
