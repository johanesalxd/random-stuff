"""Tests for the hardened OAuth test harness.

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
os.environ.setdefault("ADK_OAUTH_TOKEN_STATE_KEY", "bq-caapi-oauth-semantic")

_WEB_DIR = Path(__file__).resolve().parents[1] / "advanced" / "test_web"
if not _WEB_DIR.exists():
    pytest.skip("advanced/test_web not present", allow_module_level=True)
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
        "authoring_mode": "compiled",
        "trust_tier": "TIER_1_VERIFIED_OR_COMPILED",
        "trust_sub_mode": "STRICT_CONTRACT_COMPILED",
        "trust_reasons": ["deterministically compiled from YAML contract"],
        "semantic_context_ids": ["thelook_orders"],
        "auth": {"mode": "user", "authorized": True},
        "sql": "SELECT 1",
        "execution": {"status": "SUCCESS"},
        "catalog_route": "narrow",
        "unrelated": "drop-me",
    }
    prov = web_app.extract_provenance(output)
    assert prov["status"] == "sql_executed"
    assert prov["authoring_mode"] == "compiled"
    assert prov["trust_tier"] == "TIER_1_VERIFIED_OR_COMPILED"
    assert prov["trust_sub_mode"] == "STRICT_CONTRACT_COMPILED"
    assert prov["trust_reasons"] == ["deterministically compiled from YAML contract"]
    assert prov["semantic_context_ids"] == ["thelook_orders"]
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


def test_login_captures_pkce_code_verifier_and_callback_restores_it(monkeypatch):
    """Login must save code_verifier and callback must restore it on the new Flow."""
    created_flows = []

    class _FakeFlow:
        def __init__(self):
            self.code_verifier = f"verifier-{len(created_flows) + 1}"
            self.credentials = type(
                "Creds",
                (),
                {"token": "tok-1", "refresh_token": "ref-1", "expiry": None},
            )()
            created_flows.append(self)

        def authorization_url(self, **kwargs):
            return "https://accounts.google.com/o/oauth2/auth?state=st123", "st123"

        def fetch_token(self, authorization_response=None):
            self.fetched_with_verifier = self.code_verifier

    monkeypatch.setattr(web_app, "get_oauth_flow", lambda: _FakeFlow())
    monkeypatch.setattr(
        web_app.requests,
        "get",
        lambda *args, **kwargs: type("Resp", (), {"ok": True, "json": lambda *a, **k: {"email": "u@test.com"}})(),
    )

    client = web_app.app.test_client()

    # 1. Login captures code_verifier
    resp_login = client.get("/auth/login")
    assert resp_login.status_code == 302
    assert "accounts.google.com" in resp_login.headers["Location"]
    with client.session_transaction() as sess:
        assert sess.get("oauth_state") == "st123"
        assert sess.get("oauth_code_verifier") == "verifier-1"

    # 2. Callback restores code_verifier on the second Flow instance
    resp_callback = client.get("/auth/callback?state=st123&code=auth-code-xyz")
    assert resp_callback.status_code == 302
    assert len(created_flows) == 2
    # Flow 2 received the verifier captured from Flow 1!
    assert created_flows[1].code_verifier == "verifier-1"
    assert created_flows[1].fetched_with_verifier == "verifier-1"
    # Session cleaned up
    with client.session_transaction() as sess:
        assert "oauth_code_verifier" not in sess
        assert "oauth_state" not in sess

