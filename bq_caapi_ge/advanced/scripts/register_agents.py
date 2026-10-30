"""Utility for registering ADK Agent Engine agents in Gemini Enterprise."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
import sys
import urllib.error
import urllib.request

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv  # noqa: E402

from config.gcp_auth import get_gcloud_or_adc_access_token  # noqa: E402

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT")
PROJECT_NUMBER = os.getenv("GOOGLE_CLOUD_PROJECT_NUMBER")
APP_ID = os.getenv("GEMINI_APP_ID")
GE_LOCATION = os.getenv("GEMINI_APP_LOCATION", "global")
AUTH_ORDERS = os.getenv("AUTH_RESOURCE_ORDERS", "bq-caapi-oauth-orders")
AUTH_INVENTORY = os.getenv("AUTH_RESOURCE_INVENTORY", "bq-caapi-oauth-inventory")


def register_agent(
    display_name: str,
    description: str,
    reasoning_engine_resource: str,
    auth_resource: str | None = None,
) -> None:
    """Register an ADK agent with Gemini Enterprise via REST API.

    Args:
        display_name: The name to display in the UI.
        description: A brief description of the agent.
        reasoning_engine_resource: The full resource name of the deployed Agent Engine.
        auth_resource: The full path to an authorization resource.
    """
    logger.info("Registering %s...", display_name)

    token = get_gcloud_or_adc_access_token()

    url = (
        f"https://{GE_LOCATION}-discoveryengine.googleapis.com/v1alpha/"
        f"projects/{PROJECT_ID}/locations/{GE_LOCATION}/collections/default_collection/"
        f"engines/{APP_ID}/assistants/default_assistant/agents"
    )

    # Construct payload for ADK Agent (Agent Engine)
    payload: dict = {
        "displayName": display_name,
        "description": description,
        "adkAgentDefinition": {
            "provisionedReasoningEngine": {"reasoningEngine": reasoning_engine_resource}
        },
    }

    if auth_resource:
        payload["authorizationConfig"] = {"toolAuthorizations": [auth_resource]}

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    if PROJECT_ID:
        headers["X-Goog-User-Project"] = PROJECT_ID

    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            resp_body = resp.read().decode("utf-8")
            response_json = json.loads(resp_body) if resp_body.strip() else {}
            if "error" in response_json:
                logger.error(
                    "Registration failed for %s: %s", display_name, response_json["error"]
                )
            else:
                logger.info(
                    "Successfully registered %s: %s",
                    display_name,
                    response_json.get("name"),
                )
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8")
        try:
            err_json = json.loads(err_body)
            err_msg = err_json.get("error", {}).get("message", err_body)
        except json.JSONDecodeError:
            err_msg = err_body
        logger.error("Registration failed for %s (%s): %s", display_name, e.code, err_msg)
    except Exception as e:
        logger.error("Failed to execute registration request for %s: %s", display_name, e)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Register agents with Gemini Enterprise."
    )
    parser.add_argument(
        "--orders-resource",
        required=False,
        help="Reasoning Engine resource name for Orders Agent",
    )
    parser.add_argument(
        "--inventory-resource",
        required=False,
        help="Reasoning Engine resource name for Inventory Agent",
    )

    args = parser.parse_args()

    if not args.orders_resource and not args.inventory_resource:
        parser.error(
            "At least one of --orders-resource or --inventory-resource is required"
        )

    missing = [
        name
        for name, value in (
            ("GOOGLE_CLOUD_PROJECT", PROJECT_ID),
            ("GOOGLE_CLOUD_PROJECT_NUMBER", PROJECT_NUMBER),
            ("GEMINI_APP_ID", APP_ID),
        )
        if not value
    ]
    if missing:
        parser.error(f"Missing required environment variables: {', '.join(missing)}")

    # 1. Orders Agent
    if args.orders_resource:
        register_agent(
            "Order & User Analyst",
            "Expert in customer journeys and order tracking.",
            args.orders_resource,
            auth_resource=f"projects/{PROJECT_NUMBER}/locations/{GE_LOCATION}/authorizations/{AUTH_ORDERS}",
        )

    # 2. Inventory Agent
    if args.inventory_resource:
        register_agent(
            "Inventory & Product Analyst",
            "Expert in stock levels and product catalog.",
            args.inventory_resource,
            auth_resource=f"projects/{PROJECT_NUMBER}/locations/{GE_LOCATION}/authorizations/{AUTH_INVENTORY}",
        )
