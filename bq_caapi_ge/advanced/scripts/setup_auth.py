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

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT")
PROJECT_NUMBER = os.getenv("GOOGLE_CLOUD_PROJECT_NUMBER")
GE_LOCATION = os.getenv("GEMINI_APP_LOCATION", "global")
OAUTH_CLIENT_ID = os.getenv("OAUTH_CLIENT_ID")
OAUTH_CLIENT_SECRET = os.getenv("OAUTH_CLIENT_SECRET")

# Load Auth Resource IDs from environment
AUTH_ID_ORDERS = os.getenv("AUTH_RESOURCE_ORDERS", "bq-caapi-oauth-orders")
AUTH_ID_INVENTORY = os.getenv("AUTH_RESOURCE_INVENTORY", "bq-caapi-oauth-inventory")


def create_auth_resource(auth_id: str) -> None:
    """Create an OAuth authorization resource in Gemini Enterprise.

    Args:
        auth_id: The authorization resource ID to create.

    Raises:
        ValueError: If required OAuth or project configuration is not set.
    """
    if not OAUTH_CLIENT_ID or not OAUTH_CLIENT_SECRET:
        raise ValueError("OAUTH_CLIENT_ID and OAUTH_CLIENT_SECRET must be set")
    if not PROJECT_NUMBER:
        raise ValueError("GOOGLE_CLOUD_PROJECT_NUMBER must be set")

    logger.info("Creating Authorization Resource: %s...", auth_id)

    # Authorization resources are addressed by project number so the reference
    # built by register_agents.py resolves to the resource created here.
    url = (
        f"https://{GE_LOCATION}-discoveryengine.googleapis.com/v1alpha/"
        f"projects/{PROJECT_NUMBER}/locations/{GE_LOCATION}/authorizations?authorizationId={auth_id}"
    )

    payload = {
        "name": f"projects/{PROJECT_NUMBER}/locations/{GE_LOCATION}/authorizations/{auth_id}",
        "serverSideOauth2": {
            "clientId": OAUTH_CLIENT_ID,
            "clientSecret": OAUTH_CLIENT_SECRET,
            "authorizationUri": "https://accounts.google.com/o/oauth2/v2/auth?client_id="
            + OAUTH_CLIENT_ID
            + "&redirect_uri=https%3A%2F%2Fvertexaisearch.cloud.google.com%2Foauth-redirect&scope=https%3A%2F%2Fwww.googleapis.com%2Fauth%2Fcloud-platform&include_granted_scopes=true&response_type=code&access_type=offline&prompt=consent",
            "tokenUri": "https://oauth2.googleapis.com/token",
        },
    }

    token = get_gcloud_or_adc_access_token()

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


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Create OAuth authorization resources for Gemini Enterprise."
    )
    parser.add_argument(
        "--orders-only",
        action="store_true",
        help="Only create authorization for Orders agent",
    )
    parser.add_argument(
        "--inventory-only",
        action="store_true",
        help="Only create authorization for Inventory agent",
    )

    args = parser.parse_args()

    if args.orders_only:
        create_auth_resource(AUTH_ID_ORDERS)
    elif args.inventory_only:
        create_auth_resource(AUTH_ID_INVENTORY)
    else:
        # Default: create both
        create_auth_resource(AUTH_ID_ORDERS)
        create_auth_resource(AUTH_ID_INVENTORY)
