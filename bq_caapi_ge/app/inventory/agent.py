from __future__ import annotations

import os

from google.adk.agents import Agent
from google.adk.tools.data_agent import DataAgentCredentialsConfig, DataAgentToolset

# Load configuration from environment
AGENT_INVENTORY_ID = os.getenv("AGENT_INVENTORY_ID", "agent-inventory-id-placeholder")
PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT", "project-id-placeholder")
MODEL_NAME = os.getenv("MODEL_NAME", "gemini-2.5-flash")

# Construct the full resource name of the Data Agent
DATA_AGENT_NAME = (
    f"projects/{PROJECT_ID}/locations/global/dataAgents/{AGENT_INVENTORY_ID}"
)

# OAuth Identity Passthrough Configuration (REQUIRED for Gemini Enterprise)
# These credentials enable the Data Agent to access BigQuery as the end user
OAUTH_CLIENT_ID = os.getenv("OAUTH_CLIENT_ID")
OAUTH_CLIENT_SECRET = os.getenv("OAUTH_CLIENT_SECRET")
SCOPES = ["https://www.googleapis.com/auth/cloud-platform"]

# Configure credentials for OAuth identity passthrough
# The DataAgentToolset will use these to set up the OAuth flow
# when called from Gemini Enterprise
creds_config = DataAgentCredentialsConfig(
    client_id=OAUTH_CLIENT_ID,
    client_secret=OAUTH_CLIENT_SECRET,
    scopes=SCOPES,
)

# Initialize the Data Agent Toolset with OAuth passthrough configuration
data_agent_toolset = DataAgentToolset(credentials_config=creds_config)

# Define the Inventory Agent
root_agent = Agent(
    name="inventory_analyst",
    model=MODEL_NAME,
    instruction=f"You are the Inventory & Product Analyst. Use the ask_data_agent tool with agent name: {DATA_AGENT_NAME}",
    tools=[data_agent_toolset],
    description="Expert in stock levels, product catalog, and distribution logistics.",
)
