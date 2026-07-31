"""Test web app for OAuth passthrough to Conversational Analytics API.

This is a development harness, not a production identity service.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
import logging
import os
import secrets
from typing import Any

import requests
from dotenv import load_dotenv
from flask import Flask, redirect, render_template, request, session, url_for
from google_auth_oauthlib.flow import Flow

# Load environment configs from the Froyo Lakehouse pipeline and agent environments
_ROOT = os.path.dirname(__file__)
load_dotenv(os.path.join(_ROOT, "..", "config.local.env"), override=False)
load_dotenv(os.path.join(_ROOT, "..", "agent", ".env"), override=True)
load_dotenv(os.path.join(_ROOT, ".env"), override=True)

logger = logging.getLogger(__name__)


def env_flag(name: str, default: str = "0") -> bool:
    """Reads an environment variable as a boolean flag.

    Args:
        name: Environment variable name.
        default: Value assumed when the variable is unset.

    Returns:
        True when the value is one of ``1``, ``true``, ``yes`` or ``on``
        (case-insensitive).
    """
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


app = Flask(__name__)

# A stable secret keeps signed session cookies valid across restarts. An ephemeral
# secret is only acceptable for throwaway local runs and logs a warning.
_secret = os.getenv("FLASK_SECRET_KEY")
if not _secret:
    _secret = secrets.token_hex(32)
    logger.warning(
        "FLASK_SECRET_KEY is not set; using an ephemeral secret. "
        "Sessions will not survive a restart."
    )
app.secret_key = _secret
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=env_flag("COOKIE_SECURE"),
)

# Allow OAuth scope changes (Google may add scopes like bigquery)
os.environ["OAUTHLIB_RELAX_TOKEN_SCOPE"] = "1"

# Configuration
CLIENT_ID = os.getenv("OAUTH_CLIENT_ID")
CLIENT_SECRET = os.getenv("OAUTH_CLIENT_SECRET")
PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT") or os.getenv("GCP_PROJECT")

# Live CA API configuration
AGENT_ID = os.getenv("AGENT_ID", "froyo_lakehouse_analyst")
GOOGLE_CLOUD_LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION", "global")

# Mock sign-in bypasses OAuth entirely and must never be enabled on a deployed,
# publicly reachable service. It exists only for offline UI work.
ALLOW_MOCK_LOGIN = env_flag("ALLOW_MOCK_LOGIN")

# Route Conversational Analytics calls through the service's own Application
# Default Credentials instead of the signed-in user's token. This discards
# per-user authorization, so it is refused unless explicitly acknowledged.
USE_ADC_FOR_API = env_flag("USE_ADC_FOR_API")

SCOPES = [
    "https://www.googleapis.com/auth/cloud-platform",
    "https://www.googleapis.com/auth/userinfo.email",
    "openid",
]

# Must match an Authorized Redirect URI on the OAuth client. On Cloud Run this
# has to be the deployed service URL, not localhost.
REDIRECT_URI = os.getenv("OAUTH_REDIRECT_URI", "http://localhost:8080/auth/callback")

_SESSIONS: dict[str, dict[str, Any]] = {}

if ALLOW_MOCK_LOGIN:
    logger.warning(
        "ALLOW_MOCK_LOGIN is enabled; anyone reaching this service can sign in "
        "without credentials. Use only for local development."
    )
if USE_ADC_FOR_API and not ALLOW_MOCK_LOGIN:
    logger.warning(
        "USE_ADC_FOR_API is enabled; Conversational Analytics queries run as the "
        "service identity rather than the signed-in user."
    )
if ALLOW_MOCK_LOGIN and USE_ADC_FOR_API:
    raise RuntimeError(
        "ALLOW_MOCK_LOGIN and USE_ADC_FOR_API must not be enabled together: "
        "unauthenticated callers would query BigQuery as the service identity."
    )


def validate_oauth_state(expected: str | None, received: str | None) -> bool:
    """Compares the stored and returned OAuth state values in constant time.

    Args:
        expected: State value generated when the flow started.
        received: State value echoed back on the callback.

    Returns:
        True when both are present and equal.
    """
    if not expected or not received:
        return False
    return secrets.compare_digest(str(expected), str(received))


def is_token_expired(
    expiry_iso: str | None, *, now: datetime | None = None, skew_seconds: int = 60
) -> bool:
    """Reports whether an ISO-8601 expiry has passed, allowing for clock skew.

    Args:
        expiry_iso: Token expiry timestamp, or None when unknown.
        now: Current time; defaults to the current UTC time.
        skew_seconds: Treat the token as expired this many seconds early.

    Returns:
        True when the token is missing, unparseable, or within the skew window.
    """
    if not expiry_iso:
        return True
    try:
        expiry = datetime.fromisoformat(expiry_iso)
    except ValueError:
        return True
    if expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=timezone.utc)
    current = now or datetime.now(timezone.utc)
    return (expiry - current).total_seconds() <= skew_seconds


# --- server-side session helpers -------------------------------------------


def _session_data() -> dict[str, Any]:
    sid = session.get("sid")
    if not sid or sid not in _SESSIONS:
        return {}
    return _SESSIONS[sid]


def _new_session() -> dict[str, Any]:
    sid = secrets.token_urlsafe(32)
    session["sid"] = sid
    _SESSIONS[sid] = {}
    return _SESSIONS[sid]


def _clear_session() -> None:
    sid = session.get("sid")
    if sid:
        _SESSIONS.pop(sid, None)
    session.clear()


def _credentials_from_store(data: dict[str, Any]) -> Any:
    from google.oauth2.credentials import Credentials

    return Credentials(
        token=data.get("access_token"),
        refresh_token=data.get("refresh_token"),
        token_uri="https://oauth2.googleapis.com/token",
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        scopes=SCOPES,
    )


def _ensure_valid_token(data: dict[str, Any]) -> tuple[str | None, str | None]:
    if data.get("access_token") == "mock-access-token":
        return "mock-access-token", None
    if not is_token_expired(data.get("token_expiry")):
        return data.get("access_token"), None
    if not data.get("refresh_token"):
        return None, "session expired; please sign in again"
    try:
        from google.auth.transport.requests import Request

        credentials = _credentials_from_store(data)
        credentials.refresh(Request())
    except Exception as error:
        return None, f"token refresh failed; please sign in again: {error}"
    data["access_token"] = credentials.token
    data["token_expiry"] = (
        credentials.expiry.replace(tzinfo=timezone.utc).isoformat()
        if credentials.expiry
        else None
    )
    return credentials.token, None


def _query_ca_api(message: str, access_token: str) -> Any:
    """Sends a question to the Conversational Analytics API and folds the stream.

    Args:
        message: The user's natural-language question.
        access_token: Bearer token used for the call. This is the signed-in
            user's OAuth token unless USE_ADC_FOR_API is enabled.

    Returns:
        A response body dict, or a ``(body, status)`` tuple on failure.
    """
    location = GOOGLE_CLOUD_LOCATION
    project_id = PROJECT_ID
    agent_id = AGENT_ID

    if not location or location == "global":
        base_url = "https://geminidataanalytics.googleapis.com"
    elif "-" in location:
        base_url = f"https://geminidataanalytics-{location}.googleapis.com"
    else:
        base_url = f"https://geminidataanalytics.{location}.rep.googleapis.com"

    chat_url = f"{base_url}/v1beta/projects/{project_id}/locations/{location}:chat"
    data_agent_name = (
        f"projects/{project_id}/locations/{location}/dataAgents/{agent_id}"
    )

    if USE_ADC_FOR_API:
        try:
            import google.auth
            import google.auth.transport.requests

            credentials, _ = google.auth.default(
                scopes=["https://www.googleapis.com/auth/cloud-platform"]
            )
            credentials.refresh(google.auth.transport.requests.Request())
            api_token = credentials.token
        except Exception:
            logger.exception("Failed to obtain an ADC token")
            api_token = access_token
    else:
        api_token = access_token

    headers = {
        "Authorization": f"Bearer {api_token}",
        "Content-Type": "application/json",
    }
    payload = {
        "messages": [{"userMessage": {"text": message}}],
        "dataAgentContext": {"dataAgent": data_agent_name},
    }

    try:
        response = requests.post(
            chat_url, json=payload, headers=headers, stream=True, timeout=120
        )
    except requests.exceptions.RequestException as e:
        return {"error": f"Failed to connect to Conversational Analytics API: {e}"}, 500

    if response.status_code != 200:
        logger.error("Conversational Analytics API returned %s", response.status_code)
        return {
            "error": (
                f"Conversational Analytics API failed "
                f"({response.status_code}): {response.text}"
            )
        }, 500

    accumulated_text = ""
    generated_sql = ""
    rows_returned = 0
    raw_rows = []
    vega_config = None
    executed = False

    accumulator = ""
    for line in response.iter_lines():
        if not line:
            continue
        decoded = line.decode("utf-8")
        if decoded == "[{":
            accumulator = "{"
        elif decoded == "}]":
            accumulator += "}"
        elif decoded == ",":
            continue
        else:
            accumulator += decoded

        try:
            data_json = json.loads(accumulator)
        except ValueError:
            continue

        if "error" in data_json:
            return {"error": f"API streamed error: {data_json['error']}"}, 500

        msg = data_json.get("systemMessage")
        if not msg:
            accumulator = ""
            continue

        if "text" in msg:
            text_block = msg["text"]
            text_type = text_block.get("textType") or text_block.get("text_type")
            if text_type in ("THOUGHT", 2, "PROGRESS", 3):
                # Skip thinking and progress logs from being appended to the response
                pass
            else:
                parts = text_block.get("parts", [])
                accumulated_text += "".join(parts)

        if "data" in msg:
            data_block = msg["data"]
            if "generatedSql" in data_block:
                generated_sql = data_block["generatedSql"]
            if "result" in data_block:
                raw_rows = data_block["result"].get("data", [])
                rows_returned = len(raw_rows)
                executed = True

        if "chart" in msg:
            chart_block = msg["chart"]
            if "vegaConfig" in chart_block:
                vega_config = chart_block["vegaConfig"]
            elif "vega_config" in chart_block:
                vega_config = chart_block["vega_config"]

        accumulator = ""

    if raw_rows:
        final_response = json.dumps(raw_rows)
    else:
        final_response = accumulated_text

    # Report what the stream actually contained rather than assuming success:
    # the agent may answer from context without emitting SQL, or emit SQL that
    # never produced a result block.
    if executed:
        status = "SUCCESS"
    elif generated_sql:
        status = "NO_RESULT"
    else:
        status = "NO_SQL"

    provenance = {
        "status": status,
        "catalog_route": "Conversational Analytics Route",
        "sql": generated_sql,
        "dry_run": False,
        "execution": {"rows_returned": rows_returned} if executed else None,
    }

    return {
        "response": final_response,
        "vega_config": vega_config,
        "provenance": provenance,
        "session_id": "live-ca-session",
        "runtime_mode": "live_ca_api",
        "app_name": agent_id,
    }


def get_oauth_flow():
    """Builds the Google OAuth authorization-code flow for this app."""
    client_config = {
        "web": {
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [REDIRECT_URI],
        }
    }
    return Flow.from_client_config(
        client_config, scopes=SCOPES, redirect_uri=REDIRECT_URI
    )


@app.route("/")
def index():
    """Renders the landing page, or redirects an authenticated user to chat."""
    if _session_data().get("access_token"):
        return redirect(url_for("chat"))
    return render_template("index.html")


@app.route("/auth/login")
def login():
    """Starts the OAuth authorization-code flow."""
    if not CLIENT_ID or not CLIENT_SECRET:
        if not ALLOW_MOCK_LOGIN:
            logger.error(
                "OAUTH_CLIENT_ID/OAUTH_CLIENT_SECRET are not configured and "
                "ALLOW_MOCK_LOGIN is off; refusing to issue a session."
            )
            return (
                "Sign-in is not configured. Set OAUTH_CLIENT_ID and "
                "OAUTH_CLIENT_SECRET, or set ALLOW_MOCK_LOGIN=1 for local "
                "development only.",
                503,
            )
        logger.warning("Bypassing OAuth: issuing a mock development session.")
        data = _new_session()
        data["access_token"] = "mock-access-token"
        data["user_email"] = "mock-user@example.invalid"
        data["token_expiry"] = (
            datetime.now(timezone.utc).replace(hour=23, minute=59, second=59)
        ).isoformat()
        return redirect(url_for("chat"))

    flow = get_oauth_flow()
    authorization_url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )
    session["oauth_state"] = state
    return redirect(authorization_url)


@app.route("/auth/callback")
def callback():
    """Completes the OAuth flow and establishes a server-side session."""
    if not validate_oauth_state(session.get("oauth_state"), request.args.get("state")):
        return "OAuth state mismatch; possible CSRF. Please retry sign-in.", 400

    flow = get_oauth_flow()
    flow.fetch_token(authorization_response=request.url)
    credentials = flow.credentials

    data = _new_session()
    data["access_token"] = credentials.token
    data["refresh_token"] = credentials.refresh_token
    data["token_expiry"] = (
        credentials.expiry.replace(tzinfo=timezone.utc).isoformat()
        if credentials.expiry
        else None
    )
    session.pop("oauth_state", None)

    userinfo_response = requests.get(
        "https://www.googleapis.com/oauth2/v2/userinfo",
        headers={"Authorization": f"Bearer {credentials.token}"},
        timeout=10,
    )
    data["user_email"] = (
        userinfo_response.json().get("email", "unknown")
        if userinfo_response.ok
        else "unknown"
    )
    return redirect(url_for("chat"))


@app.route("/chat")
def chat():
    """Renders the chat page for an authenticated user."""
    data = _session_data()
    if not data.get("access_token"):
        return redirect(url_for("index"))

    return render_template(
        "chat.html",
        user_email=data.get("user_email", "unknown"),
        runtime_mode="live_ca_api",
    )


@app.route("/api/query", methods=["POST"])
def query():
    """Answers a chat question via the Conversational Analytics API."""
    data = _session_data()
    if not data.get("access_token"):
        return {"error": "Not authenticated"}, 401

    body = request.get_json(silent=True) or {}
    message = body.get("message", "")
    if not message:
        return {"error": "Message is required"}, 400

    access_token, error = _ensure_valid_token(data)
    if error:
        return {"error": error, "reauth": True}, 401

    return _query_ca_api(message, access_token)


@app.route("/auth/logout")
def logout():
    """Discards the session and returns to the landing page."""
    _clear_session()
    return redirect(url_for("index"))


if __name__ == "__main__":
    # Development entrypoint only. Deployments serve this module through
    # gunicorn (see Dockerfile), which never executes this block.
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    # Permits the OAuth token exchange over plain HTTP for http://localhost.
    # Never set this when the app is reachable over a network.
    os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

    port = int(os.getenv("PORT", "8080"))
    logger.info("Starting development server on http://localhost:%s", port)
    logger.info(
        "Project=%s location=%s agent=%s", PROJECT_ID, GOOGLE_CLOUD_LOCATION, AGENT_ID
    )
    app.run(host="127.0.0.1", port=port, debug=env_flag("FLASK_DEBUG"))
