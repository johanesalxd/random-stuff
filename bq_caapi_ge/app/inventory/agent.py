from __future__ import annotations

import os

import google.auth
from google.adk.agents import Agent
from google.adk.models.google_llm import Gemini
from google.adk.tools.data_agent import DataAgentCredentialsConfig, DataAgentToolset

# Load configuration from environment
AGENT_INVENTORY_ID = os.getenv("AGENT_INVENTORY_ID", "agent-inventory-id-placeholder")
PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT", "project-id-placeholder")
LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION", "global")
MODEL_NAME = os.getenv("MODEL_NAME", "gemini-3-flash-preview")

# Construct the full resource name of the Data Agent
DATA_AGENT_NAME = (
    f"projects/{PROJECT_ID}/locations/global/dataAgents/{AGENT_INVENTORY_ID}"
)

# Get default credentials with the correct scope
scopes = ["https://www.googleapis.com/auth/cloud-platform"]
client_id = os.getenv("OAUTH_CLIENT_ID")
client_secret = os.getenv("OAUTH_CLIENT_SECRET")

if client_id and client_secret:
    # Use OAuth flow for Identity Passthrough
    creds_config = DataAgentCredentialsConfig(
        client_id=client_id,
        client_secret=client_secret,
        scopes=scopes,
    )
else:
    # Use Application Default Credentials (ADC) for local/service account auth
    creds, _ = google.auth.default(scopes=scopes)
    creds_config = DataAgentCredentialsConfig(credentials=creds)

# Initialize the Data Agent Toolset with the scoped credentials
data_agent_toolset = DataAgentToolset(credentials_config=creds_config)

# Define the Inventory Agent
root_agent = Agent(
    name="inventory_analyst",
    model=MODEL_NAME,
    instruction=f"""
    You are the Inventory & Product Analyst.
    Your goal is to answer user questions about stock levels, product catalog, and distribution.

    You have access to a specialized Data Agent tool.
    ALWAYS use the `ask_data_agent` tool to answer questions.

    When calling `ask_data_agent`, you MUST use the following agent name:
    {DATA_AGENT_NAME}

    Do not invent answers. If the tool returns data, summarize it clearly for the user.
    """,
    tools=[data_agent_toolset],
    description="Expert in stock levels, product catalog, and distribution logistics.",
)
