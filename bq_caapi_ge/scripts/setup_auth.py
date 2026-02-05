import os
import subprocess
import json
import logging
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT")
LOCATION = "global"
OAUTH_CLIENT_ID = os.getenv("OAUTH_CLIENT_ID")
OAUTH_CLIENT_SECRET = os.getenv("OAUTH_CLIENT_SECRET")

# Load Auth Resource IDs from environment
AUTH_ID_ORDERS = os.getenv("AUTH_RESOURCE_ORDERS", "bq-caapi-oauth")
AUTH_ID_INVENTORY = os.getenv("AUTH_RESOURCE_INVENTORY", "bq-caapi-oauth-inventory")


def create_auth_resource(auth_id: str):
    logger.info(f"Creating Authorization Resource: {auth_id}...")

    url = (
        f"https://{LOCATION}-discoveryengine.googleapis.com/v1alpha/"
        f"projects/{PROJECT_ID}/locations/{LOCATION}/authorizations?authorizationId={auth_id}"
    )

    payload = {
        "name": f"projects/{PROJECT_ID}/locations/{LOCATION}/authorizations/{auth_id}",
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
        logger.error(f"Failed to get token: {e}")
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
        logger.info(f"Response for {auth_id}: {result.stdout}")
    else:
        logger.error(f"Failed to create {auth_id}: {result.stderr}")


if __name__ == "__main__":
    create_auth_resource(AUTH_ID_ORDERS)
    create_auth_resource(AUTH_ID_INVENTORY)
