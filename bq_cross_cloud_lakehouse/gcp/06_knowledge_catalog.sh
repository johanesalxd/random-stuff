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

echo "== 0. Enable APIs required by the Knowledge Catalog / extraction path =="
gcloud services enable --project="${GCP_PROJECT}" \
  dataplex.googleapis.com \
  datacatalog.googleapis.com \
  aiplatform.googleapis.com \
  bigqueryconnection.googleapis.com \
  bigquery.googleapis.com \
  storage.googleapis.com

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

echo "== 3. Grant the connection SA the roles the DataScan needs (per codelab) =="
# A freshly-created connection SA can take ~30-60s to become bindable; retry.
retry() { local n=0; until "$@"; do n=$((n+1)); [[ $n -ge 8 ]] && return 1; echo "  ...retry $n"; sleep 15; done; }
# Bucket-level: read the PDFs.
for ROLE in roles/storage.objectViewer roles/storage.objectUser; do
  retry gcloud storage buckets add-iam-policy-binding "gs://${GCS_PDF_BUCKET}" \
    --member="serviceAccount:${CONN_SA}" --role="${ROLE}" >/dev/null
done
# Project-level: run BQ jobs, use Vertex inference, and let Knowledge Catalog publish.
for ROLE in roles/bigquery.user roles/bigquery.dataEditor roles/aiplatform.user \
            roles/dataplex.discoveryPublishingServiceAgent; do
  retry gcloud projects add-iam-policy-binding "${GCP_PROJECT}" \
    --member="serviceAccount:${CONN_SA}" --role="${ROLE}" --condition=None >/dev/null
done

echo "== 4. Create the Dataplex DataScan (semantic inference on) =="
DATAPLEX_API="dataplex.googleapis.com/v1/projects/${GCP_PROJECT}/locations/${GCP_REGION}"
# Payload uses the shape the live Dataplex v1 API accepts for unstructured
# discovery + semantic inference (verified against the v1 discovery document):
#   bigqueryPublishingConfig.tableType = BIGLAKE
#   storageConfig.unstructuredDataOptions.semanticInferenceEnabled = true
# (The codelab's older field name entity_inference_enabled, and the OBJECT_TABLE +
# unstructuredDataEventsConfig shape, are both rejected as unknown on v1 here.)
#   https://docs.cloud.google.com/dataplex/docs/data-insights-unstructured-data
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
          "tableType": "BIGLAKE",
          "connection": "projects/'"${GCP_PROJECT}"'/locations/'"${GCP_REGION}"'/connections/'"${BQ_CONNECTION_ID}"'"
        },
        "storageConfig": { "unstructuredDataOptions": { "semanticInferenceEnabled": true } }
      }
    }'
  echo
fi

echo "== Wait for the DataScan to become ACTIVE (async create), then run it =="
# NOTE: 'describe' succeeds while the scan is still state=CREATING, but 'run'
# fails with INVALID_ARGUMENT ("... does not exist") until it is ACTIVE. Poll
# the actual state, not just describe-success.
scan_state=""
for i in $(seq 1 24); do
  scan_state="$(gcloud dataplex datascans describe "${DATASCAN_ID}" \
    --location="${GCP_REGION}" --format='value(state)' 2>/dev/null)"
  echo "  [$((i*10))s] state=${scan_state:-<none>}"
  [[ "${scan_state}" == "ACTIVE" ]] && break
  sleep 10
done
if [[ "${scan_state}" != "ACTIVE" ]]; then
  echo "ERROR: DataScan ${DATASCAN_ID} did not reach ACTIVE (last: ${scan_state:-<none>})." >&2
  exit 1
fi

# Run the discovery job. Regional discovery can fail fast with a transient
# "unable to acquire necessary resources" error (documented in the codelab);
# retry once after a short pause before giving up.
run_scan_job() {
  local job jobid st
  job="$(gcloud dataplex datascans run "${DATASCAN_ID}" \
    --location="${GCP_REGION}" --format='value(job.name)' 2>&1)" || { echo "${job}" >&2; return 2; }
  jobid="${job##*/}"
  echo "  scan job: ${jobid}"
  for i in $(seq 1 40); do
    st="$(gcloud dataplex datascans jobs describe "${jobid}" \
      --datascan="${DATASCAN_ID}" --location="${GCP_REGION}" \
      --format='value(state)' 2>/dev/null)"
    echo "  [$((i*30))s] job=${st:-<none>}"
    case "${st}" in
      SUCCEEDED|SUCCEEDED_WITH_ERRORS) return 0 ;;
      FAILED|CANCELLED)
        echo "  job ${st}: $(gcloud dataplex datascans jobs describe "${jobid}" \
          --datascan="${DATASCAN_ID}" --location="${GCP_REGION}" \
          --format='value(message)' 2>/dev/null)" >&2
        return 1 ;;
    esac
    sleep 30
  done
  return 1
}

if ! run_scan_job; then
  echo "== First discovery run failed (often transient); retrying once in 60s =="
  sleep 60
  run_scan_job || { echo "ERROR: DataScan discovery run failed twice." >&2; exit 1; }
fi
echo "== Discovery complete: object table published into a BigQuery dataset derived from gs://${GCS_PDF_BUCKET} =="

cat <<EOF

Delivered by this script:
  * A discovery-managed BigLake OBJECT TABLE cataloguing every PDF in
    gs://${GCS_PDF_BUCKET} (queryable in BigQuery; one row per document).

Structured extraction ("dark PDF -> allergen columns") is a console step and is
region-gated in preview. In some regions (e.g. us-east4 today) the object
table's Insights tab exposes only "Manage discovery scan settings" and "Generate
insights" -- the "Extract with SQL" action is not yet available. When it is
(or once AI.PARSE_DOCUMENT / ML.PROCESS_DOCUMENT is allowlisted in your region):
  1. Open the published dataset for gs://${GCS_PDF_BUCKET} in BigQuery.
  2. On the object table's Insights tab, click Extract > Extract with SQL.
  3. Run the generated SQL to publish inferred structured tables into BigQuery.

Until then, the deterministic seed (gcp/05_seed_native_bq.sh) mirrors that
extracted output (e.g. Midnight Base 204 -> Soy) for a reliable, offline demo
that tells the same story. See the Roadmap in README.md.
EOF
