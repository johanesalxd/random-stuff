"""Register CA API data agents as A2A agents in Gemini Enterprise.

Fetches the A2A agent card directly from the Conversational Analytics API
(getCard endpoint) and submits it to the Gemini Enterprise Discovery Engine
API. No manual card construction -- the CA API owns the agent card format.

Usage::

    export GOOGLE_CLOUD_PROJECT=your-project-id
    export GEMINI_APP_ID=your-ge-app-id
    export OAUTH_CLIENT_ID=your-oauth-client-id
    export OAUTH_CLIENT_SECRET=your-oauth-client-secret

    # Register specific agents with unique auth resources
    uv run python scripts/register_ge_agents.py \\
        --agents campaign_monitor marketing_analyst \\
        --auth-ids auth-campaign auth-marketing

    # List agents registered in the GE app
    uv run python scripts/register_ge_agents.py --list

    # Delete an agent from GE by its GE agent ID
    uv run python scripts/register_ge_agents.py --delete 882487484595163651
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

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config.ca_locations import ca_api_endpoint  # noqa: E402

load_dotenv(override=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT")
PROJECT_NUMBER = os.getenv("GOOGLE_CLOUD_PROJECT_NUMBER")
# The data agent's location (where the CA API resource lives) and the Gemini
# Enterprise app's location are independent: a regional agent is routinely
# registered into a global GE app.
CA_LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION", "global")
GE_LOCATION = os.getenv("GEMINI_APP_LOCATION", "global")
APP_ID = os.getenv("GEMINI_APP_ID")
OAUTH_CLIENT_ID = os.getenv("OAUTH_CLIENT_ID")
OAUTH_CLIENT_SECRET = os.getenv("OAUTH_CLIENT_SECRET")

CA_API_BASE = f"https://{ca_api_endpoint(CA_LOCATION)}"
DE_BASE = f"https://{GE_LOCATION}-discoveryengine.googleapis.com/v1alpha"


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
        method: HTTP method (GET, POST, PATCH, DELETE).
        url: Full request URL.
        token: Bearer access token.
        payload: Optional JSON payload for POST/PATCH requests.

    Returns:
        Parsed JSON response dict.

    Raises:
        RuntimeError: If the curl command fails or the response contains an error.
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
        # A successful DELETE returns an empty body, which is not valid JSON.
        data = json.loads(result.stdout or "{}")
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Invalid JSON response: {result.stdout[:200]}") from e

    if "error" in data:
        raise RuntimeError(
            f"API error {data['error'].get('code')}: {data['error'].get('message')}"
        )
    return data


def get_agent_card(agent_id: str, token: str) -> dict:
    """Fetch the A2A agent card from the CA API getCard endpoint.

    Args:
        agent_id: The CA API data agent ID.
        token: Bearer access token.

    Returns:
        Agent card dict as returned by the CA API.
    """
    url = (
        f"{CA_API_BASE}/v1beta/a2a/projects/{PROJECT_ID}/locations/{CA_LOCATION}"
        f"/dataAgents/{agent_id}/v1/card"
    )
    logger.info("Fetching agent card for: %s", agent_id)
    return _request("GET", url, token)


# Redundant in Gemini Enterprise: the agent is authenticated through
# ``authorizationConfig.agentAuthorization`` (the OAuth authorization resource),
# not through the card. The CA API began emitting these fields after mid-2026 in
# a shape GE's A2A validator rejects outright, so they are dropped rather than
# reshaped.
_STRIPPED_CARD_FIELDS = ("security", "securitySchemes")

# Gemini Enterprise freezes the agent card at registration time and negotiates
# A2A extensions from that snapshot. The CA API has since added extensions that
# make the negotiated request fail before it reaches the chat backend: the call
# is authenticated and audit-logged, then dropped without ever dispatching to
# ChatInternal, so the stream closes empty and GE's A2A client fails with
# "async generator raised StopAsyncIteration".
#
# Confirmed against the endpoint by activating extensions via X-A2A-Extensions:
#   a2ui/v0.9   the card advertises v0.8 *and* v0.9; activating both returns
#               400 "You provide multiple versions of the a2ui extension".
#               Unlike the "Input is required" errors -- which GE resolves by
#               supplying the input, as client-id/v1 and authorizations/v1 show
#               on working agents -- no caller-supplied input can resolve this.
#   model/v1    returns 400 "Input is required"; absent from working agents.
#   stateless/v1, sse/v1
#               absent from working agents.
#
# The agents registered before the CA API change carry a card without these and
# keep working, but they only re-read the card when re-registered -- so any
# re-registration without this cleanup would break a currently working agent.
_STRIPPED_EXTENSION_URIS = (
    "a2a-extension/a2ui/v0.9",
    "gemini-enterprise/a2a/extensions/model/v1",
    "conversational-analytics-api/reference/a2a/extensions/stateless/v1",
    "conversational-analytics-api/reference/a2a/extensions/sse/v1",
)


def normalize_agent_card(card: dict) -> dict:
    """Remove card declarations that break Gemini Enterprise A2A calls.

    Drops the redundant security declaration and the extensions that GE cannot
    negotiate. See ``_STRIPPED_CARD_FIELDS`` and ``_STRIPPED_EXTENSION_URIS``.

    Args:
        card: The agent card dict from the CA API.

    Returns:
        The same card dict, with the offending declarations removed.
    """
    for field in _STRIPPED_CARD_FIELDS:
        card.pop(field, None)

    capabilities = card.get("capabilities")
    if isinstance(capabilities, dict):
        extensions = capabilities.get("extensions")
        if isinstance(extensions, list):
            capabilities["extensions"] = [
                extension
                for extension in extensions
                if not any(
                    uri in extension.get("uri", "") for uri in _STRIPPED_EXTENSION_URIS
                )
            ]

    return card


def create_auth_resource(auth_id: str, token: str) -> None:
    """Create an OAuth authorization resource in Gemini Enterprise.

    Skips silently if the resource already exists.

    Args:
        auth_id: The authorization resource ID to create.
        token: Bearer access token.

    Raises:
        ValueError: If OAUTH_CLIENT_ID or OAUTH_CLIENT_SECRET is not set.
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
        name = agent.get("name", "")
        ge_id = name.split("/")[-1]
        display = agent.get("displayName", "")
        state = agent.get("state", "")
        if "a2aAgentDefinition" in agent:
            kind = "A2A"
        elif "adkAgentDefinition" in agent:
            kind = "ADK"
        else:
            kind = "builtin"
        logger.info("%-25s %-30s %-8s %s", ge_id, display, kind, state)


