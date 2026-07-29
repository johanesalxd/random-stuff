"""Register the Froyo Lakehouse CA data agent in Gemini Enterprise.

Fetches the A2A agent card from the Conversational Analytics API ``getCard``
endpoint and registers it in the Gemini Enterprise (Discovery Engine) app,
optionally creating a per-agent OAuth authorization resource so queries run with
the signed-in user's BigQuery/BigLake identity.

Usage::

    # Register the agent and attach its OAuth authorization resource
    uv run python scripts/register_ge_agent.py

    # Override the agent id / auth id explicitly
    uv run python scripts/register_ge_agent.py \\
        --agent froyo_lakehouse_analyst --auth-id froyo-lakehouse-oauth --force

    # List agents registered in the GE app
    uv run python scripts/register_ge_agent.py --list

    # Delete an agent from GE by its GE agent id (from --list output)
    uv run python scripts/register_ge_agent.py --delete 882487484595163651
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv

_AGENT_ROOT = Path(__file__).resolve().parents[1]
_DEMO_CONFIG = _AGENT_ROOT.parent / "config.local.env"
_AGENT_ENV = _AGENT_ROOT / ".env"

if _DEMO_CONFIG.exists():
    load_dotenv(_DEMO_CONFIG, override=False)
if _AGENT_ENV.exists():
    load_dotenv(_AGENT_ENV, override=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

PROJECT_ID = os.getenv("GCP_PROJECT") or os.getenv("GOOGLE_CLOUD_PROJECT")
PROJECT_NUMBER = os.getenv("GOOGLE_CLOUD_PROJECT_NUMBER")
# CA_LOCATION is the CA API data-agent resource location (where the agent was
# created). GE_LOCATION is the Gemini Enterprise / Discovery Engine app location,
# which is independent and usually "global". Keeping them separate lets the CA
# agent run in a region (e.g. us-east4) while GE stays global.
CA_LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION", "global")
GE_LOCATION = os.getenv("GEMINI_APP_LOCATION", "global")
APP_ID = os.getenv("GEMINI_APP_ID")
OAUTH_CLIENT_ID = os.getenv("OAUTH_CLIENT_ID")
OAUTH_CLIENT_SECRET = os.getenv("OAUTH_CLIENT_SECRET")

DEFAULT_AGENT_ID = os.getenv("AGENT_ID", "froyo_lakehouse_analyst")
DEFAULT_AUTH_ID = os.getenv("AUTH_RESOURCE", "froyo-lakehouse-oauth")

DE_BASE = f"https://{GE_LOCATION}-discoveryengine.googleapis.com/v1alpha"


def ca_api_base(location: str) -> str:
    """Return the CA API base URL for the given resource location.

    Args:
        location: CA API resource location (``global``, a region like
            ``us-east4``, or a multi-region like ``us``).

    Returns:
        The matching CA API base URL.
    """
    if not location or location == "global":
        return "https://geminidataanalytics.googleapis.com"
    if "-" in location:
        return f"https://geminidataanalytics-{location}.googleapis.com"
    return f"https://geminidataanalytics.{location}.rep.googleapis.com"


def get_access_token() -> str:
    """Get an access token via Application Default Credentials.

    Returns:
        Bearer token string.

    Raises:
        RuntimeError: If the token cannot be retrieved.
    """
    result = subprocess.run(
        ["gcloud", "auth", "application-default", "print-access-token"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Failed to get access token: {result.stderr.strip()}")
    return result.stdout.strip()


def _request(
    method: str,
    url: str,
    token: str,
    payload: dict | None = None,
) -> dict:
    """Execute an authenticated HTTP request via curl.

    Args:
        method: HTTP method.
        url: Full request URL.
        token: Bearer access token.
        payload: Optional JSON payload.

    Returns:
        Parsed JSON response.

    Raises:
        RuntimeError: If curl fails or the API returns an error.
    """
    cmd = [
        "curl",
        "-s",
        "-X",
        method,
        "-H",
        f"Authorization: Bearer {token}",
        "-H",
        "Content-Type: application/json",
        "-H",
        f"X-Goog-User-Project: {PROJECT_ID}",
        url,
    ]
    if payload is not None:
        cmd += ["-d", json.dumps(payload)]

    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(f"curl failed: {result.stderr.strip()}")

    try:
        data = json.loads(result.stdout or "{}")
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Invalid JSON response: {result.stdout[:200]}") from e

    if "error" in data:
        raise RuntimeError(
            f"API error {data['error'].get('code')}: {data['error'].get('message')}"
        )
    return data


def get_agent_card(agent_id: str, token: str) -> dict:
    """Fetch the A2A agent card from the CA API ``getCard`` endpoint.

    Args:
        agent_id: The CA API data agent id.
        token: Bearer access token.

    Returns:
        The agent card dict as returned by the CA API.
    """
    url = (
        f"{ca_api_base(CA_LOCATION)}/v1beta/a2a/projects/{PROJECT_ID}"
        f"/locations/{CA_LOCATION}/dataAgents/{agent_id}/v1/card"
    )
    logger.info("Fetching agent card for: %s", agent_id)
    return _request("GET", url, token)


def create_auth_resource(auth_id: str, token: str) -> None:
    """Create an OAuth authorization resource in Gemini Enterprise.

    Skips silently if the resource already exists.

    Args:
        auth_id: The authorization resource id to create.
        token: Bearer access token.

    Raises:
        ValueError: If OAuth client credentials are not set.
    """
    if not OAUTH_CLIENT_ID or not OAUTH_CLIENT_SECRET:
        raise ValueError(
            "OAUTH_CLIENT_ID and OAUTH_CLIENT_SECRET must be set to create an "
            "authorization resource."
        )

    auth_uri = (
        "https://accounts.google.com/o/oauth2/v2/auth"
        f"?client_id={OAUTH_CLIENT_ID}"
        "&redirect_uri=https%3A%2F%2Fvertexaisearch.cloud.google.com%2Fstatic%2Foauth%2Foauth.html"
        "&scope=https%3A%2F%2Fwww.googleapis.com%2Fauth%2Fcloud-platform"
        "&include_granted_scopes=true"
        "&response_type=code"
        "&access_type=offline"
        "&prompt=consent"
    )

    url = (
        f"{DE_BASE}/projects/{PROJECT_ID}/locations/{GE_LOCATION}"
        f"/authorizations?authorizationId={auth_id}"
    )
    payload = {
        "name": (
            f"projects/{PROJECT_ID}/locations/{GE_LOCATION}/authorizations/{auth_id}"
        ),
        "serverSideOauth2": {
            "clientId": OAUTH_CLIENT_ID,
            "clientSecret": OAUTH_CLIENT_SECRET,
            "authorizationUri": auth_uri,
            "tokenUri": "https://oauth2.googleapis.com/token",
        },
    }

    logger.info("Creating authorization resource: %s", auth_id)
    try:
        _request("POST", url, token, payload)
        logger.info("Authorization resource created: %s", auth_id)
    except RuntimeError as e:
        if "already exists" in str(e).lower():
            logger.info("Authorization resource already exists, skipping: %s", auth_id)
        else:
            raise


def _ge_agents_url() -> str:
    """Return the Discovery Engine agents endpoint URL."""
    return (
        f"{DE_BASE}/projects/{PROJECT_ID}/locations/{GE_LOCATION}"
        f"/collections/default_collection/engines/{APP_ID}"
        "/assistants/default_assistant/agents"
    )


def list_ge_agents(token: str) -> None:
    """List all agents registered in the GE app.

    Args:
        token: Bearer access token.
    """
    data = _request("GET", _ge_agents_url(), token)
    agents = data.get("agents", [])
    if not agents:
        logger.info("No agents registered in app: %s", APP_ID)
        return

    header = f"{'GE Agent ID':<25} {'Display Name':<30} {'Type':<8} {'State'}"
    logger.info("\n%s\n%s", header, "-" * 80)
    for agent in agents:
        ge_id = agent.get("name", "").split("/")[-1]
        display = agent.get("displayName", "")
        state = agent.get("state", "")
        if "a2aAgentDefinition" in agent:
            kind = "A2A"
        elif "adkAgentDefinition" in agent:
            kind = "ADK"
        else:
            kind = "builtin"
        logger.info("%-25s %-30s %-8s %s", ge_id, display, kind, state)


def _find_existing_ge_agent(display_name: str, token: str) -> str | None:
    """Return the GE agent id if one with the given display name exists.

    Args:
        display_name: Display name to search for.
        token: Bearer access token.

    Returns:
        GE agent id string, or None if not found.
    """
    data = _request("GET", _ge_agents_url(), token)
    for agent in data.get("agents", []):
        if agent.get("displayName") == display_name:
            return agent["name"].split("/")[-1]
    return None


def register_agent(
    agent_id: str,
    token: str,
    auth_id: str | None,
    display_name: str | None,
    force: bool,
) -> None:
    """Fetch the agent card and register (or update) it in GE as an A2A agent.

    Args:
        agent_id: The CA API data agent id.
        token: Bearer access token.
        auth_id: Optional authorization resource id to attach.
        display_name: Optional display name override.
        force: If True, update (PATCH) when the agent already exists.
    """
    card = get_agent_card(agent_id, token)
    derived_display_name = display_name or agent_id.replace("_", " ").title()

    payload: dict = {
        "displayName": derived_display_name,
        "description": card.get("description", ""),
        "a2aAgentDefinition": {"jsonAgentCard": json.dumps(card)},
    }
    if auth_id:
        payload["authorizationConfig"] = {
            "agentAuthorization": (
                f"projects/{PROJECT_NUMBER}/locations/{GE_LOCATION}"
                f"/authorizations/{auth_id}"
            )
        }

    existing_id = _find_existing_ge_agent(derived_display_name, token)

    if existing_id and not force:
        logger.info(
            "Agent '%s' already exists in GE (id: %s). Use --force to update.",
            derived_display_name,
            existing_id,
        )
        return

    if existing_id and force:
        url = f"{_ge_agents_url()}/{existing_id}"
        logger.info("Updating GE agent: %s (id: %s)", derived_display_name, existing_id)
        result = _request("PATCH", url, token, payload)
        logger.info("Updated: %s", result.get("name"))
    else:
        logger.info("Registering new GE agent: %s", derived_display_name)
        result = _request("POST", _ge_agents_url(), token, payload)
        ge_id = result.get("name", "").split("/")[-1]
        logger.info("Registered: %s (GE id: %s)", derived_display_name, ge_id)


def delete_ge_agent(ge_agent_id: str, token: str) -> None:
    """Delete a registered agent from the GE app by its GE agent id.

    Args:
        ge_agent_id: The GE agent id (numeric string from ``--list``).
        token: Bearer access token.
    """
    url = f"{_ge_agents_url()}/{ge_agent_id}"
    logger.info("Deleting GE agent: %s", ge_agent_id)
    _request("DELETE", url, token)
    logger.info("Deleted GE agent: %s", ge_agent_id)


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments.

    Returns:
        Parsed arguments.
    """
    parser = argparse.ArgumentParser(
        description=(
            "Register the Froyo Lakehouse CA data agent in Gemini Enterprise via "
            "the A2A agent card."
        )
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--list", action="store_true", help="List GE-registered agents.")
    group.add_argument(
        "--delete",
        metavar="GE_AGENT_ID",
        help="Delete an agent from GE by its GE agent id (from --list).",
    )

    parser.add_argument(
        "--agent",
        default=DEFAULT_AGENT_ID,
        help="CA API data agent id to register (default from AGENT_ID).",
    )
    parser.add_argument(
        "--auth-id",
        default=DEFAULT_AUTH_ID,
        help="Authorization resource id to create/attach (default from AUTH_RESOURCE).",
    )
    parser.add_argument(
        "--display-name",
        default=None,
        help="Display name override. Defaults to a title-cased agent id.",
    )
    parser.add_argument(
        "--no-auth",
        action="store_true",
        help="Register without creating/attaching an OAuth authorization resource.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Update (PATCH) the agent if it already exists in GE.",
    )
    return parser.parse_args()


def main() -> None:
    """Parse arguments and execute the requested GE operation."""
    args = parse_args()

    if not PROJECT_ID:
        logger.error("GCP_PROJECT is not set.")
        sys.exit(1)

    token = get_access_token()

    if args.list:
        if not APP_ID:
            logger.error("GEMINI_APP_ID is not set.")
            sys.exit(1)
        list_ge_agents(token)
        return

    if args.delete:
        if not APP_ID:
            logger.error("GEMINI_APP_ID is not set.")
            sys.exit(1)
        delete_ge_agent(args.delete, token)
        return

    if not APP_ID:
        logger.error("GEMINI_APP_ID is not set.")
        sys.exit(1)

    auth_id = None if args.no_auth else args.auth_id
    if auth_id:
        if not PROJECT_NUMBER:
            logger.error(
                "GOOGLE_CLOUD_PROJECT_NUMBER is required to attach an auth resource."
            )
            sys.exit(1)
        create_auth_resource(auth_id, token)

    try:
        register_agent(
            agent_id=args.agent,
            token=token,
            auth_id=auth_id,
            display_name=args.display_name,
            force=args.force,
        )
    except RuntimeError as e:
        logger.error("Failed to register agent '%s': %s", args.agent, e)
        sys.exit(1)


if __name__ == "__main__":
    main()
