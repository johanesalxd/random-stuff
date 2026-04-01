from __future__ import annotations

import logging
import os

from google.adk.agents import Agent
from google.adk.tools.data_agent import DataAgentCredentialsConfig, DataAgentToolset

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
AGENT_ORDERS_ID = os.getenv("AGENT_ORDERS_ID", "agent-orders-id-placeholder")
PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT", "project-id-placeholder")
MODEL_NAME = os.getenv("MODEL_NAME", "gemini-2.5-flash")

# Session state key where Gemini Enterprise deposits the user's OAuth token.
# Must match the AUTH_RESOURCE_ORDERS value used when registering the agent.
AUTH_RESOURCE_ID = os.getenv("AUTH_RESOURCE_ORDERS", "bq-caapi-oauth")

DATA_AGENT_NAME = f"projects/{PROJECT_ID}/locations/global/dataAgents/{AGENT_ORDERS_ID}"

# DataAgentCredentialsConfig reads the OAuth access token directly from
# session state at AUTH_RESOURCE_ID on every tool call — no bridge callback,
# no client credentials, no hardcoded expiry.
creds_config = DataAgentCredentialsConfig(
    external_access_token_key=AUTH_RESOURCE_ID,
)

data_agent_toolset = DataAgentToolset(credentials_config=creds_config)

root_agent = Agent(
    name="orders_analyst",
    model=MODEL_NAME,
    instruction=f"Use ask_data_agent with: {DATA_AGENT_NAME}. Summarize results clearly.",
    tools=[data_agent_toolset],
    description="Expert in customer journeys, order statuses, and site events.",
)