def register_agent(
    agent_id: str,
    token: str,
    auth_id: str | None = None,
    display_name: str | None = None,
    force: bool = False,
    share_scope: str | None = None,
) -> None:
    """Fetch agent card from CA API and register it in GE as an A2A agent.

    Args:
        agent_id: The CA API data agent ID.
        token: Bearer access token.
        auth_id: Optional authorization resource ID to attach.
        display_name: Optional display name override. Defaults to title-cased agent_id.
        force: If True, update (PATCH) if the agent already exists.
        share_scope: Sharing scope to apply (``ALL_USERS`` or ``RESTRICTED``).
            When None, an existing agent keeps its current scope.
    """
    card = normalize_agent_card(get_agent_card(agent_id, token))

    derived_display_name = display_name or agent_id.replace("_", " ").title()

    payload: dict = {
        "displayName": derived_display_name,
        "description": card.get("description", ""),
        "a2aAgentDefinition": {
            "jsonAgentCard": json.dumps(card),
        },
    }
    if auth_id:
        payload["authorizationConfig"] = {
            "agentAuthorization": (
                f"projects/{PROJECT_NUMBER}/locations/{GE_LOCATION}"
                f"/authorizations/{auth_id}"
            )
        }

    # Check if an agent with this display name already exists.
    existing = _find_existing_ge_agent(derived_display_name, token)

    if existing and not force:
        logger.info(
            "Agent '%s' already exists in GE (ID: %s). Use --force to update.",
            derived_display_name,
            existing["name"].split("/")[-1],
        )
        return

    if share_scope:
        payload["sharingConfig"] = {"scope": share_scope}
    elif existing and existing.get("sharingConfig"):
        # A PATCH without an update mask replaces the resource, so any field
        # omitted from the payload is cleared. Carry the current scope forward,
        # otherwise --force silently un-shares the agent and it disappears for
        # every non-admin user.
        payload["sharingConfig"] = existing["sharingConfig"]

    if existing and force:
        existing_id = existing["name"].split("/")[-1]
        url = f"{_ge_agents_url()}/{existing_id}"
        logger.info(
            "Updating existing GE agent: %s (ID: %s)", derived_display_name, existing_id
        )
        result = _request("PATCH", url, token, payload)
        logger.info(
            "Updated: %s (sharing: %s)",
            result.get("name"),
            result.get("sharingConfig", {}).get("scope", "unset"),
        )
    else:
        logger.info("Registering new GE agent: %s", derived_display_name)
        result = _request("POST", _ge_agents_url(), token, payload)
        logger.info(
            "Registered: %s (GE ID: %s, sharing: %s)",
            derived_display_name,
            result.get("name", "").split("/")[-1],
            result.get("sharingConfig", {}).get("scope", "unset"),
        )


