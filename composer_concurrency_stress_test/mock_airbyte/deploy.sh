#!/usr/bin/env bash
# Deploy mock Airbyte API to Cloud Run for deferrable operator stress testing.
#
# Usage:
#   ./deploy.sh <PROJECT_ID> [REGION] [SYNC_DURATION_SECONDS]
#
# Example:
#   ./deploy.sh my-project us-central1 30
#
# After deployment, configure the Airflow connection:
#   Host:     https://<CLOUD_RUN_URL>/v1
#   Login:    (blank)
#   Password: (blank)
#   Schema:   (blank)

set -euo pipefail

PROJECT_ID="${1:?Usage: ./deploy.sh <PROJECT_ID> [REGION] [SYNC_DURATION_SECONDS]}"
REGION="${2:-us-central1}"
SYNC_DURATION="${3:-30}"
SERVICE_NAME="mock-airbyte"

echo "Deploying ${SERVICE_NAME} to Cloud Run..."
echo "  Project:       ${PROJECT_ID}"
echo "  Region:        ${REGION}"
echo "  Sync Duration: ${SYNC_DURATION}s"
echo ""

gcloud run deploy "${SERVICE_NAME}" \
    --source . \
    --region "${REGION}" \
    --project "${PROJECT_ID}" \
    --allow-unauthenticated \
    --max-instances=1 \
    --set-env-vars="SYNC_DURATION_SECONDS=${SYNC_DURATION}" \
    --quiet

# Get the service URL
SERVICE_URL=$(gcloud run services describe "${SERVICE_NAME}" \
    --region "${REGION}" \
    --project "${PROJECT_ID}" \
    --format="value(status.url)")

echo ""
echo "Mock Airbyte deployed successfully!"
echo ""
echo "Service URL: ${SERVICE_URL}"
echo ""
echo "Next steps:"
echo "  1. Create Airflow connection 'airbyte_default':"
echo "     Host:     ${SERVICE_URL}/v1"
echo "     Login:    (leave blank)"
echo "     Password: (leave blank)"
echo "     Schema:   (leave blank)"
echo ""
echo "  2. Or via gcloud CLI:"
echo "     gcloud composer environments run <ENV> \\"
echo "       --location=<LOCATION> \\"
echo "       connections add -- airbyte_default \\"
echo "       --conn-type airbyte \\"
echo "       --conn-host '${SERVICE_URL}/v1'"
echo ""
echo "  3. Test the connection:"
echo "     curl ${SERVICE_URL}/v1/health"
