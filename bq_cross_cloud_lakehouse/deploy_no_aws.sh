#!/usr/bin/env bash
# deploy_no_aws.sh
# Coordinates the deployment of the Froyo GCP stack in NO-AWS mode.

set -euo pipefail
cd "$(dirname "$0")"

cleanup_tip() {
  local exit_code=$?
  if [[ $exit_code -ne 0 ]]; then
    echo "" >&2
    echo "⚠️  Deployment failed! You can clean up GCP resources by running: ./gcp/90_teardown.sh" >&2
  fi
}
trap cleanup_tip EXIT

echo "=== Phase 1: Environment Setup ==="
if [[ ! -f "config.local.env" ]]; then
  echo "ERROR: config.local.env not found!" >&2
  exit 1
fi

source config.local.env

if [[ "${NO_AWS:-false}" != "true" ]]; then
  echo "ERROR: NO_AWS must be set to true in config.local.env for this deployment." >&2
  exit 1
fi

# Enable required GCP APIs automatically
echo "Enabling required GCP services..."
gcloud services enable --project="$GCP_PROJECT" \
  biglake.googleapis.com \
  bigquery.googleapis.com \
  dataplex.googleapis.com \
  geminidataanalytics.googleapis.com \
  discoveryengine.googleapis.com \
  cloudaicompanion.googleapis.com || { echo "❌ ERROR: Failed to enable required GCP APIs." >&2; exit 1; }

# -------------------------------------------------------------
# 2. Provision & Seed GCP Datasets
# -------------------------------------------------------------
echo ""
echo "=== Phase 2: Seeding Data ==="
# Seed the deterministic native BigQuery allergen & recipe metadata
./gcp/05_seed_native_bq.sh || { echo "❌ ERROR: Seeding native BigQuery tables failed." >&2; exit 1; }

# Seed the mock AWS data natively
./gcp/04_seed_mock_aws_data.sh || { echo "❌ ERROR: Seeding mock AWS data failed." >&2; exit 1; }

# -------------------------------------------------------------
# 3. Verification
# -------------------------------------------------------------
echo ""
echo "=== Phase 3: Verification ==="
echo "Verifying tables exist..."
bq --project_id="$GCP_PROJECT" show "$FROYO_NATIVE_DATASET.$FROYO_LOYALTY_TABLE" >/dev/null || { echo "❌ ERROR: Mock loyalty table missing." >&2; exit 1; }
bq --project_id="$GCP_PROJECT" show "$FROYO_NATIVE_DATASET.$FROYO_SALES_TABLE" >/dev/null || { echo "❌ ERROR: Mock sales table missing." >&2; exit 1; }
echo "✅ All tables verified natively."

# Run the final demo queries & ML model
echo "Executing allergen target join query..."
./gcp/40_query_froyo.sh || { echo "❌ ERROR: Froyo query execution failed." >&2; exit 1; }

echo "Training and running BigQuery ML forecast..."
./gcp/50_forecast_bqml.sh 92 || { echo "❌ ERROR: BigQuery ML ARIMA forecasting failed." >&2; exit 1; }
echo "✅ Froyo queries executed and ARIMA forecast completed successfully."

# -------------------------------------------------------------
# 4. Deploy Conversational Analytics Agent & Web App UI
# -------------------------------------------------------------
echo ""
echo "=== Phase 4: Deploying CA Agent & Web App UI ==="

# Check for agent .env
if [[ ! -f "agent/.env" ]]; then
  echo "❌ ERROR: agent/.env not found! OAuth credentials are required for Web App." >&2
  exit 1
fi

echo "Deploying Conversational Analytics data agent..."
cd agent
# Run with NO_AWS=true in environment so create_agent.py (which uses agent_definition.py) picks it up
NO_AWS=true GOOGLE_API_USE_CLIENT_CERTIFICATE=false uv run python scripts/create_agent.py || { echo "❌ ERROR: Failed to create CA agent." >&2; exit 1; }

