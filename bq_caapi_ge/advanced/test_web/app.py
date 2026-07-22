"""Test web app for OAuth passthrough to Agent Engine or local ADK.

This is a development harness, not a production identity service. Phase 9 Slice 2
hardens the legacy behavior: OAuth state is validated before token exchange, access
tokens live in a server-side store (only an opaque session id is placed in the
signed cookie), tokens are refreshed when expired, backend sessions are reused
across queries, and the user token is written to the workflow's configured
session-state key (``ADK_OAUTH_TOKEN_STATE_KEY``, default
``AUTH_RESOURCE_SEMANTIC_ANALYTICS``) so it reaches the guarded SQL executor.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
import os
import secrets
import subprocess
from typing import Any

import requests
from dotenv import load_dotenv
from flask import Flask, redirect, render_template, request, session, url_for
from google_auth_oauthlib.flow import Flow

# Load environment from parent directory
load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

app = Flask(__name__)

# A stable secret keeps signed session cookies valid across restarts. An ephemeral
# secret is only acceptable for throwaway local runs and logs a warning.
_secret = os.getenv("FLASK_SECRET_KEY")
if not _secret:
    _secret = secrets.token_hex(32)
    print(
        "WARNING: FLASK_SECRET_KEY is not set; using an ephemeral secret. "
        "Sessions will not survive a restart."
    )
app.secret_key = _secret
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.getenv("COOKIE_SECURE", "0").strip().lower()
    in {"1", "true", "yes", "on"},
)

# Allow OAuth scope changes (Google may add scopes like bigquery)
os.environ["OAUTHLIB_RELAX_TOKEN_SCOPE"] = "1"

# Configuration
CLIENT_ID = os.getenv("OAUTH_CLIENT_ID")
CLIENT_SECRET = os.getenv("OAUTH_CLIENT_SECRET")
PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT")
REASONING_ENGINE_ID = os.getenv("ORDERS_REASONING_ENGINE_ID")
# The workflow reads the user token from this session-state key. It must match the
# engine's ADK_OAUTH_TOKEN_STATE_KEY (default AUTH_RESOURCE_SEMANTIC_ANALYTICS).
TOKEN_STATE_KEY = os.getenv(
    "ADK_OAUTH_TOKEN_STATE_KEY", "AUTH_RESOURCE_SEMANTIC_ANALYTICS"
)
ADK_LOCAL_BASE_URL = os.getenv("ADK_LOCAL_BASE_URL")
ADK_LOCAL_APP_NAME = os.getenv("ADK_LOCAL_APP_NAME", "semantic_analytics")

if ADK_LOCAL_BASE_URL:
    RUNTIME_MODE = "local_adk"
elif PROJECT_ID and REASONING_ENGINE_ID:
    RUNTIME_MODE = "agent_engine"
else:
    raise ValueError(
        "Set ADK_LOCAL_BASE_URL for local ADK mode or set "
        "GOOGLE_CLOUD_PROJECT and ORDERS_REASONING_ENGINE_ID for Agent Engine mode"
    )

# Option A (Phase 9): the user token scopes SQL execution. `bigquery` is sufficient;
# `cloud-platform` is a superset that also covers user-scoped Dataplex if adopted.
SCOPES = [
    "https://www.googleapis.com/auth/cloud-platform",
    "https://www.googleapis.com/auth/userinfo.email",
    "openid",
]
REDIRECT_URI = "http://localhost:8080/auth/callback"

# Agent Engine API base URL
AGENT_ENGINE_BASE = (
    f"https://us-central1-aiplatform.googleapis.com/v1/projects/{PROJECT_ID}"
    f"/locations/us-central1/reasoningEngines/{REASONING_ENGINE_ID}"
)

# Server-side session store. Only an opaque session id is placed in the signed
# cookie; access and refresh tokens never leave the server. This in-process dict is
# adequate for a single-process dev harness; a real deployment would use a shared
# backing store.
_SESSIONS: dict[str, dict[str, Any]] = {}


# --- pure helpers (unit-testable without a Flask context) -------------------


def validate_oauth_state(expected: str | None, received: str | None) -> bool:
    """Returns whether the OAuth callback state matches the stored state.

    A constant-time comparison of two present, non-empty values.
    """
    if not expected or not received:
        return False
    return secrets.compare_digest(str(expected), str(received))


def is_token_expired(
    expiry_iso: str | None, *, now: datetime | None = None, skew_seconds: int = 60
) -> bool:
    """Returns whether an ISO-8601 expiry has passed, within a safety skew.

    Missing or unparseable expiries are treated as expired (fail closed).
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