def _find_existing_ge_agent(display_name: str, token: str) -> dict | None:
    """Return the GE agent resource with the given display name, if it exists.

    Args:
        display_name: Display name to search for.
        token: Bearer access token.

    Returns:
        The agent resource dict, or None if not found.
    """
    data = _request("GET", _ge_agents_url(), token)
    for agent in data.get("agents", []):
        if agent.get("displayName") == display_name:
            return agent
    return None


def delete_ge_agent(ge_agent_id: str, token: str) -> None:
    """Delete a registered agent from the GE app by its GE agent ID.

    Args:
        ge_agent_id: The GE agent ID (numeric string from --list output).
        token: Bearer access token.
    """
    url = f"{_ge_agents_url()}/{ge_agent_id}"
    logger.info("Deleting GE agent: %s", ge_agent_id)
    _request("DELETE", url, token)
    logger.info("Deleted GE agent: %s", ge_agent_id)


def main() -> None:
    """Parse arguments and execute the requested operation."""
    parser = argparse.ArgumentParser(
        description=(
            "Register CA API data agents as A2A agents in Gemini Enterprise. "
            "Fetches agent cards directly from the CA API getCard endpoint."
        )
    )

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--agents",
        nargs="+",
        metavar="AGENT_ID",
        help="CA API data agent IDs to register in GE.",
    )
    group.add_argument(
        "--list",
        action="store_true",
        help="List agents currently registered in the GE app.",
    )
    group.add_argument(
        "--delete",
        metavar="GE_AGENT_ID",
        help="Delete an agent from GE by its GE agent ID (from --list output).",
    )

    parser.add_argument(
        "--auth-ids",
        nargs="+",
        metavar="AUTH_ID",
        help=(
            "Authorization resource IDs to create and attach to the registered agents. "
            "Must provide exactly one auth-id per agent to satisfy the 1:1 GE mapping. "
            "Requires OAUTH_CLIENT_ID and OAUTH_CLIENT_SECRET to be set."
        ),
    )
    parser.add_argument(
        "--display-names",
        metavar="NAMES",
        help=(
            "Comma-separated display name overrides, matched positionally with --agents. "
            "Example: 'Series Analyst,Marketing Analyst,Campaign Monitor'"
        ),
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Update (PATCH) agents that already exist in GE instead of skipping.",
    )
    parser.add_argument(
        "--share",
        choices=["all-users", "restricted"],
        default=None,
        help=(
            "Sharing scope for the agents. 'all-users' makes them visible to "
            "every user of the GE app; 'restricted' limits them to their owner. "
            "Defaults to keeping the scope each agent already has."
        ),
    )

    args = parser.parse_args()

    if not PROJECT_ID:
        logger.error("GOOGLE_CLOUD_PROJECT is not set.")
        sys.exit(1)
    if not APP_ID and (args.agents or args.list or args.delete):
        logger.error("GEMINI_APP_ID is not set.")
        sys.exit(1)

    token = get_access_token()

    if args.list:
        list_ge_agents(token)
        return

    if args.delete:
        delete_ge_agent(args.delete, token)
        return

    # --agents flow
    display_names: list[str | None] = []
    if args.display_names:
        display_names = [n.strip() for n in args.display_names.split(",")]
        if len(display_names) != len(args.agents):
            logger.error(
                "--display-names count (%d) does not match --agents count (%d).",
                len(display_names),
                len(args.agents),
            )
            sys.exit(1)
    else:
        display_names = [None] * len(args.agents)

    auth_ids: list[str | None] = []
    if args.auth_ids:
        auth_ids = args.auth_ids
        if len(auth_ids) != len(args.agents):
            logger.error(
                "--auth-ids count (%d) does not match --agents count (%d).",
                len(auth_ids),
                len(args.agents),
            )
            sys.exit(1)
        for unique_auth_id in set(auth_ids):
            create_auth_resource(unique_auth_id, token)
    else:
        auth_ids = [None] * len(args.agents)

    share_scope = {"all-users": "ALL_USERS", "restricted": "RESTRICTED"}.get(args.share)

    for agent_id, display_name, auth_id in zip(args.agents, display_names, auth_ids):
        try:
            register_agent(
                agent_id=agent_id,
                token=token,
                auth_id=auth_id,
                display_name=display_name,
                force=args.force,
                share_scope=share_scope,
            )
        except RuntimeError as e:
            logger.error("Failed to register agent '%s': %s", agent_id, e)


if __name__ == "__main__":
    main()
