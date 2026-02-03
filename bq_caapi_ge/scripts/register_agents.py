"""Utility for registering A2A agents in Gemini Enterprise."""

import json
import os
import subprocess
import sys

from dotenv import load_dotenv

# Load environment variables
load_dotenv()

PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT")
PROJECT_NUMBER = os.getenv("GOOGLE_CLOUD_PROJECT_NUMBER")
APP_ID = os.getenv("GEMINI_APP_ID")
LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION", "global")
OAUTH_CLIENT_ID = os.getenv("OAUTH_CLIENT_ID")
OAUTH_CLIENT_SECRET = os.getenv("OAUTH_CLIENT_SECRET")
AUTH_ORDERS = os.getenv("AUTH_RESOURCE_ORDERS", "bq-caapi-oauth")
AUTH_INVENTORY = os.getenv("AUTH_RESOURCE_INVENTORY", "bq-caapi-oauth-inventory")


def register_agent(
    display_name: str,
    description: str,
    agent_card: dict,
    auth_resource: str | None = None,
) -> None:
    """Register an A2A agent with Gemini Enterprise via REST API.

    Args:
        display_name: The name to display in the UI.
        description: A brief description of the agent.
        agent_card: The A2A protocol agent card.
        auth_resource: The full path to an authorization resource.
    """
    print(f"Registering {display_name}...")

    # We use curl to call the REST API as it's easier to handle the v1alpha endpoint
    token = (
        subprocess.check_output(["gcloud", "auth", "print-access-token"])
        .decode()
        .strip()
    )

    url = (
        f"https://{LOCATION}-discoveryengine.googleapis.com/v1alpha/"
        f"projects/{PROJECT_ID}/locations/{LOCATION}/collections/default_collection/"
        f"engines/{APP_ID}/assistants/default_assistant/agents"
    )

    payload = {
        "displayName": display_name,
        "description": description,
        "a2aAgentDefinition": {"jsonAgentCard": json.dumps(agent_card)},
    }

    if auth_resource:
        payload["authorizationConfig"] = {"agentAuthorization": auth_resource}

    cmd = [
        "curl",
        "-X",
        "POST",
        "-H",
        f"Authorization: Bearer {token}",
        "-H",
        "Content-Type: application/json",
        "-H",
        f"X-Goog-User-Project: {PROJECT_ID}",
        url,
        "-d",
        json.dumps(payload),
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0:
        print(f"Success! Response: {result.stdout}")
    else:
        print(f"Failed! Error: {result.stderr}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python register_agents.py <BRIDGE_BASE_URL>")
        print("Example: python register_agents.py https://xyz.ngrok-free.app")
        sys.exit(1)

    base_url = sys.argv[1].rstrip("/")

    # 1. Orders Agent
    register_agent(
        "Order & User Analyst",
        "Expert in customer journeys and order tracking.",
        {
            "protocolVersion": "0.3.0",
            "name": "Order & User Analyst",
            "description": "Analyze orders and user events.",
            "url": f"{base_url}/orders/chat",
            "version": "1.0.0",
            "capabilities": {},
            "skills": [
                {
                    "id": "chat",
                    "name": "Chat",
                    "description": "Chat with analyst",
                    "tags": [],
                }
            ],
            "defaultInputModes": ["text/plain"],
            "defaultOutputModes": ["text/plain"],
        },
        auth_resource=f"projects/{PROJECT_NUMBER}/locations/{LOCATION}/authorizations/{AUTH_ORDERS}",
    )

    # 2. Inventory Agent
    register_agent(
        "Inventory & Product Analyst",
        "Expert in stock levels and product catalog.",
        {
            "protocolVersion": "0.3.0",
            "name": "Inventory & Product Analyst",
            "description": "Analyze stock and products.",
            "url": f"{base_url}/inventory/chat",
            "version": "1.0.0",
            "capabilities": {},
            "skills": [
                {
                    "id": "chat",
                    "name": "Chat",
                    "description": "Chat with analyst",
                    "tags": [],
                }
            ],
            "defaultInputModes": ["text/plain"],
            "defaultOutputModes": ["text/plain"],
        },
        auth_resource=f"projects/{PROJECT_NUMBER}/locations/{LOCATION}/authorizations/{AUTH_INVENTORY}",
    )
