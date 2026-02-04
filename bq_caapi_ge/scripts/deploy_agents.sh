#!/bin/bash

# Deployment script for ADK Agents to Vertex AI Agent Engine
# This script redeploys the agents with the fixed OAuth passthrough configuration

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== ADK Agent Deployment Script ===${NC}"
echo ""

# Load environment variables from root .env
if [ -f .env ]; then
    echo -e "${GREEN}Loading environment variables from .env${NC}"
    export $(cat .env | xargs)
else
    echo -e "${RED}ERROR: .env file not found in project root${NC}"
    exit 1
fi

# Verify required environment variables
if [ -z "$GOOGLE_CLOUD_PROJECT" ]; then
    echo -e "${RED}ERROR: GOOGLE_CLOUD_PROJECT not set${NC}"
    exit 1
fi

if [ -z "$OAUTH_CLIENT_ID" ] || [ -z "$OAUTH_CLIENT_SECRET" ]; then
    echo -e "${RED}ERROR: OAuth credentials not set (OAUTH_CLIENT_ID or OAUTH_CLIENT_SECRET)${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Environment variables loaded${NC}"
echo "  Project: $GOOGLE_CLOUD_PROJECT"
echo "  OAuth Client ID: ${OAUTH_CLIENT_ID:0:30}..."
echo ""

# Configuration
PROJECT_ID="johanesa-playground-326616"
LOCATION="us-central1"

echo -e "${YELLOW}=== Deployment Configuration ===${NC}"
echo "  Project ID: $PROJECT_ID"
echo "  Location: $LOCATION"
echo "  Mode: Create new agents"
echo ""

# Function to deploy an agent (creates new agent if no ID provided)
deploy_agent() {
    local agent_dir=$1
    local display_name=$2
    
    echo -e "${YELLOW}Deploying $display_name...${NC}"
    
    uv run adk deploy agent_engine "$agent_dir" \
        --project="$PROJECT_ID" \
        --region="$LOCATION" \
        --display_name="$display_name"
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ $display_name deployed successfully${NC}"
        echo ""
    else
        echo -e "${RED}✗ Failed to deploy $display_name${NC}"
        exit 1
    fi
}

# Deploy Orders Agent
echo -e "${YELLOW}=== Step 1: Deploying Orders Agent ===${NC}"
deploy_agent "app/orders" "Orders Analyst"

# Deploy Inventory Agent
echo -e "${YELLOW}=== Step 2: Deploying Inventory Agent ===${NC}"
deploy_agent "app/inventory" "Inventory Analyst"

echo -e "${GREEN}=== Deployment Complete ===${NC}"
echo ""
echo -e "${YELLOW}Next Steps:${NC}"
echo "1. Wait ~1-2 minutes for agents to fully initialize"
echo "2. Run verification script: bash scripts/final_verify.sh"
echo "3. Check logs if issues persist:"
echo "   gcloud logging read 'resource.type=\"aiplatform.googleapis.com/ReasoningEngine\"' --limit=50"
echo ""
