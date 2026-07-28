#!/bin/bash

# Deployment script for ADK Agents to Vertex AI Agent Engine

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

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

echo -e "${GREEN}Environment loaded${NC}"
echo "  Project: $GOOGLE_CLOUD_PROJECT"
echo ""

PROJECT_ID="$GOOGLE_CLOUD_PROJECT"
LOCATION="us-central1"

deploy_agent() {
    local agent_dir=$1
    local display_name=$2
    
    echo -e "${YELLOW}Deploying $display_name...${NC}"
    
    # 'set -e' aborts the script if this deploy fails, so reaching the next
    # line means the deploy succeeded.
    uv run adk deploy agent_engine "$agent_dir" \
        --project="$PROJECT_ID" \
        --region="$LOCATION" \
        --display_name="$display_name"

    echo -e "${GREEN}$display_name deployed successfully${NC}"
    echo ""
}

echo -e "${YELLOW}=== Deploying Orders Agent ===${NC}"
deploy_agent "advanced/app/orders" "Orders Analyst"

echo -e "${YELLOW}=== Deploying Inventory Agent ===${NC}"
deploy_agent "advanced/app/inventory" "Inventory Analyst"

echo -e "${GREEN}=== Deployment Complete ===${NC}"
echo ""
echo "Next steps:"
echo "1. Note the Reasoning Engine resource names from the output above"
echo "2. Create the OAuth authorizations (once): uv run python advanced/scripts/setup_auth.py"
echo "3. Register with Gemini Enterprise, passing the resource names as flags:"
echo "   uv run python advanced/scripts/register_agents.py \\"
echo "     --orders-resource <ORDERS_REASONING_ENGINE_RESOURCE> \\"
echo "     --inventory-resource <INVENTORY_REASONING_ENGINE_RESOURCE>"
