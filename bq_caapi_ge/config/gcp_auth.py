"""GCP authentication helpers for CLI scripts and agent registration.

Provides access token retrieval using Application Default Credentials (ADC)
with fallback to the user's gcloud CLI credentials.
"""

from __future__ import annotations

import logging
import subprocess

logger = logging.getLogger(__name__)


def get_gcloud_or_adc_access_token() -> str:
    """Retrieve an access token via ADC or gcloud CLI fallback.

    Tries Application Default Credentials (google.auth.default) first, falling
    back to the user gcloud auth print-access-token CLI.
    """
    try:
        import google.auth
        import google.auth.exceptions
        import google.auth.transport.requests
    except ImportError as e:
        logger.debug("google-auth not installed, falling back to gcloud CLI: %s", e)
    else:
        try:
            credentials, _ = google.auth.default(
                scopes=["https://www.googleapis.com/auth/cloud-platform"]
            )
            request = google.auth.transport.requests.Request()
            credentials.refresh(request)
            if credentials.token:
                return credentials.token.strip()
        except (google.auth.exceptions.GoogleAuthError, OSError) as e:
            logger.debug("ADC token lookup failed, falling back to gcloud CLI: %s", e)

    try:
        result = subprocess.run(
            ["gcloud", "auth", "print-access-token"],
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError as e:
        raise RuntimeError(
            "Neither Application Default Credentials nor the gcloud CLI is available"
        ) from e

    if result.returncode != 0:
        detail = result.stderr.strip() or f"exit status {result.returncode}"
        raise RuntimeError(f"gcloud auth print-access-token failed: {detail}")

    lines = [
        ln.strip()
        for ln in result.stdout.splitlines()
        if ln.strip() and not ln.startswith("Created ")
    ]
    if not lines:
        raise RuntimeError("gcloud returned an empty access token")
    return lines[-1]
