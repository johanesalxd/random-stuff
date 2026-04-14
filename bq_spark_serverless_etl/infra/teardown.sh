#!/bin/bash
#
# teardown.sh -- Delete all GCP resources created by setup.sh.
#
# This script reads infra/.env for resource names written during setup.
# Run it after the demo to avoid ongoing charges.
#
# Usage:
#   bash infra/teardown.sh

set -euo pipefail

ENV_FILE="$(dirname "$0")/.env"

if [[ ! -f "${ENV_FILE}" ]]; then
  echo "ERROR: ${ENV_FILE} not found. Run infra/setup.sh first."
  exit 1
fi

# shellcheck disable=SC1090
source "${ENV_FILE}"

echo "=== Dataproc Serverless Spark ETL Demo Teardown ==="
echo "Project : ${GCP_PROJECT}"
echo ""
echo "WARNING: This will permanently delete the following resources:"
echo "  - GCS bucket:       gs://${GCS_BUCKET}"
echo "  - Cloud SQL:        ${SQL_INSTANCE}"
echo "  - Secret:           ${SECRET_RESOURCE%%/versions/*}"
echo "  - BQ datasets:      raw_thelook, analytics, ${BQ_DATASET}"
echo "  - BQ connection:    ${BQ_CONNECTION}"
echo "  - Service account:  ${SERVICE_ACCOUNT}"
echo ""
read -r -p "Type 'yes' to continue: " CONFIRM
if [[ "${CONFIRM}" != "yes" ]]; then
  echo "Aborted."
  exit 0
fi

# ---------------------------------------------------------------------------
# Delete BQ stored procedure
# ---------------------------------------------------------------------------
echo "[1/7] Dropping stored procedure (if exists)..."
bq query \
  --project_id="${GCP_PROJECT}" \
  --location="${GCP_REGION}" \
  --nouse_legacy_sql \
  "DROP PROCEDURE IF EXISTS \`${GCP_PROJECT}.${BQ_DATASET}.run_pipeline\`" \
  2>/dev/null || true
echo "      Done."

# ---------------------------------------------------------------------------
# Delete BQ Spark connection
# ---------------------------------------------------------------------------
echo "[2/7] Deleting BigQuery Spark connection: ${BQ_CONNECTION}..."
bq rm --connection \
  --project_id="${GCP_PROJECT}" \
  --location="${GCP_REGION}" \
  "${BQ_CONNECTION}" \
  --quiet 2>/dev/null || echo "      Connection not found, skipping."

# ---------------------------------------------------------------------------
# Delete BQ datasets
# ---------------------------------------------------------------------------
echo "[3/7] Deleting BigQuery datasets..."
for DS in raw_thelook analytics "${BQ_DATASET}"; do
  bq rm \
    --project_id="${GCP_PROJECT}" \
    --dataset \
    --recursive \
    --force \
    "${DS}" \
    2>/dev/null || echo "      Dataset ${DS} not found, skipping."
  echo "      Deleted ${DS}."
done

# ---------------------------------------------------------------------------
# Delete Cloud SQL instance
# ---------------------------------------------------------------------------
echo "[4/7] Deleting Cloud SQL instance: ${SQL_INSTANCE}..."
gcloud sql instances delete "${SQL_INSTANCE}" \
  --project="${GCP_PROJECT}" \
  --quiet 2>/dev/null || echo "      Instance not found, skipping."
echo "      Done."

# ---------------------------------------------------------------------------
# Delete Secret Manager secret
# ---------------------------------------------------------------------------
SECRET_NAME="${SECRET_RESOURCE%%/versions/*}"
SECRET_NAME="${SECRET_NAME##*/secrets/}"
echo "[5/7] Deleting Secret Manager secret: ${SECRET_NAME}..."
gcloud secrets delete "${SECRET_NAME}" \
  --project="${GCP_PROJECT}" \
  --quiet 2>/dev/null || echo "      Secret not found, skipping."
echo "      Done."

# ---------------------------------------------------------------------------
# Delete GCS bucket
# ---------------------------------------------------------------------------
echo "[6/7] Deleting GCS bucket: gs://${GCS_BUCKET}..."
gcloud storage rm --recursive "gs://${GCS_BUCKET}" \
  --quiet 2>/dev/null || echo "      Bucket not found, skipping."
echo "      Done."

# ---------------------------------------------------------------------------
# Delete service account
# ---------------------------------------------------------------------------
echo "[7/7] Deleting service account: ${SERVICE_ACCOUNT}..."
gcloud iam service-accounts delete "${SERVICE_ACCOUNT}" \
  --project="${GCP_PROJECT}" \
  --quiet 2>/dev/null || echo "      Service account not found, skipping."
echo "      Done."

# Remove .env
rm -f "${ENV_FILE}"
echo ""
echo "=== Teardown complete. All demo resources deleted. ==="
