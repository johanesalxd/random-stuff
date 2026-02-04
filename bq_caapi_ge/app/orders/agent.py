from __future__ import annotations

import os

from google.adk.agents import Agent
from google.adk.models.google_llm import Gemini
from google.adk.tools.data_agent import DataAgentCredentialsConfig, DataAgentToolset

# Load configuration from environment
AGENT_ORDERS_ID = os.getenv("AGENT_ORDERS_ID", "agent-orders-id-placeholder")
PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT", "project-id-placeholder")
LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION", "global")
MODEL_NAME = os.getenv("MODEL_NAME", "gemini-3-flash-preview")

# Construct the full resource name of the Data Agent
DATA_AGENT_NAME = f"projects/{PROJECT_ID}/locations/global/dataAgents/{AGENT_ORDERS_ID}"

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

# Define the Orders Agent
root_agent = Agent(
    name="orders_analyst",
    model=MODEL_NAME,
    instruction=f"""
    You are the Order & User Analyst.
    Your goal is to answer user questions about orders, items, and customer profiles.

    You have access to a specialized Data Agent tool.
    ALWAYS use the `ask_data_agent` tool to answer questions.

    When calling `ask_data_agent`, you MUST use the following agent name:
    {DATA_AGENT_NAME}

    Do not invent answers. If the tool returns data, summarize it clearly for the user.
    """,
    tools=[data_agent_toolset],
    description="Expert in customer journeys, order statuses, and site events.",
)