# Load agent env to check if we can register in GE
run_registration=true
if [ -f .env ]; then
  # Simple grep to find GEMINI_APP_ID value
  GE_APP_ID=$(grep '^GEMINI_APP_ID=' .env | cut -d'=' -f2- || echo "")
  # Strip whitespace and quotes
  GE_APP_ID=$(echo "${GE_APP_ID}" | tr -d '[:space:]' | tr -d '"' | tr -d "'")
  if [[ -z "${GE_APP_ID}" || "${GE_APP_ID}" == "your-gemini-app-id" ]]; then
    echo "⚠️  GEMINI_APP_ID is not set in agent/.env. Skipping Gemini Enterprise registration."
    run_registration=false
  fi
else
  run_registration=false
fi

if [ "$run_registration" = true ]; then
  echo "Registering agent in Gemini Enterprise..."
  NO_AWS=true GOOGLE_API_USE_CLIENT_CERTIFICATE=false uv run python scripts/register_ge_agent.py --force || { echo "❌ ERROR: Failed to register agent in GE." >&2; exit 1; }
fi
cd ..

echo "Building and deploying Web UI to Google Cloud Run..."

# Enable Cloud Build, Cloud Run, Artifact Registry APIs
gcloud services enable --project="$GCP_PROJECT" \
  run.googleapis.com \
  artifactregistry.googleapis.com \
  cloudbuild.googleapis.com || { echo "❌ ERROR: Failed to enable Web Deployment APIs." >&2; exit 1; }

# Create Artifact Registry Repository if not exists
REPO_NAME="froyo-agent-hub"
if ! gcloud artifacts repositories describe "$REPO_NAME" --location="us-central1" --project="$GCP_PROJECT" >/dev/null 2>&1; then
  echo "Creating Artifact Registry repository..."
  gcloud artifacts repositories create "$REPO_NAME" \
    --repository-format=docker --location="us-central1" --project="$GCP_PROJECT" || { echo "❌ ERROR: Failed to create Artifact Registry repository." >&2; exit 1; }
fi

# Build the image using Cloud Build
echo "Submitting build to Cloud Build..."
gcloud builds submit --tag "us-central1-docker.pkg.dev/$GCP_PROJECT/$REPO_NAME/webui:latest" --project="$GCP_PROJECT" ./webui/ || { echo "❌ ERROR: Cloud Build failed." >&2; exit 1; }

# Deploy to Cloud Run
echo "Deploying container to Cloud Run..."
# We pass NO_AWS=true to Cloud Run as well, though the Web UI might not need it directly if it only calls CA API,
# but it's safe to have it.
gcloud run deploy froyo-agent-hub \
  --image "us-central1-docker.pkg.dev/$GCP_PROJECT/$REPO_NAME/webui:latest" \
  --region "us-central1" \
  --allow-unauthenticated \
  --project "$GCP_PROJECT" \
  --set-env-vars="GCP_PROJECT=$GCP_PROJECT,GOOGLE_CLOUD_PROJECT=$GCP_PROJECT,USE_LIVE_CA_API=1,AGENT_ID=froyo_lakehouse_analyst,GOOGLE_CLOUD_LOCATION=global,NO_AWS=true,USE_ADC_FOR_API=true" || { echo "❌ ERROR: Cloud Run deployment failed." >&2; exit 1; }

RUN_URL=$(gcloud run services describe froyo-agent-hub --region "us-central1" --project "$GCP_PROJECT" --format="value(status.url)")
echo ""
echo "🎉 Web App successfully deployed to Cloud Run!"
echo "👉 URL: $RUN_URL"
echo "⚠️  IMPORTANT: Please copy this URL and register it as an Authorized Redirect URI in your Google Cloud OAuth Client Credentials in the console:"
echo "   $RUN_URL/auth/callback"

echo ""
echo "=== Deployment Completed Successfully! ==="
