"""Utility for registering A2A agents in Gemini Enterprise."""

import json
import os
import subprocess
import sys

from dotenv import load_dotenv

# Load environment variables
load_dotenv()

PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT")
APP_ID = os.getenv("GEMINI_APP_ID")
LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION", "global")
OAUTH_CLIENT_ID = os.getenv("OAUTH_CLIENT_ID")
OAUTH_CLIENT_SECRET = os.getenv("OAUTH_CLIENT_SECRET")


def register_agent(
    display_name: str,
    description: str,
    agent_card: dict,
    client_id: str | None = None,
    client_secret: str | None = None,
) -> None:
    """Register an A2A agent with Gemini Enterprise via REST API.

    Args:
        display_name: The name to display in the UI.
        description: A brief description of the agent.
        agent_card: The A2A protocol agent card.
        client_id: OAuth 2.0 client ID for identity passthrough.
        client_secret: OAuth 2.0 client secret for identity passthrough.
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

    if client_id and client_secret:
        payload["authorizationConfig"] = {
            "a2aAuthorization": {
                "serverSideOauth2": {
                    "clientId": client_id,
                    "clientSecret": client_secret,
                    "authorizationUri": f"https://accounts.google.com/o/oauth2/v2/auth?client_id={client_id}&redirect_uri=https%3A%2F%2Fvertexaisearch.cloud.google.com%2Fstatic%2Foauth%2Foauth.html&scope=https%3A%2F%2Fwww.googleapis.com%2Fauth%2Fbigquery&include_granted_scopes=true&response_type=code&access_type=offline&prompt=consent",
                    "tokenUri": "https://oauth2.googleapis.com/token",
                }
            }
        }

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
                {"id": "chat", "name": "Chat", "description": "Chat with analyst"}
            ],
            "defaultInputModes": ["text/plain"],
            "defaultOutputModes": ["text/plain"],
        },
        client_id=OAUTH_CLIENT_ID,
        client_secret=OAUTH_CLIENT_SECRET,
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
                {"id": "chat", "name": "Chat", "description": "Chat with analyst"}
            ],
            "defaultInputModes": ["text/plain"],
            "defaultOutputModes": ["text/plain"],
        },
        client_id=OAUTH_CLIENT_ID,
        client_secret=OAUTH_CLIENT_SECRET,
    )
