#!/usr/bin/env bash
# Preview or execute removal of the GCP demo resources.
set -euo pipefail
cd "$(dirname "$0")/.."
source ./config.local.env

MODE="${1:---dry-run}"
if [[ "${MODE}" != "--dry-run" && "${MODE}" != "--execute" ]]; then
  echo "Usage: $0 [--dry-run|--execute]" >&2
  exit 2
fi

run() {
  printf "  "
  printf "%q " "$@"
  printf "\n"
  if [[ "${MODE}" == "--execute" ]]; then
    "$@"
  fi
}

CONN="${GCP_PROJECT}.${GCP_REGION}.${BQ_CONNECTION_ID}"

case "${GCS_PDF_BUCKET_MODE:-}" in
  dedicated|shared) ;;
  *)
    echo "ERROR: Set GCS_PDF_BUCKET_MODE to dedicated or shared in config.local.env." >&2
    exit 1
    ;;
esac

echo "GCP teardown ${MODE}."
[[ "${MODE}" == "--dry-run" ]] && echo "No resources will be changed."

echo "== Optional Knowledge Catalog resources =="
if gcloud dataplex datascans describe "${DATASCAN_ID}" \
    --project="${GCP_PROJECT}" --location="${GCP_REGION}" >/dev/null 2>&1; then
  run gcloud dataplex datascans delete "${DATASCAN_ID}" \
    --project="${GCP_PROJECT}" --location="${GCP_REGION}" --quiet
fi
if [[ -n "${DISCOVERY_DATASET:-}" ]] && bq --project_id="${GCP_PROJECT}" \
    show --dataset "${GCP_PROJECT}:${DISCOVERY_DATASET}" >/dev/null 2>&1; then
  run bq --project_id="${GCP_PROJECT}" rm -r -f --dataset \
    "${GCP_PROJECT}:${DISCOVERY_DATASET}"
fi

# Revoke the project-level roles gcp/06 grants to the Dataplex service agent.
# NOTE: this is the shared, project-wide Dataplex service agent. In a project
# that runs other Dataplex scans you may prefer to keep the generic roles
# (aiplatform.user, bigquery.jobUser, bigquery.dataViewer); comment them out here.
PROJECT_NUMBER="$(gcloud projects describe "${GCP_PROJECT}" --format='value(projectNumber)')"
DATAPLEX_SA="service-${PROJECT_NUMBER}@gcp-sa-dataplex.iam.gserviceaccount.com"
for role in roles/aiplatform.user roles/bigquery.jobUser roles/bigquery.dataViewer \
  roles/dataplex.discoveryPublishingServiceAgent; do
  if gcloud projects get-iam-policy "${GCP_PROJECT}" \
      --flatten='bindings[].members' \
      --filter="bindings.members:serviceAccount:${DATAPLEX_SA} AND bindings.role:${role}" \
      --format='value(bindings.role)' 2>/dev/null | grep -q "${role}"; then
    run gcloud projects remove-iam-policy-binding "${GCP_PROJECT}" \
      --member="serviceAccount:${DATAPLEX_SA}" --role="${role}" \
      --condition=None --quiet
  fi
done

if bq --project_id="${GCP_PROJECT}" show --connection "${CONN}" >/dev/null 2>&1; then
  connection_sa="$(bq --project_id="${GCP_PROJECT}" --format=json show \
    --connection "${CONN}" | python3 -c \
    'import json,sys; print(json.load(sys.stdin)["cloudResource"]["serviceAccountId"])')"
  connection_role="$(gcloud projects get-iam-policy "${GCP_PROJECT}" \
    --flatten='bindings[].members' \
    --filter="bindings.members:serviceAccount:${connection_sa} AND bindings.role:roles/aiplatform.user" \
    --format='value(bindings.role)')"
  if [[ "${connection_role}" == "roles/aiplatform.user" ]]; then
    run gcloud projects remove-iam-policy-binding "${GCP_PROJECT}" \
      --member="serviceAccount:${connection_sa}" --role=roles/aiplatform.user \
      --condition=None --quiet
  fi
  # gcp/06 also grants this SA storage.objectViewer on the PDF bucket. Revoke it
  # here, while the connection still exists and its SA id is resolvable. Only
  # shared buckets need it -- a dedicated bucket is deleted wholesale below.
  if [[ "${GCS_PDF_BUCKET_MODE}" == "shared" ]] \
      && gcloud storage buckets describe "gs://${GCS_PDF_BUCKET}" >/dev/null 2>&1; then
    if gcloud storage buckets get-iam-policy "gs://${GCS_PDF_BUCKET}" \
        --format='value(bindings.members)' 2>/dev/null \
        | grep -q "${connection_sa}"; then
      run gcloud storage buckets remove-iam-policy-binding "gs://${GCS_PDF_BUCKET}" \
        --member="serviceAccount:${connection_sa}" \
        --role=roles/storage.objectViewer
    fi
  fi
  run bq --project_id="${GCP_PROJECT}" rm --connection --force "${CONN}"
fi
if gcloud storage buckets describe "gs://${GCS_PDF_BUCKET}" >/dev/null 2>&1; then
  if [[ "${GCS_PDF_BUCKET_MODE}" == "shared" ]]; then
    echo "  Shared PDF bucket will be retained; revoking only the demo bindings."
    if gcloud storage buckets get-iam-policy "gs://${GCS_PDF_BUCKET}" \
        --format='value(bindings.members)' 2>/dev/null \
        | grep -q "${DATAPLEX_SA}"; then
      run gcloud storage buckets remove-iam-policy-binding "gs://${GCS_PDF_BUCKET}" \
        --member="serviceAccount:${DATAPLEX_SA}" \
        --role=roles/dataplex.discoveryServiceAgent
    fi
  else
    run gcloud storage rm --recursive "gs://${GCS_PDF_BUCKET}" --quiet
  fi
fi

echo "== Federated catalog and native dataset =="
if gcloud alpha biglake iceberg catalogs describe "${FEDERATED_CATALOG}" \
    --project="${GCP_PROJECT}" >/dev/null 2>&1; then
  run gcloud alpha biglake iceberg catalogs delete "${FEDERATED_CATALOG}" \
    --project="${GCP_PROJECT}" --quiet
fi
if bq --project_id="${GCP_PROJECT}" show --dataset \
    "${GCP_PROJECT}:${FROYO_NATIVE_DATASET}" >/dev/null 2>&1; then
  run bq --project_id="${GCP_PROJECT}" rm -r -f --dataset \
    "${GCP_PROJECT}:${FROYO_NATIVE_DATASET}"
fi

echo "GCP teardown ${MODE} complete."
