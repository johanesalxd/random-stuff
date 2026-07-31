#!/usr/bin/env bash
# teardown_demo.sh
# Coordinates the sequential teardown and cleanup of all demo resources on GCP and AWS.

set -euo pipefail
cd "$(dirname "$0")"

# -------------------------------------------------------------
# 1. Initialization and Safety Checks
# -------------------------------------------------------------
echo "=== Phase 1: Environment Setup ==="
if [[ ! -f "config.local.env" ]]; then
  echo "ERROR: config.local.env not found!" >&2
  echo "Please create config.local.env and populate the required environment variables first." >&2
  exit 1
fi

source config.local.env

# Auto-calculate DISCOVERY_DATASET name from GCS_PDF_BUCKET if not explicitly set
if [[ -z "${DISCOVERY_DATASET:-}" && -n "${GCS_PDF_BUCKET:-}" ]]; then
  export DISCOVERY_DATASET="$(printf '%s' "${GCS_PDF_BUCKET}" | tr -c 'a-zA-Z0-9' '_')"
  sed -i "s|export DISCOVERY_DATASET=\".*\"|export DISCOVERY_DATASET=\"${DISCOVERY_DATASET}\"|g" config.local.env
fi

# Fetch Connection Service Account to clean up shared bucket bindings later
CONN_SA=""
CONN="${GCP_PROJECT}.${GCP_REGION}.${BQ_CONNECTION_ID}"
if bq --project_id="${GCP_PROJECT}" show --connection "${CONN}" >/dev/null 2>&1; then
  CONN_SA="$(bq --project_id="${GCP_PROJECT}" --format=json show \
    --connection "${CONN}" | python3 -c \
    'import json,sys; print(json.load(sys.stdin)["cloudResource"]["serviceAccountId"])')"
fi

# -------------------------------------------------------------
# 2. Dry-run / Preview
# -------------------------------------------------------------
echo ""
echo "=== Phase 2: Previewing Teardown (Dry-Run) ==="
echo "--- GCP Dry-run ---"
./gcp/90_teardown.sh --dry-run
echo ""
echo "--- AWS Dry-run ---"
./aws/90_teardown.sh --dry-run
echo ""

