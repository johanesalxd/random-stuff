#!/usr/bin/env bash
# deploy_demo.sh
# Coordinates the sequential deployment of the cross-cloud Lakehouse demo.

set -euo pipefail
cd "$(dirname "$0")"

# Error trap to print a cleanup tip if the deploy fails midway
cleanup_tip() {
  local exit_code=$?
  if [[ $exit_code -ne 0 ]]; then
    echo "" >&2
    echo "⚠️  Deployment failed! If some GCP/AWS resources were already created," >&2
    echo "   you can clean them up by running: ./teardown_demo.sh" >&2
  fi
}
trap cleanup_tip EXIT

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

# Reset DISCOVERY_DATASET to empty for new deployment
if [[ -n "${DISCOVERY_DATASET:-}" ]]; then
  sed -i 's|export DISCOVERY_DATASET=".*"|export DISCOVERY_DATASET=""|g' config.local.env
  export DISCOVERY_DATASET=""
fi

# Check and auto-install gcloud alpha component if missing
if ! gcloud alpha help >/dev/null 2>&1; then
  echo "⚠️  gcloud alpha component is required but not installed."
  read -p "Would you like to install the 'alpha' component now? [Y/n]: " install_alpha
  if [[ ! "$install_alpha" =~ ^[Nn]$ ]]; then
    echo "Installing gcloud alpha component..."
    gcloud components install alpha --quiet
  else
    echo "❌ ERROR: gcloud alpha component is required. Exiting." >&2
    exit 1
  fi
fi

# Variable validation and CLI prompting helper
validate_and_prompt() {
  local var_name="$1"
  local placeholder="$2"
  local description="$3"
  local current_value="${!var_name:-}"

  local is_invalid=0
  if [[ -z "$current_value" ]]; then
    is_invalid=1
  elif [[ "$current_value" == "$placeholder" ]]; then
    is_invalid=1
  elif [[ "$current_value" == *"CHANGE-ME"* ]]; then
    is_invalid=1
  fi

  # Special rule for AWS Account ID (must be exactly 12 digits)
  if [[ "$var_name" == "AWS_ACCOUNT_ID" && ! "$current_value" =~ ^[0-9]{12}$ ]]; then
    is_invalid=1
  fi

  if [[ $is_invalid -eq 1 ]]; then
    echo "⚠️  Variable $var_name is unset, matches placeholder, or is invalid: '$current_value'"
    local new_value=""
    while [[ -z "$new_value" ]]; do
      read -p "Enter value for $var_name ($description): " new_value
      if [[ "$var_name" == "AWS_ACCOUNT_ID" && ! "$new_value" =~ ^[0-9]{12}$ ]]; then
        echo "Error: AWS Account ID must be exactly 12 digits."
        new_value=""
      fi
    done

    # Update the environment variable in memory
    eval "export $var_name=\"$new_value\""

    # Update in config.local.env
    sed -i "s|export $var_name=\".*\"|export $var_name=\"$new_value\"|g" config.local.env
    echo "Updated $var_name in config.local.env."
  fi
}

validate_and_prompt "GCP_PROJECT" "my-gcp-project" "your GCP Project ID"
validate_and_prompt "AWS_ACCOUNT_ID" "123456789012" "your 12-digit AWS Account ID"
validate_and_prompt "S3_BUCKET" "CHANGE-ME-unique-lakehouse-demo" "globally-unique S3 bucket name"
validate_and_prompt "GCS_PDF_BUCKET" "CHANGE-ME-unique-froyo-pdfs" "globally-unique GCS bucket name"

# Enable required GCP APIs automatically
echo "Enabling required GCP services..."
gcloud services enable --project="$GCP_PROJECT" \
  biglake.googleapis.com \
  bigquery.googleapis.com \
  dataplex.googleapis.com || { echo "❌ ERROR: Failed to enable required GCP APIs." >&2; exit 1; }

# Confirm AWS credentials before starting
echo "Checking AWS credentials..."
./aws/01_verify.sh || { echo "❌ ERROR: AWS credentials verification failed. Make sure you logged in (e.g. 'aws sso login')." >&2; exit 1; }

# -------------------------------------------------------------
# 2. Provision AWS S3 & Glue resources
# -------------------------------------------------------------
echo ""
echo "=== Phase 2: Deploying AWS S3 & Glue Dataset ==="
./aws/10_s3_glue.sh || { echo "❌ ERROR: AWS S3 and Glue database deployment failed." >&2; exit 1; }
./aws/11_iceberg_tables_athena.sh || { echo "❌ ERROR: Iceberg tables creation / seeding via Athena failed." >&2; exit 1; }
./aws/20_iam_role.sh || { echo "❌ ERROR: AWS IAM role creation failed." >&2; exit 1; }
echo "✅ AWS storage and IAM resources provisioned successfully."

# -------------------------------------------------------------
# 3. Create Federated Catalog and Bootstrap OIDC
# -------------------------------------------------------------
echo ""
echo "=== Phase 3: Bootstrap Federation (GCP to AWS) ==="
echo "Creating BigLake federated catalog..."
SA_ID=$(./gcp/10_create_federated_catalog.sh) || { echo "❌ ERROR: GCP BigLake federated catalog creation failed." >&2; exit 1; }

echo "GCP BigLake Service Account minted: $SA_ID"
echo "Updating AWS trust policy with the Service Account ID..."
./aws/30_update_trust_policy.sh "$SA_ID" || { echo "❌ ERROR: Finalizing AWS trust policy failed." >&2; exit 1; }

