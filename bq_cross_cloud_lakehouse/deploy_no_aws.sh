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
source ./lib/no_aws.sh

if ! is_no_aws; then
  echo "ERROR: NO_AWS must be set to true in config.local.env for this deployment." >&2
  exit 1
fi

# Every child process (query scripts, create_agent.py, register_ge_agent.py)
# resolves the loyalty/sales location from this flag, so export it once here
# rather than prefixing each invocation.
export NO_AWS=true

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

#######################################
# Read a single KEY=value entry from a dotenv file, stripping quotes.
# Arguments:
#   $1 - path to the dotenv file
#   $2 - key to look up
# Outputs:
#   The value on stdout, empty when the key is absent.
#######################################
read_dotenv_value() {
  local file="$1"
  local key="$2"
  local value
  value="$(grep -m1 "^${key}=" "${file}" | cut -d'=' -f2- || true)"
  value="${value%\"}"; value="${value#\"}"
  value="${value%\'}"; value="${value#\'}"
  echo "${value}"
}

# The Web UI signs users in with OAuth and forwards their token to the
# Conversational Analytics API. Without real credentials the service would fall
# back to a mock sign-in, so require them up front rather than deploying an
# open endpoint.
OAUTH_CLIENT_ID="$(read_dotenv_value agent/.env OAUTH_CLIENT_ID)"
OAUTH_CLIENT_SECRET="$(read_dotenv_value agent/.env OAUTH_CLIENT_SECRET)"
FLASK_SECRET_KEY="$(read_dotenv_value agent/.env FLASK_SECRET_KEY)"

if [[ -z "${OAUTH_CLIENT_ID}" || -z "${OAUTH_CLIENT_SECRET}" ]]; then
  echo "❌ ERROR: OAUTH_CLIENT_ID and OAUTH_CLIENT_SECRET must be set in agent/.env." >&2
  echo "   The deployed Web UI is publicly reachable and will not start without them." >&2
  exit 1
fi

if [[ -z "${FLASK_SECRET_KEY}" ]]; then
  echo "FLASK_SECRET_KEY not set in agent/.env; generating one for this deployment."
  FLASK_SECRET_KEY="$(python3 -c 'import secrets; print(secrets.token_hex(32))')"
fi

echo "Deploying Conversational Analytics data agent..."
cd agent
# NO_AWS is exported above; create_agent.py resolves it via LakehouseConfig.
GOOGLE_API_USE_CLIENT_CERTIFICATE=false uv run python scripts/create_agent.py || { echo "❌ ERROR: Failed to create CA agent." >&2; exit 1; }

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
  GOOGLE_API_USE_CLIENT_CERTIFICATE=false uv run python scripts/register_ge_agent.py --force || { echo "❌ ERROR: Failed to register agent in GE." >&2; exit 1; }
fi
cd ..

echo "Building and deploying Web UI to Google Cloud Run..."

# Enable Cloud Build, Cloud Run, Artifact Registry and Secret Manager APIs
gcloud services enable --project="$GCP_PROJECT" \
  run.googleapis.com \
  artifactregistry.googleapis.com \
  cloudbuild.googleapis.com \
  secretmanager.googleapis.com || { echo "❌ ERROR: Failed to enable Web Deployment APIs." >&2; exit 1; }

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

# Store OAuth credentials in Secret Manager rather than passing them as
# plaintext environment variables on the Cloud Run revision.
echo "Syncing OAuth credentials to Secret Manager..."
upsert_secret() {
  local name="$1"
  local value="$2"
  if ! gcloud secrets describe "${name}" --project="$GCP_PROJECT" >/dev/null 2>&1; then
    gcloud secrets create "${name}" --replication-policy=automatic \
      --project="$GCP_PROJECT" >/dev/null || return 1
  fi
  printf '%s' "${value}" | gcloud secrets versions add "${name}" \
    --data-file=- --project="$GCP_PROJECT" >/dev/null || return 1
}

upsert_secret froyo-oauth-client-id "${OAUTH_CLIENT_ID}" || { echo "❌ ERROR: Failed to store OAUTH_CLIENT_ID." >&2; exit 1; }
upsert_secret froyo-oauth-client-secret "${OAUTH_CLIENT_SECRET}" || { echo "❌ ERROR: Failed to store OAUTH_CLIENT_SECRET." >&2; exit 1; }
upsert_secret froyo-flask-secret-key "${FLASK_SECRET_KEY}" || { echo "❌ ERROR: Failed to store FLASK_SECRET_KEY." >&2; exit 1; }

# Grant the Cloud Run runtime service account read access to those secrets.
PROJECT_NUMBER=$(gcloud projects describe "$GCP_PROJECT" --format="value(projectNumber)")
RUNTIME_SA="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"
for secret in froyo-oauth-client-id froyo-oauth-client-secret froyo-flask-secret-key; do
  gcloud secrets add-iam-policy-binding "${secret}" \
    --member="serviceAccount:${RUNTIME_SA}" \
    --role="roles/secretmanager.secretAccessor" \
    --project="$GCP_PROJECT" >/dev/null || { echo "❌ ERROR: Failed to grant access to ${secret}." >&2; exit 1; }
done

# Deploy to Cloud Run. Sessions are held in process memory, so the service is
# pinned to a single instance until that moves to a shared store.
#
# Queries run as the signed-in user's OAuth token, not the service identity:
# each demo user therefore needs BigQuery and Conversational Analytics access
# on this project. Setting USE_ADC_FOR_API would remove that check and let any
# visitor query as the service account, so it is deliberately left unset.
echo "Deploying container to Cloud Run..."
COMMON_ENV="GCP_PROJECT=$GCP_PROJECT,GOOGLE_CLOUD_PROJECT=$GCP_PROJECT,AGENT_ID=froyo_lakehouse_agent,GOOGLE_CLOUD_LOCATION=global,NO_AWS=true,COOKIE_SECURE=1"

deploy_webui() {
  gcloud run deploy froyo-agent-hub \
    --image "us-central1-docker.pkg.dev/$GCP_PROJECT/$REPO_NAME/webui:latest" \
    --region "us-central1" \
    --allow-unauthenticated \
    --max-instances 1 \
    --project "$GCP_PROJECT" \
    --set-secrets="OAUTH_CLIENT_ID=froyo-oauth-client-id:latest,OAUTH_CLIENT_SECRET=froyo-oauth-client-secret:latest,FLASK_SECRET_KEY=froyo-flask-secret-key:latest" \
    --set-env-vars="$1"
}

# First pass: the service URL is unknown until the service exists, and the OAuth
# redirect URI must point at it.
deploy_webui "$COMMON_ENV" || { echo "❌ ERROR: Cloud Run deployment failed." >&2; exit 1; }

RUN_URL=$(gcloud run services describe froyo-agent-hub --region "us-central1" --project "$GCP_PROJECT" --format="value(status.url)")

# Second pass: pin the redirect URI to the now-known service URL.
echo "Setting OAuth redirect URI to ${RUN_URL}/auth/callback..."
deploy_webui "${COMMON_ENV},OAUTH_REDIRECT_URI=${RUN_URL}/auth/callback" || { echo "❌ ERROR: Cloud Run redeploy failed." >&2; exit 1; }

echo ""
echo "🎉 Web App successfully deployed to Cloud Run!"
echo "👉 URL: $RUN_URL"
echo "⚠️  IMPORTANT: Register this exact URI as an Authorized Redirect URI on your"
echo "   OAuth client in the Google Cloud console, or sign-in will fail:"
echo "   $RUN_URL/auth/callback"

echo ""
echo "=== Deployment Completed Successfully! ==="
