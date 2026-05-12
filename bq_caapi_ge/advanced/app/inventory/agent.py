from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timedelta
from typing import Any, Optional

from google.adk.agents import Agent
from google.adk.tools.base_tool import BaseTool
from google.adk.tools.data_agent import DataAgentCredentialsConfig, DataAgentToolset
from google.adk.tools.tool_context import ToolContext

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
AGENT_INVENTORY_ID = os.getenv("AGENT_INVENTORY_ID", "agent-inventory-id-placeholder")
PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT", "project-id-placeholder")
MODEL_NAME = os.getenv("MODEL_NAME", "gemini-2.5-flash")
AUTH_RESOURCE_ID = os.getenv("AUTH_RESOURCE_INVENTORY", "bq-caapi-oauth-inventory")

DATA_AGENT_NAME = (
    f"projects/{PROJECT_ID}/locations/global/dataAgents/{AGENT_INVENTORY_ID}"
)

# OAuth Configuration
OAUTH_CLIENT_ID = os.getenv("OAUTH_CLIENT_ID")
OAUTH_CLIENT_SECRET = os.getenv("OAUTH_CLIENT_SECRET")
SCOPES = ["https://www.googleapis.com/auth/cloud-platform"]
TOKEN_CACHE_KEY = "data_agent_token_cache"


async def bridge_oauth_token(
    tool: BaseTool,
    args: dict[str, Any],
    tool_context: ToolContext,
) -> Optional[dict]:
    """Bridge OAuth token from Gemini Enterprise to DataAgentToolset.

    Copies the access token from the Gemini Enterprise location (AUTH_RESOURCE_ID)
    to the DataAgentToolset expected location (TOKEN_CACHE_KEY).
    """
    access_token = tool_context.state.get(AUTH_RESOURCE_ID)

    if access_token:
        existing_token = tool_context.state.get(TOKEN_CACHE_KEY)

        if not existing_token:
            # Set expiry 1 hour from now (access tokens typically last 1 hour)
            expiry_time = (datetime.utcnow() + timedelta(hours=1)).strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            )

            # Format expected by google.oauth2.credentials.Credentials.from_authorized_user_info
            token_data = {
                "token": access_token,
                "refresh_token": "",  # Empty - no refresh token from Gemini Enterprise
                "token_uri": "https://oauth2.googleapis.com/token",
                "client_id": OAUTH_CLIENT_ID,
                "client_secret": OAUTH_CLIENT_SECRET,
                "scopes": SCOPES,
                "expiry": expiry_time,
            }

            tool_context.state[TOKEN_CACHE_KEY] = json.dumps(token_data)
            logger.info(
                f"OAuth token bridged from '{AUTH_RESOURCE_ID}' to '{TOKEN_CACHE_KEY}'"
            )
        else:
            logger.info("Token already bridged, skipping")
    else:
        logger.warning(f"No token found at '{AUTH_RESOURCE_ID}'")

    return None


# Credentials config for OAuth identity passthrough
creds_config = DataAgentCredentialsConfig(
    client_id=OAUTH_CLIENT_ID,
    client_secret=OAUTH_CLIENT_SECRET,
    scopes=SCOPES,
)

data_agent_toolset = DataAgentToolset(credentials_config=creds_config)

root_agent = Agent(
    name="inventory_analyst",
    model=MODEL_NAME,
    instruction=f"Use ask_data_agent with: {DATA_AGENT_NAME}. Summarize results clearly.",
    tools=[data_agent_toolset],
    description="Expert in stock levels, product catalog, and distribution logistics.",
    before_tool_callback=bridge_oauth_token,
)
