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

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_auth_resource(auth_id: str) -> None:
    """Create an OAuth authorization resource in Gemini Enterprise.

    Args:
        auth_id: The authorization resource ID to create.

    Raises:
        ValueError: If required OAuth or project configuration is not set.
    """
    project_id = os.getenv("GOOGLE_CLOUD_PROJECT")
    project_number = os.getenv("GOOGLE_CLOUD_PROJECT_NUMBER")
    ge_location = os.getenv("GEMINI_APP_LOCATION", "global")
    oauth_client_id = os.getenv("OAUTH_CLIENT_ID")
    oauth_client_secret = os.getenv("OAUTH_CLIENT_SECRET")

    if not oauth_client_id or not oauth_client_secret:
        raise ValueError("OAUTH_CLIENT_ID and OAUTH_CLIENT_SECRET must be set")
    if not project_number:
        raise ValueError("GOOGLE_CLOUD_PROJECT_NUMBER must be set")

    logger.info("Creating Authorization Resource: %s...", auth_id)

    # Authorization resources are addressed by project number so the reference
    # built by register_agents.py resolves to the resource created here.
    url = (
        f"https://{ge_location}-discoveryengine.googleapis.com/v1alpha/"
        f"projects/{project_number}/locations/{ge_location}/authorizations?authorizationId={auth_id}"
    )

    payload = {
        "name": f"projects/{project_number}/locations/{ge_location}/authorizations/{auth_id}",
        "serverSideOauth2": {
            "clientId": oauth_client_id,
            "clientSecret": oauth_client_secret,
            "authorizationUri": (
                "https://accounts.google.com/o/oauth2/v2/auth?client_id="
                + oauth_client_id
                + "&redirect_uri=https%3A%2F%2Fvertexaisearch.cloud.google.com%2Foauth-redirect"
                "&scope=https%3A%2F%2Fwww.googleapis.com%2Fauth%2Fcloud-platform"
                "&include_granted_scopes=true&response_type=code&access_type=offline&prompt=consent"
            ),
            "tokenUri": "https://oauth2.googleapis.com/token",
        },
    }

    token = get_gcloud_or_adc_access_token()

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
            logger.info("Response for %s: %s", auth_id, resp_body)
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8")
        try:
            err_json = json.loads(err_body)
            err_msg = err_json.get("error", {}).get("message", err_body)
        except json.JSONDecodeError:
            err_msg = err_body
        logger.error("Failed to create %s (%s): %s", auth_id, e.code, err_msg)
    except Exception as e:
        logger.error("Failed to create %s: %s", auth_id, e)


def main() -> None:
    default_auth_id = os.getenv("AUTH_RESOURCE_SEMANTIC_ANALYTICS", "bq-caapi-oauth-semantic")

    parser = argparse.ArgumentParser(
        description="Create OAuth authorization resource for Gemini Enterprise."
    )
    parser.add_argument(
        "--auth-id",
        default=default_auth_id,
        help=f"Authorization resource ID to create (default: {default_auth_id})",
    )

    args = parser.parse_args()
    create_auth_resource(args.auth_id)


if __name__ == "__main__":
    main()