echo "Waiting 120 seconds for AWS IAM trust policy propagation..."
sleep 120
echo "✅ OIDC trust policy updated on AWS IAM role."

# -------------------------------------------------------------
# 4. Finalize Federation Sync & Verification
# -------------------------------------------------------------
echo ""
echo "=== Phase 4: Finalizing Federation ==="
./gcp/20_enable_refresh.sh || { echo "❌ ERROR: Enabling metadata refresh schedule failed." >&2; exit 1; }

# Retry verification loop to handle AWS IAM propagation delay
retry_count=0
max_retries=3
verified=0

while [ $retry_count -lt $max_retries ]; do
  echo "Verifying federation sync (attempt $((retry_count + 1)) of $max_retries)..."
  if ./gcp/30_verify.sh; then
    verified=1
    break
  else
    retry_count=$((retry_count + 1))
    if [ $retry_count -lt $max_retries ]; then
      echo "⚠️  Federation sync verification failed. This is common if AWS IAM has not propagated yet."
      read -p "Would you like to trigger another metadata refresh and retry verification now? [Y/n]: " retry_choice
      if [[ "$retry_choice" =~ ^[Nn]$ ]]; then
        break
      fi
      echo "Re-triggering metadata refresh..."
      ./gcp/20_enable_refresh.sh || { echo "❌ ERROR: Re-enabling metadata refresh failed." >&2; exit 1; }
    fi
  fi
done

if [ $verified -eq 0 ]; then
  echo "❌ ERROR: Federation sync verification failed after $max_retries attempts. The Iceberg tables did not propagate to BigQuery." >&2
  exit 1
fi
echo "✅ Federation sync verified. AWS Iceberg tables are queryable from BigQuery."

# -------------------------------------------------------------
# 5. Data Seeding & Query Execution
# -------------------------------------------------------------
echo ""
echo "=== Phase 5: Seeding Data & Running Queries ==="
# Seed the deterministic native BigQuery allergen & recipe metadata
./gcp/05_seed_native_bq.sh || { echo "❌ ERROR: Seeding native BigQuery tables failed." >&2; exit 1; }

# Optional Knowledge Catalog flow
read -p "Do you want to run the optional Dataplex Knowledge Catalog extraction? (takes ~20m) [y/N]: " run_datacatalog
if [[ "$run_datacatalog" =~ ^[Yy]$ ]]; then
  echo "Running Dataplex Knowledge Catalog extraction (this will take time)..."
  ./gcp/06_knowledge_catalog.sh || { echo "❌ ERROR: Dataplex Knowledge Catalog extraction failed." >&2; exit 1; }
else
  echo "Skipped Dataplex Knowledge Catalog extraction. Using seeded BigQuery tables."
fi

# Run the final demo queries & ML model
echo "Executing cross-cloud allergen target join query..."
./gcp/40_query_froyo.sh || { echo "❌ ERROR: Froyo cross-cloud query execution failed." >&2; exit 1; }

echo "Training and running BigQuery ML forecast..."
./gcp/50_forecast_bqml.sh 92 || { echo "❌ ERROR: BigQuery ML ARIMA forecasting failed." >&2; exit 1; }
echo "✅ Froyo queries executed and ARIMA forecast completed successfully."

# -------------------------------------------------------------
# 6. Deploy Conversational Analytics Agent & Web App UI
# -------------------------------------------------------------
echo ""
echo "=== Phase 6: Deploying Conversational Analytics Agent & Web App UI ==="
read -p "Do you want to deploy the CA Agent & Web App UI to Cloud Run? [y/N]: " deploy_webapp
if [[ "$deploy_webapp" =~ ^[Yy]$ ]]; then
  echo "Deploying Conversational Analytics data agent..."
  cd agent
  GOOGLE_API_USE_CLIENT_CERTIFICATE=false uv run python scripts/create_agent.py || { echo "❌ ERROR: Failed to create CA agent." >&2; exit 1; }
  GOOGLE_API_USE_CLIENT_CERTIFICATE=false uv run python scripts/register_ge_agent.py --force || { echo "❌ ERROR: Failed to register agent in GE." >&2; exit 1; }
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
  gcloud run deploy froyo-agent-hub \
    --image "us-central1-docker.pkg.dev/$GCP_PROJECT/$REPO_NAME/webui:latest" \
    --region "us-central1" \
    --allow-unauthenticated \
    --project "$GCP_PROJECT" \
    --set-env-vars="GCP_PROJECT=$GCP_PROJECT,USE_LIVE_CA_API=1,AGENT_ID=froyo_lakehouse_analyst,GOOGLE_CLOUD_LOCATION=us-east4" || { echo "❌ ERROR: Cloud Run deployment failed." >&2; exit 1; }

  RUN_URL=$(gcloud run services describe froyo-agent-hub --region "us-central1" --project "$GCP_PROJECT" --format="value(status.url)")
  echo ""
  echo "🎉 Web App successfully deployed to Cloud Run!"
  echo "👉 URL: $RUN_URL"
  echo "⚠️  IMPORTANT: Please copy this URL and register it as an Authorized Redirect URI in your Google Cloud OAuth Client Credentials in the console:"
  echo "   $RUN_URL/auth/callback"
else
  echo "Skipped Web App deployment."
fi

echo ""
echo "=== Deployment & Demo Execution Completed Successfully! ==="
