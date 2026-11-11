"""Utility for registering ADK Agent Engine agents in Gemini Enterprise."""

from __future__ import annotations

import argparse
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

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def register_agent(
    display_name: str,
    description: str,
    reasoning_engine_resource: str,
    auth_resource: str | None = None,
    *,
    project_id: str,
    app_id: str,
    ge_location: str = "global",
) -> None:
    """Register an ADK agent with Gemini Enterprise via REST API.

    Args:
        display_name: The name to display in the UI.
        description: A brief description of the agent.
        reasoning_engine_resource: The full resource name of the deployed Agent Engine.
        auth_resource: The full path to an authorization resource.
        project_id: Google Cloud project ID.
        app_id: Gemini Enterprise application ID.
        ge_location: Gemini Enterprise location.
    """
    logger.info("Registering %s...", display_name)

    token = get_gcloud_or_adc_access_token()

    url = (
        f"https://{ge_location}-discoveryengine.googleapis.com/v1alpha/"
        f"projects/{project_id}/locations/{ge_location}/collections/default_collection/"
        f"engines/{app_id}/assistants/default_assistant/agents"
    )

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
    if project_id:
        headers["X-Goog-User-Project"] = project_id

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


def main() -> None:
    default_auth_id = os.getenv("AUTH_RESOURCE_SEMANTIC_ANALYTICS", "bq-caapi-oauth-semantic")
    default_reasoning_engine = os.getenv("SEMANTIC_REASONING_ENGINE_ID", "")
    default_description = "High-precision semantic analytics agent powered by ADK and BigQuery."

    parser = argparse.ArgumentParser(
        description="Register ADK Agent Engine agents with Gemini Enterprise."
    )
    parser.add_argument(
        "--reasoning-engine",
        default=default_reasoning_engine,
        help="Reasoning Engine resource name or ID (default: SEMANTIC_REASONING_ENGINE_ID)",
    )
    parser.add_argument(
        "--display-name",
        default="Semantic Analytics Agent",
        help="Display name for the agent (default: 'Semantic Analytics Agent')",
    )
    parser.add_argument(
        "--description",
        default=default_description,
        help="Description of the agent",
    )
    parser.add_argument(
        "--auth-id",
        default=default_auth_id,
        help=f"Authorization resource ID (default: {default_auth_id})",
    )

    args = parser.parse_args()

    project_id = os.getenv("GOOGLE_CLOUD_PROJECT")
    project_number = os.getenv("GOOGLE_CLOUD_PROJECT_NUMBER")
    app_id = os.getenv("GEMINI_APP_ID")
    ge_location = os.getenv("GEMINI_APP_LOCATION", "global")

    missing = [
        name
        for name, value in (
            ("GOOGLE_CLOUD_PROJECT", project_id),
            ("GOOGLE_CLOUD_PROJECT_NUMBER", project_number),
            ("GEMINI_APP_ID", app_id),
        )
        if not value
    ]
    if missing:
        parser.error(f"Missing required environment variables: {', '.join(missing)}")

    reasoning_engine = (args.reasoning_engine or "").strip()
    if not reasoning_engine:
        parser.error(
            "Reasoning engine must be specified via --reasoning-engine or SEMANTIC_REASONING_ENGINE_ID"
        )

    if "/" not in reasoning_engine:
        agent_engine_location = os.getenv("AGENT_ENGINE_LOCATION", "us-central1")
        reasoning_engine = (
            f"projects/{project_id}/locations/{agent_engine_location}/reasoningEngines/{reasoning_engine}"
        )

    auth_resource = None
    if args.auth_id:
        auth_resource = (
            f"projects/{project_number}/locations/{ge_location}/authorizations/{args.auth_id}"
        )

    register_agent(
        display_name=args.display_name,
        description=args.description,
        reasoning_engine_resource=reasoning_engine,
        auth_resource=auth_resource,
        project_id=project_id,  # type: ignore[arg-type]
        app_id=app_id,  # type: ignore[arg-type]
        ge_location=ge_location,
    )


if __name__ == "__main__":
    main()