def select_final_output(events: list[dict[str, Any]]) -> Any:
    """Returns the last event payload from an ADK ``/run`` event list."""
    for event in reversed(events):
        output = event.get("output")
        if output is not None:
            return output
        content = event.get("content", {})
        parts = content.get("parts", [])
        text = "".join(part.get("text", "") for part in parts)
        if text:
            return text
    return None


def format_response_text(output: Any) -> str:
    """Renders a workflow output payload for display."""
    if output is None:
        return "No response from agent"
    if isinstance(output, str):
        return output
    return json.dumps(output, indent=2)


def extract_provenance(output: Any) -> dict[str, Any]:
    """Extracts the reasoning-path and execution provenance from an output payload.

    Returns an empty dict for non-structured output. Values are copied verbatim; no
    computation or reformatting of returned data occurs here.
    """
    if not isinstance(output, dict):
        return {}
    keys = (
        "status",
        "next_step",
        "catalog_route",
        "catalog_discovery_backend",
        "auth",
        "sql",
        "sql_policy",
        "dry_run",
        "execution",
        "refusal_reason",
        "auth_error",
    )
    return {key: output[key] for key in keys if key in output}


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
    """Returns a live access token, refreshing it when expired.

    Returns ``(token, None)`` on success, or ``(None, error)`` when the token is
    expired and cannot be refreshed (the caller must reauthenticate).
    """
    if not is_token_expired(data.get("token_expiry")):
        return data.get("access_token"), None
    if not data.get("refresh_token"):
        return None, "session expired; please sign in again"
    try:
        from google.auth.transport.requests import Request

        credentials = _credentials_from_store(data)
        credentials.refresh(Request())
    except Exception as error:  # surface any refresh failure as reauth
        return None, f"token refresh failed; please sign in again: {error}"
    data["access_token"] = credentials.token
    data["token_expiry"] = (
        credentials.expiry.replace(tzinfo=timezone.utc).isoformat()
        if credentials.expiry
        else None
    )
    return credentials.token, None


# --- backend query paths ----------------------------------------------------


def _query_local_adk(message: str, access_token: str, data: dict[str, Any]):
    base_url = ADK_LOCAL_BASE_URL.rstrip("/")
    user_email = data.get("user_email", "test-user")
    session_id = _get_or_create_local_session(base_url, user_email, access_token, data)
    if session_id is None:
        return {"error": "Failed to create local ADK session"}, 500

    run_payload = {
        "app_name": ADK_LOCAL_APP_NAME,
        "user_id": user_email,
        "session_id": session_id,
        "new_message": {"role": "user", "parts": [{"text": message}]},
    }
    run_response = requests.post(f"{base_url}/run", json=run_payload, timeout=120)
    if not run_response.ok:
        return {"error": f"Local ADK query failed: {run_response.text}"}, 500

    output = select_final_output(run_response.json())
    return {
        "response": format_response_text(output),
        "provenance": extract_provenance(output),
        "session_id": session_id,
        "runtime_mode": RUNTIME_MODE,
        "app_name": ADK_LOCAL_APP_NAME,
    }


def _get_or_create_local_session(
    base_url: str, user_email: str, access_token: str, data: dict[str, Any]
) -> str | None:
    """Returns a reusable local ADK session id, recreating it if the token changed.

    The token is written into session state under ``TOKEN_STATE_KEY``; when it is
    refreshed, a new session is created so the workflow sees the current token.
    """
    cached = data.get("local_session_id")
    if cached and data.get("session_token") == access_token:
        return cached
    session_payload = {"state": {TOKEN_STATE_KEY: access_token}}
    response = requests.post(
        f"{base_url}/apps/{ADK_LOCAL_APP_NAME}/users/{user_email}/sessions",
        json=session_payload,
        timeout=30,
    )
    if not response.ok:
        return None
    session_id = response.json().get("id")
    if not session_id:
        return None
    data["local_session_id"] = session_id
    data["session_token"] = access_token
    return session_id