# -------------------------------------------------------------
# 3. Confirmation and Execution
# -------------------------------------------------------------
read -p "Are you sure you want to execute this teardown and DELETE these resources? [y/N]: " confirm
if [[ "$confirm" =~ ^[Yy]$ ]]; then
  echo ""
  echo "=== Phase 3: Executing Teardown ==="
  echo "--- Deleting GCP Resources ---"
  ./gcp/90_teardown.sh --execute
  
  # Revoke the connection SA permissions if using a shared bucket (not handled by standard gcp teardown)
  if [[ "${GCS_PDF_BUCKET_MODE:-}" == "shared" && -n "${CONN_SA}" ]]; then
    if gcloud storage buckets describe "gs://${GCS_PDF_BUCKET}" >/dev/null 2>&1; then
      echo "Revoking connection Service Account storage.objectViewer role from shared GCS bucket..."
      gcloud storage buckets remove-iam-policy-binding "gs://${GCS_PDF_BUCKET}" \
        --member="serviceAccount:${CONN_SA}" \
        --role=roles/storage.objectViewer --quiet || true
    fi
  fi

  echo ""
  echo "--- Deleting AWS Resources ---"
  ./aws/90_teardown.sh --execute
  echo ""
  
  # -------------------------------------------------------------
  # 4. Generate Cleanup Report
  # -------------------------------------------------------------
  generate_cleanup_report() {
    echo ""
    echo "=================================================="
    echo "                CLEANUP REPORT                    "
    echo "=================================================="

    echo "GCP Resources:"
    if gcloud dataplex datascans describe "${DATASCAN_ID}" --project="${GCP_PROJECT}" --location="${GCP_REGION}" >/dev/null 2>&1; then
      echo "  ❌ Dataplex DataScan (${DATASCAN_ID}): STILL EXISTS"
    else
      echo "  ✅ Dataplex DataScan (${DATASCAN_ID}): DELETED"
    fi

    if [[ -n "${DISCOVERY_DATASET}" ]] && bq --project_id="${GCP_PROJECT}" show --dataset "${GCP_PROJECT}:${DISCOVERY_DATASET}" >/dev/null 2>&1; then
      echo "  ❌ Discovery BQ Dataset (${DISCOVERY_DATASET}): STILL EXISTS"
    else
      echo "  ✅ Discovery BQ Dataset (${DISCOVERY_DATASET}): DELETED"
    fi

    if bq --project_id="${GCP_PROJECT}" show --connection "${CONN}" >/dev/null 2>&1; then
      echo "  ❌ BQ Cloud Connection (${BQ_CONNECTION_ID}): STILL EXISTS"
    else
      echo "  ✅ BQ Cloud Connection (${BQ_CONNECTION_ID}): DELETED"
    fi

    if gcloud storage buckets describe "gs://${GCS_PDF_BUCKET}" >/dev/null 2>&1; then
      if [[ "${GCS_PDF_BUCKET_MODE}" == "shared" ]]; then
        echo "  ℹ️  GCS PDF Bucket (gs://${GCS_PDF_BUCKET}): RETAINED (Shared Mode)"
      else
        echo "  ❌ GCS PDF Bucket (gs://${GCS_PDF_BUCKET}): STILL EXISTS"
      fi
    else
      echo "  ✅ GCS PDF Bucket (gs://${GCS_PDF_BUCKET}): DELETED"
    fi

    if gcloud alpha biglake iceberg catalogs describe "${FEDERATED_CATALOG}" --project="${GCP_PROJECT}" >/dev/null 2>&1; then
      echo "  ❌ Federated Catalog (${FEDERATED_CATALOG}): STILL EXISTS"
    else
      echo "  ✅ Federated Catalog (${FEDERATED_CATALOG}): DELETED"
    fi

    if bq --project_id="${GCP_PROJECT}" show --dataset "${GCP_PROJECT}:${FROYO_NATIVE_DATASET}" >/dev/null 2>&1; then
      echo "  ❌ Native BQ Dataset (${FROYO_NATIVE_DATASET}): STILL EXISTS"
    else
      echo "  ✅ Native BQ Dataset (${FROYO_NATIVE_DATASET}): DELETED"
    fi

    echo ""
    echo "AWS Resources:"
    if aws glue get-table --database-name "${GLUE_DATABASE}" --name "${FROYO_LOYALTY_TABLE}" --region "${AWS_REGION}" >/dev/null 2>&1; then
      echo "  ❌ Glue Table (${FROYO_LOYALTY_TABLE}): STILL EXISTS"
    else
      echo "  ✅ Glue Table (${FROYO_LOYALTY_TABLE}): DELETED"
    fi

    if aws glue get-table --database-name "${GLUE_DATABASE}" --name "${FROYO_SALES_TABLE}" --region "${AWS_REGION}" >/dev/null 2>&1; then
      echo "  ❌ Glue Table (${FROYO_SALES_TABLE}): STILL EXISTS"
    else
      echo "  ✅ Glue Table (${FROYO_SALES_TABLE}): DELETED"
    fi

    if aws glue get-database --name "${GLUE_DATABASE}" --region "${AWS_REGION}" >/dev/null 2>&1; then
      echo "  ❌ Glue Database (${GLUE_DATABASE}): STILL EXISTS"
    else
      echo "  ✅ Glue Database (${GLUE_DATABASE}): DELETED"
    fi

    if aws s3api head-bucket --bucket "${S3_BUCKET}" --region "${AWS_REGION}" >/dev/null 2>&1; then
      if [[ "${S3_BUCKET_MODE}" == "shared" ]]; then
        echo "  ℹ️  S3 Bucket (s3://${S3_BUCKET}): RETAINED (Shared Mode)"
      else
        echo "  ❌ S3 Bucket (s3://${S3_BUCKET}): STILL EXISTS"
      fi
    else
      echo "  ✅ S3 Bucket (s3://${S3_BUCKET}): DELETED"
    fi

    if aws iam get-role --role-name "${AWS_ROLE_NAME}" >/dev/null 2>&1; then
      echo "  ❌ IAM Role (${AWS_ROLE_NAME}): STILL EXISTS"
    else
      echo "  ✅ IAM Role (${AWS_ROLE_NAME}): DELETED"
    fi

    echo "=================================================="
  }

  generate_cleanup_report
else
  echo "Teardown execution canceled."
fi
