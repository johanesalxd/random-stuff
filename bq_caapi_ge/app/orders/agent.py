from __future__ import annotations

import os

from google.adk.agents import Agent
from google.adk.tools.data_agent import DataAgentToolset


# Load configuration from environment
# These variables should be set in the environment or .env file.
AGENT_ORDERS_ID = os.getenv("AGENT_ORDERS_ID", "agent-orders-id-placeholder")
PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT", "project-id-placeholder")
LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION", "global")
MODEL_NAME = os.getenv("MODEL_NAME", "gemini-3-flash-preview")

# Construct the full resource name of the Data Agent
# The location for CA API is typically 'global'.
DATA_AGENT_NAME = f"projects/{PROJECT_ID}/locations/global/dataAgents/{AGENT_ORDERS_ID}"

# Initialize the Data Agent Toolset
# This toolset provides the 'ask_data_agent' tool which proxies queries to the CA API.
# By default, it uses ADC (Application Default Credentials).
data_agent_toolset = DataAgentToolset()

# Define the Orders Agent
# This agent acts as a natural language interface to the backend Data Agent.
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
