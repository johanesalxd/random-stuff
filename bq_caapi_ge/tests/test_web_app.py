"""Tests for the Phase 9 Slice 2 hardened OAuth test harness.

These are hermetic: no live OAuth, backend, or network calls. They require the
``web`` extra (Flask, google-auth-oauthlib) and skip otherwise.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
import sys

import pytest

pytest.importorskip("flask")
pytest.importorskip("google_auth_oauthlib")

# Force deterministic local-ADK config before importing the harness module.
os.environ.setdefault("ADK_LOCAL_BASE_URL", "http://localhost:9999")
os.environ.setdefault("OAUTH_CLIENT_ID", "test-client-id")
os.environ.setdefault("OAUTH_CLIENT_SECRET", "test-secret")
os.environ.setdefault("ADK_OAUTH_TOKEN_STATE_KEY", "AUTH_RESOURCE_SEMANTIC_ANALYTICS")

_WEB_DIR = Path(__file__).resolve().parents[1] / "advanced" / "test_web"
if str(_WEB_DIR) not in sys.path:
    sys.path.insert(0, str(_WEB_DIR))

import app as web_app  # noqa: E402


# --- pure helpers -----------------------------------------------------------


def test_validate_oauth_state():
    assert web_app.validate_oauth_state("abc", "abc") is True
    assert web_app.validate_oauth_state("abc", "xyz") is False
    assert web_app.validate_oauth_state(None, "abc") is False
    assert web_app.validate_oauth_state("abc", None) is False
    assert web_app.validate_oauth_state("", "") is False


def test_is_token_expired():
    now = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    future = (now + timedelta(hours=1)).isoformat()
    past = (now - timedelta(hours=1)).isoformat()
    near = (now + timedelta(seconds=30)).isoformat()
    assert web_app.is_token_expired(future, now=now) is False
    assert web_app.is_token_expired(past, now=now) is True
    assert web_app.is_token_expired(near, now=now) is True  # inside 60s skew
    assert web_app.is_token_expired(None) is True
    assert web_app.is_token_expired("not-a-date") is True


def test_select_final_output():
    events = [{"output": {"a": 1}}, {"output": {"status": "sql_planned"}}]
    assert web_app.select_final_output(events) == {"status": "sql_planned"}
    text_events = [{"content": {"parts": [{"text": "hello"}]}}]
    assert web_app.select_final_output(text_events) == "hello"
    assert web_app.select_final_output([]) is None


def test_extract_provenance():
    output = {
        "status": "sql_executed",
        "auth": {"mode": "user", "authorized": True},
        "sql": "SELECT 1",
        "execution": {"status": "SUCCESS"},
        "catalog_route": "narrow",
        "unrelated": "drop-me",
    }
    prov = web_app.extract_provenance(output)
    assert prov["status"] == "sql_executed"
    assert prov["auth"] == {"mode": "user", "authorized": True}
    assert prov["sql"] == "SELECT 1"
    assert prov["catalog_route"] == "narrow"
    assert "unrelated" not in prov
    assert web_app.extract_provenance("not-a-dict") == {}


def test_format_response_text():
    assert web_app.format_response_text(None) == "No response from agent"
    assert web_app.format_response_text("plain") == "plain"
    assert '"status"' in web_app.format_response_text({"status": "x"})


# --- token lifecycle --------------------------------------------------------


def test_ensure_valid_token_passes_live_token():
    future = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    data = {"access_token": "tok", "token_expiry": future}
    token, error = web_app._ensure_valid_token(data)
    assert token == "tok"
    assert error is None


def test_ensure_valid_token_requires_reauth_without_refresh():
    data = {"access_token": "tok", "token_expiry": None, "refresh_token": None}
    token, error = web_app._ensure_valid_token(data)
    assert token is None
    assert "sign in again" in error


def test_ensure_valid_token_refreshes_when_expired(monkeypatch):
    class _FakeCreds:
        def __init__(self):
            self.token = "old"
            self.expiry = datetime.now(timezone.utc) + timedelta(hours=1)

        def refresh(self, _request):
            self.token = "refreshed-tok"

    monkeypatch.setattr(web_app, "_credentials_from_store", lambda data: _FakeCreds())
    data = {"access_token": "old", "token_expiry": None, "refresh_token": "r"}
    token, error = web_app._ensure_valid_token(data)
    assert error is None
    assert token == "refreshed-tok"
    assert data["access_token"] == "refreshed-tok"
    assert data["token_expiry"] is not None


# --- backend session reuse --------------------------------------------------


class _FakeResp:
    def __init__(self, payload, ok=True):
        self._payload = payload
        self.ok = ok
        self.text = str(payload)

    def json(self):
        return self._payload


def test_local_session_is_reused_and_recreated_on_token_change(monkeypatch):
    calls: list[tuple[str, dict]] = []

    def fake_post(url, json=None, timeout=None):
        calls.append((url, json))
        return _FakeResp({"id": f"sess-{len(calls)}"})

    monkeypatch.setattr(web_app.requests, "post", fake_post)
    data = {"user_email": "u@example.com"}

    sid = web_app._get_or_create_local_session("http://x", "u@example.com", "tok", data)
    assert sid == "sess-1"
    assert data["local_session_id"] == "sess-1"
    # The token is injected into session state under the configured key.
    assert calls[0][1]["state"][web_app.TOKEN_STATE_KEY] == "tok"

    # Same token: session is reused, no new backend call.
    sid_again = web_app._get_or_create_local_session(
        "http://x", "u@example.com", "tok", data
    )
    assert sid_again == "sess-1"
    assert len(calls) == 1

    # Token changed (e.g. refreshed): a new session is created.
    sid_new = web_app._get_or_create_local_session(
        "http://x", "u@example.com", "tok-2", data
    )
    assert sid_new == "sess-2"
    assert len(calls) == 2
    assert calls[1][1]["state"][web_app.TOKEN_STATE_KEY] == "tok-2"


# --- routes -----------------------------------------------------------------


def test_query_requires_authentication():
    client = web_app.app.test_client()
    response = client.post("/api/query", json={"message": "hi"})
    assert response.status_code == 401


def test_callback_rejects_state_mismatch():
    client = web_app.app.test_client()
    with client.session_transaction() as sess:
        sess["oauth_state"] = "expected-state"
    response = client.get("/auth/callback?state=attacker&code=abc")
    assert response.status_code == 400
