import os
import subprocess
import json
import logging
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT")
PROJECT_NUMBER = os.getenv("GOOGLE_CLOUD_PROJECT_NUMBER")
LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION", "global")
OAUTH_CLIENT_ID = os.getenv("OAUTH_CLIENT_ID")
OAUTH_CLIENT_SECRET = os.getenv("OAUTH_CLIENT_SECRET")

# Load Auth Resource IDs from environment
AUTH_ID_ORDERS = os.getenv("AUTH_RESOURCE_ORDERS", "bq-caapi-oauth")
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
        f"https://{LOCATION}-discoveryengine.googleapis.com/v1alpha/"
        f"projects/{PROJECT_NUMBER}/locations/{LOCATION}/authorizations?authorizationId={auth_id}"
    )

    payload = {
        "name": f"projects/{PROJECT_NUMBER}/locations/{LOCATION}/authorizations/{auth_id}",
        "serverSideOauth2": {
            "clientId": OAUTH_CLIENT_ID,
            "clientSecret": OAUTH_CLIENT_SECRET,
            "authorizationUri": "https://accounts.google.com/o/oauth2/v2/auth?client_id="
            + OAUTH_CLIENT_ID
            + "&redirect_uri=https%3A%2F%2Fvertexaisearch.cloud.google.com%2Foauth-redirect&scope=https%3A%2F%2Fwww.googleapis.com%2Fauth%2Fcloud-platform&include_granted_scopes=true&response_type=code&access_type=offline&prompt=consent",
            "tokenUri": "https://oauth2.googleapis.com/token",
        },
    }

    try:
        token = (
            subprocess.check_output(["gcloud", "auth", "print-access-token"])
            .decode()
            .strip()
        )
    except Exception as e:
        logger.error("Failed to get token: %s", e)
        return

    cmd = [
        "curl",
        "-s",
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
        logger.info("Response for %s: %s", auth_id, result.stdout)
    else:
        logger.error("Failed to create %s: %s", auth_id, result.stderr)


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
