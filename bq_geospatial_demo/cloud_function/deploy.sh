#!/bin/bash

# ============================================================================
# Cloud Function Deployment Script
# ============================================================================
# This script deploys the route optimization Cloud Function to Google Cloud.
#
# Prerequisites:
# 1. gcloud CLI installed and authenticated
# 2. Google Maps API key
# 3. Billing enabled on your GCP project
# ============================================================================

set -e  # Exit on error

# ============================================================================
# Configuration - UPDATE THESE VALUES
# ============================================================================

# Your Google Cloud Project ID
PROJECT_ID="${PROJECT_ID:-your-project-id}"

# Cloud Function region
REGION="${REGION:-us-central1}"

# Google Maps API Key
# IMPORTANT: In production, use Secret Manager instead
MAPS_API_KEY="${MAPS_API_KEY:-your-maps-api-key}"

# Function name
FUNCTION_NAME="optimize-route"

# ============================================================================
# Validation
# ============================================================================

if [ "$PROJECT_ID" = "your-project-id" ]; then
    echo "ERROR: Please set PROJECT_ID environment variable or update this script"
    echo "Usage: export PROJECT_ID=your-project-id && ./deploy.sh"
    exit 1
fi

if [ "$MAPS_API_KEY" = "your-maps-api-key" ]; then
    echo "ERROR: Please set MAPS_API_KEY environment variable or update this script"
    echo "Usage: export MAPS_API_KEY=your-api-key && ./deploy.sh"
    exit 1
fi

echo "============================================================================"
echo "Deploying Cloud Function: $FUNCTION_NAME"
echo "Project: $PROJECT_ID"
echo "Region: $REGION"
echo "============================================================================"

# ============================================================================
# Set the active project
# ============================================================================

echo "Setting active project..."
gcloud config set project "$PROJECT_ID"

# ============================================================================
# Enable required APIs
# ============================================================================

echo "Enabling required APIs..."
gcloud services enable cloudfunctions.googleapis.com
gcloud services enable cloudbuild.googleapis.com
gcloud services enable run.googleapis.com

# ============================================================================
# Deploy the Cloud Function (Gen 2)
# ============================================================================

echo "Deploying Cloud Function..."
gcloud functions deploy "$FUNCTION_NAME" \
  --gen2 \
  --runtime=python311 \
  --region="$REGION" \
  --source=. \
  --entry-point=optimize_route \
  --trigger-http \
  --allow-unauthenticated \
  --set-env-vars MAPS_API_KEY="$MAPS_API_KEY" \
  --timeout=60s \
  --memory=256MB \
  --max-instances=10

# ============================================================================
# Get the function URL
# ============================================================================

echo ""
echo "============================================================================"
echo "Deployment complete!"
echo "============================================================================"

FUNCTION_URL=$(gcloud functions describe "$FUNCTION_NAME" \
  --region="$REGION" \
  --gen2 \
  --format="value(serviceConfig.uri)")

echo "Function URL: $FUNCTION_URL"
echo ""
echo "Next steps:"
echo "1. Create BigQuery connection in the BigQuery Console"
echo "2. Grant the connection service account 'Cloud Functions Invoker' role:"
echo "   gcloud functions add-invoker-policy-binding $FUNCTION_NAME \\"
echo "     --region=$REGION \\"
echo "     --member='serviceAccount:SERVICE_ACCOUNT_FROM_BQ_CONNECTION'"
echo "3. Update sql/05_maps_api_integration.sql with:"
echo "   - endpoint = '$FUNCTION_URL'"
echo "   - your project and dataset names"
echo "============================================================================"