def _query_agent_engine(message: str, access_token: str, data: dict[str, Any]):
    user_email = data.get("user_email", "test-user")
    try:
        gcp_token = _get_gcp_access_token()
    except Exception as e:
        return {"error": f"Failed to get GCP token: {e}"}, 500

    headers = {
        "Authorization": f"Bearer {gcp_token}",
        "Content-Type": "application/json",
    }
    session_id = _get_or_create_agent_session(headers, user_email, access_token, data)
    if session_id is None:
        return {"error": "Failed to create Agent Engine session"}, 500

    query_payload = {
        "input": {
            "message": message,
            "user_id": user_email,
            "session_id": session_id,
        }
    }
    query_response = requests.post(
        f"{AGENT_ENGINE_BASE}:streamQuery",
        headers=headers,
        json=query_payload,
        timeout=120,
    )
    if not query_response.ok:
        return {"error": f"Query failed: {query_response.text}"}, 500

    output = _extract_agent_engine_response(query_response.text)
    return {
        "response": output or "No response from agent",
        "provenance": extract_provenance(_maybe_json(output)),
        "session_id": session_id,
        "runtime_mode": RUNTIME_MODE,
        "app_name": REASONING_ENGINE_ID,
    }


def _get_or_create_agent_session(
    headers: dict[str, str], user_email: str, access_token: str, data: dict[str, Any]
) -> str | None:
    cached = data.get("agent_session_id")
    if cached and data.get("session_token") == access_token:
        return cached
    session_payload = {
        "userId": user_email,
        "sessionState": {TOKEN_STATE_KEY: access_token},
    }
    response = requests.post(
        f"{AGENT_ENGINE_BASE}/sessions",
        headers=headers,
        json=session_payload,
        timeout=30,
    )
    if not response.ok:
        return None
    session_name = response.json().get("name", "")
    parts = session_name.split("/sessions/")
    if len(parts) < 2:
        return None
    session_id = parts[1].split("/")[0]
    data["agent_session_id"] = session_id
    data["session_token"] = access_token
    return session_id


def _get_gcp_access_token() -> str:
    result = subprocess.run(
        ["gcloud", "auth", "print-access-token"],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def _extract_agent_engine_response(response_body: str) -> str:
    response_text = ""
    for line in response_body.strip().split("\n"):
        if line:
            try:
                event = json.loads(line)
                content = event.get("content", {})
                parts = content.get("parts", [])
                for part in parts:
                    if "text" in part:
                        response_text += part["text"]
            except json.JSONDecodeError:
                continue
    return response_text


def _maybe_json(text: str) -> Any:
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return text


def get_oauth_flow():
    """Create OAuth flow with client configuration."""
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
    """Landing page - show login or redirect to chat."""
    if _session_data().get("access_token"):
        return redirect(url_for("chat"))
    return render_template("index.html")


@app.route("/auth/login")
def login():
    """Initiate Google OAuth flow."""
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
    """Handle OAuth callback, validating state before exchanging the code."""
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
    """Chat interface."""
    data = _session_data()
    if not data.get("access_token"):
        return redirect(url_for("index"))

    return render_template(
        "chat.html",
        user_email=data.get("user_email", "unknown"),
        token_expiry=data.get("token_expiry"),
        reasoning_engine_id=REASONING_ENGINE_ID,
        auth_resource_id=TOKEN_STATE_KEY,
        runtime_mode=RUNTIME_MODE,
        adk_local_base_url=ADK_LOCAL_BASE_URL,
        adk_local_app_name=ADK_LOCAL_APP_NAME,
    )


@app.route("/api/query", methods=["POST"])
def query():
    """Send query to the backend with the user OAuth token in session state."""
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

    if RUNTIME_MODE == "local_adk":
        return _query_local_adk(message, access_token, data)
    return _query_agent_engine(message, access_token, data)


@app.route("/auth/logout")
def logout():
    """Clear session and logout."""
    _clear_session()
    return redirect(url_for("index"))


if __name__ == "__main__":
    # Allow OAuth over HTTP for localhost
    os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"
    print("\nTest Web App Starting...")
    print(f"  Runtime Mode: {RUNTIME_MODE}")
    if RUNTIME_MODE == "local_adk":
        print(f"  ADK Local Base URL: {ADK_LOCAL_BASE_URL}")
        print(f"  ADK Local App: {ADK_LOCAL_APP_NAME}")
    else:
        print(f"  Project: {PROJECT_ID}")
        print(f"  Reasoning Engine: {REASONING_ENGINE_ID}")
    print(f"  Token State Key: {TOKEN_STATE_KEY}")
    print("\nOpen http://localhost:8080 in your browser\n")
    app.run(host="0.0.0.0", port=8080, debug=True)
