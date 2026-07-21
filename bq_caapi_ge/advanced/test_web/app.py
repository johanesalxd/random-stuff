"""Test web app for OAuth passthrough to Agent Engine or local ADK."""

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
app.secret_key = secrets.token_hex(32)

# Allow OAuth scope changes (Google may add scopes like bigquery)
os.environ["OAUTHLIB_RELAX_TOKEN_SCOPE"] = "1"

# Configuration
CLIENT_ID = os.getenv("OAUTH_CLIENT_ID")
CLIENT_SECRET = os.getenv("OAUTH_CLIENT_SECRET")
PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT")
REASONING_ENGINE_ID = os.getenv("ORDERS_REASONING_ENGINE_ID")
AUTH_RESOURCE_ID = os.getenv("AUTH_RESOURCE_ORDERS", "bq-caapi-oauth")
ADK_LOCAL_BASE_URL = os.getenv("ADK_LOCAL_BASE_URL")
ADK_LOCAL_APP_NAME = os.getenv("ADK_LOCAL_APP_NAME", "certified_analytics")

if ADK_LOCAL_BASE_URL:
    RUNTIME_MODE = "local_adk"
elif PROJECT_ID and REASONING_ENGINE_ID:
    RUNTIME_MODE = "agent_engine"
else:
    raise ValueError(
        "Set ADK_LOCAL_BASE_URL for local ADK mode or set "
        "GOOGLE_CLOUD_PROJECT and ORDERS_REASONING_ENGINE_ID for Agent Engine mode"
    )

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


def _extract_local_adk_response(events: list[dict[str, Any]]) -> str:
    for event in reversed(events):
        output = event.get("output")
        if output is not None:
            if isinstance(output, str):
                return output
            return json.dumps(output, indent=2)

        content = event.get("content", {})
        parts = content.get("parts", [])
        text = "".join(part.get("text", "") for part in parts)
        if text:
            return text

    return "No response from agent"


def _query_local_adk(message: str, access_token: str, user_email: str):
    base_url = ADK_LOCAL_BASE_URL.rstrip("/")
    session_payload = {
        "state": {
            AUTH_RESOURCE_ID: access_token,
        }
    }

    session_response = requests.post(
        f"{base_url}/apps/{ADK_LOCAL_APP_NAME}/users/{user_email}/sessions",
        json=session_payload,
        timeout=30,
    )
    if not session_response.ok:
        return {
            "error": f"Failed to create local ADK session: {session_response.text}"
        }, 500

    session_id = session_response.json().get("id")
    if not session_id:
        return {"error": f"Local ADK session has no ID: {session_response.text}"}, 500

    run_payload = {
        "app_name": ADK_LOCAL_APP_NAME,
        "user_id": user_email,
        "session_id": session_id,
        "new_message": {
            "role": "user",
            "parts": [{"text": message}],
        },
    }
    run_response = requests.post(
        f"{base_url}/run",
        json=run_payload,
        timeout=120,
    )
    if not run_response.ok:
        return {"error": f"Local ADK query failed: {run_response.text}"}, 500

    return {
        "response": _extract_local_adk_response(run_response.json()),
        "session_id": session_id,
        "runtime_mode": RUNTIME_MODE,
        "app_name": ADK_LOCAL_APP_NAME,
    }


def _query_agent_engine(message: str, access_token: str, user_email: str):
    try:
        gcp_token = _get_gcp_access_token()
    except Exception as e:
        return {"error": f"Failed to get GCP token: {e}"}, 500

    headers = {
        "Authorization": f"Bearer {gcp_token}",
        "Content-Type": "application/json",
    }

    session_payload = {
        "userId": user_email,
        "sessionState": {
            AUTH_RESOURCE_ID: access_token,
        },
    }

    create_session_url = f"{AGENT_ENGINE_BASE}/sessions"
    session_response = requests.post(
        create_session_url,
        headers=headers,
        json=session_payload,
        timeout=30,
    )

    if not session_response.ok:
        return {"error": f"Failed to create session: {session_response.text}"}, 500

    operation = session_response.json()
    session_name = operation.get("name", "")
    parts = session_name.split("/sessions/")
    if len(parts) < 2:
        return {"error": f"Could not parse session ID from: {session_name}"}, 500

    session_id = parts[1].split("/")[0]

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

    return {
        "response": _extract_agent_engine_response(query_response.text)
        or "No response from agent",
        "session_id": session_id,
        "runtime_mode": RUNTIME_MODE,
        "app_name": REASONING_ENGINE_ID,
    }


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
    if "access_token" in session:
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
    """Handle OAuth callback."""
    flow = get_oauth_flow()
    flow.fetch_token(authorization_response=request.url)

    credentials = flow.credentials
    session["access_token"] = credentials.token
    session["token_expiry"] = (
        credentials.expiry.isoformat() if credentials.expiry else None
    )

    # Get user info
    userinfo_response = requests.get(
        "https://www.googleapis.com/oauth2/v2/userinfo",
        headers={"Authorization": f"Bearer {credentials.token}"},
        timeout=10,
    )
    if userinfo_response.ok:
        userinfo = userinfo_response.json()
        session["user_email"] = userinfo.get("email", "unknown")
    else:
        session["user_email"] = "unknown"

    return redirect(url_for("chat"))


@app.route("/chat")
def chat():
    """Chat interface."""
    if "access_token" not in session:
        return redirect(url_for("index"))

    return render_template(
        "chat.html",
        user_email=session.get("user_email", "unknown"),
        token_expiry=session.get("token_expiry"),
        reasoning_engine_id=REASONING_ENGINE_ID,
        auth_resource_id=AUTH_RESOURCE_ID,
        runtime_mode=RUNTIME_MODE,
        adk_local_base_url=ADK_LOCAL_BASE_URL,
        adk_local_app_name=ADK_LOCAL_APP_NAME,
    )


@app.route("/api/query", methods=["POST"])
def query():
    """Send query to Agent Engine with OAuth token in session state."""
    if "access_token" not in session:
        return {"error": "Not authenticated"}, 401

    data = request.get_json()
    message = data.get("message", "")

    if not message:
        return {"error": "Message is required"}, 400

    access_token = session["access_token"]
    user_email = session.get("user_email", "test-user")

    if RUNTIME_MODE == "local_adk":
        return _query_local_adk(message, access_token, user_email)
    return _query_agent_engine(message, access_token, user_email)


@app.route("/auth/logout")
def logout():
    """Clear session and logout."""
    session.clear()
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
    print(f"  Auth Resource ID: {AUTH_RESOURCE_ID}")
    print("\nOpen http://localhost:8080 in your browser\n")
    app.run(host="0.0.0.0", port=8080, debug=True)
