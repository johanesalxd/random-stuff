"""Unit tests for signed role assertions, allowlisted SA impersonation, and RLS runtime execution."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
import sys
from unittest.mock import MagicMock

import pytest

pytest.importorskip("google.adk")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from semantic import ca_trust, sql_runtime  # noqa: E402
from semantic.execution import (  # noqa: E402
    AdkBigQueryExecutor,
    ExecResult,
    SqlExecutionError,
    build_sql_executor,
)
from semantic.rls_impersonation import (  # noqa: E402
    ImpersonationError,
    build_impersonated_credentials,
    mint_hmac_role_assertion,
    parse_role_sa_map,
    redact_service_account_emails,
    verify_role_assertion,
)

_TEST_HMAC_SECRET = "super-secret-hmac-key-at-least-32-chars-long"
_VALID_ROLE_SA = "role-apac@example-project.iam.gserviceaccount.com"
_VALID_TRUSTED_CALLER_SA = "gateway-runner@example-project.iam.gserviceaccount.com"
_ROLE_MAP_JSON = json.dumps({"apac_analyst": _VALID_ROLE_SA})

_raw_execute_sql_once = (
    getattr(sql_runtime.execute_sql_once, "__wrapped__", None)
    or sql_runtime.execute_sql_once.__pydantic_private__["_func"]
)
_raw_finish_answer = (
    getattr(sql_runtime.finish_answer, "__wrapped__", None)
    or sql_runtime.finish_answer.__pydantic_private__["_func"]
)


class _ShimContext:
    """Minimal context shim providing state dict for node tests."""

    def __init__(self, state: dict | None = None) -> None:
        self.state = state or {}


def test_parse_role_sa_map_valid():
    parsed = parse_role_sa_map(_ROLE_MAP_JSON)
    assert parsed == {"apac_analyst": _VALID_ROLE_SA}


@pytest.mark.parametrize(
    "raw_json,expected_err",
    [
        (None, "cannot be empty or None"),
        ("", "cannot be empty or None"),
        ("   ", "cannot be empty or None"),
        ("not-json", "Malformed JSON"),
        ("[]", "must be a JSON object"),
        ("{}", "cannot be an empty dictionary"),
        (
            '{"role1": "role-apac@example-project.iam.gserviceaccount.com", "role1": "role-apac2@example-project.iam.gserviceaccount.com"}',
            "Duplicate role key",
        ),
        (
            '{"Invalid_Role": "role-apac@example-project.iam.gserviceaccount.com"}',
            "Invalid role slug",
        ),
        (
            '{"apac_analyst": "service-123@gcp-sa-aiplatform.iam.gserviceaccount.com"}',
            "invalid service account email",
        ),
        (
            '{"apac_analyst": "compute@developer.gserviceaccount.com"}',
            "invalid service account email",
        ),
        (
            '{"apac_analyst": "12345@cloudservices.gserviceaccount.com"}',
            "invalid service account email",
        ),
        (
            '{"apac_analyst": "not-an-email"}',
            "invalid service account email",
        ),
    ],
)
def test_parse_role_sa_map_rejections(raw_json: str | None, expected_err: str):
    with pytest.raises(ImpersonationError, match=expected_err):
        parse_role_sa_map(raw_json)


def test_mint_and_verify_hmac_assertion():
    now_ts = 1_700_000_000
    token = mint_hmac_role_assertion(
        role="apac_analyst",
        subject="analyst@example.com",
        hmac_secret=_TEST_HMAC_SECRET,
        ttl_seconds=300,
        now=now_ts,
    )
    assert token.startswith("v1.")
    parts = token.split(".")
    assert len(parts) == 3

    verified = verify_role_assertion(
        token,
        hmac_secret=_TEST_HMAC_SECRET,
        now=now_ts + 100,
    )
    assert verified.role == "apac_analyst"
    assert verified.subject == "analyst@example.com"
    assert verified.issuer == "hmac-local"
    assert verified.expires_at == now_ts + 300
    assert verified.job_labels["bqca-role"] == "apac_analyst"
    assert len(verified.job_labels["bqca-user-hash"]) == 16


def test_verify_hmac_rejections():
    now_ts = 1_700_000_000
    token = mint_hmac_role_assertion(
        role="apac_analyst",
        subject="analyst@example.com",
        hmac_secret=_TEST_HMAC_SECRET,
        ttl_seconds=300,
        now=now_ts,
    )

    # Tampered signature
    parts = token.split(".")
    tampered = f"{parts[0]}.{parts[1]}.tampered_sig"
    with pytest.raises(ImpersonationError, match="Invalid role assertion HMAC signature"):
        verify_role_assertion(tampered, hmac_secret=_TEST_HMAC_SECRET, now=now_ts)

    # Expired token
    with pytest.raises(ImpersonationError, match="has expired"):
        verify_role_assertion(token, hmac_secret=_TEST_HMAC_SECRET, now=now_ts + 301)

    # Audience mismatch
    with pytest.raises(ImpersonationError, match="audience mismatch"):
        verify_role_assertion(
            token,
            expected_audience="wrong-aud",
            hmac_secret=_TEST_HMAC_SECRET,
            now=now_ts,
        )

    # Forged bare role slug
    with pytest.raises(ImpersonationError, match="Invalid HMAC assertion format"):
        verify_role_assertion(
            "apac_analyst",
            hmac_secret=_TEST_HMAC_SECRET,
            now=now_ts,
        )

    # Missing secrets/caller
    with pytest.raises(ImpersonationError, match="Neither SQL_ROLE_TRUSTED_CALLER_SA nor SQL_ROLE_ASSERTION_HMAC_SECRET"):
        verify_role_assertion(token, now=now_ts)


def test_verify_role_assertion_trusted_caller_rs256(monkeypatch):
    import google.oauth2.id_token

    now_ts = 1_700_000_000

    # Test HMAC downgrade rejection
    hmac_token = mint_hmac_role_assertion(
        role="apac_analyst",
        subject="analyst@example.com",
        hmac_secret=_TEST_HMAC_SECRET,
        now=now_ts,
    )
    with pytest.raises(ImpersonationError, match="algorithm downgrade prevention"):
        verify_role_assertion(
            hmac_token,
            trusted_caller_sa=_VALID_TRUSTED_CALLER_SA,
            now=now_ts,
        )

    # Mock id_token.verify_token for RS256 verification
    mock_verify = MagicMock(
        return_value={
            "iss": _VALID_TRUSTED_CALLER_SA,
            "sub": "analyst-user@example.com",
            "bqca_role": "apac_analyst",
            "exp": now_ts + 300,
            "iat": now_ts,
            "aud": "bq-caapi-rls",
        }
    )
    monkeypatch.setattr(google.oauth2.id_token, "verify_token", mock_verify)

    verified = verify_role_assertion(
        "mock-rs256-jwt-token",
        trusted_caller_sa=_VALID_TRUSTED_CALLER_SA,
        expected_audience="bq-caapi-rls",
        now=now_ts,
    )
    assert verified.role == "apac_analyst"
    assert verified.subject == "analyst-user@example.com"
    assert verified.issuer == _VALID_TRUSTED_CALLER_SA
    assert verified.expires_at == now_ts + 300
    assert verified.job_labels["bqca-role"] == "apac_analyst"


def test_verify_role_assertion_missing_iat(monkeypatch):
    import google.oauth2.id_token

    now_ts = 1_700_000_000
    mock_verify = MagicMock(
        return_value={
            "iss": _VALID_TRUSTED_CALLER_SA,
            "sub": "analyst-user@example.com",
            "bqca_role": "apac_analyst",
            "exp": now_ts + 300,
            "aud": "bq-caapi-rls",
        }
    )
    monkeypatch.setattr(google.oauth2.id_token, "verify_token", mock_verify)

    with pytest.raises(ImpersonationError, match="missing 'iat' claim"):
        verify_role_assertion(
            "mock-rs256-jwt-token",
            trusted_caller_sa=_VALID_TRUSTED_CALLER_SA,
            now=now_ts,
        )


def test_verify_role_assertion_max_ttl_exceeded():
    now_ts = 1_700_000_000
    # Mint token with 3600s TTL
    token = mint_hmac_role_assertion(
        role="apac_analyst",
        subject="analyst@example.com",
        hmac_secret=_TEST_HMAC_SECRET,
        ttl_seconds=3600,
        now=now_ts,
    )
    # Default max_ttl_seconds is 900
    with pytest.raises(ImpersonationError, match=r"Role assertion TTL \(3600s\) must be positive and <= 900s"):
        verify_role_assertion(
            token,
            hmac_secret=_TEST_HMAC_SECRET,
            now=now_ts,
            max_ttl_seconds=900,
        )


def test_verify_role_assertion_expected_subject():
    now_ts = 1_700_000_000
    token = mint_hmac_role_assertion(
        role="apac_analyst",
        subject="alice@example.com",
        hmac_secret=_TEST_HMAC_SECRET,
        ttl_seconds=300,
        now=now_ts,
    )
    # Matching subject succeeds
    verified = verify_role_assertion(
        token,
        hmac_secret=_TEST_HMAC_SECRET,
        now=now_ts,
        expected_subject="alice@example.com",
    )
    assert verified.subject == "alice@example.com"

    # Mismatched subject fails
    with pytest.raises(ImpersonationError, match="Role assertion subject mismatch"):
        verify_role_assertion(
            token,
            hmac_secret=_TEST_HMAC_SECRET,
            now=now_ts,
            expected_subject="bob@example.com",
        )


def test_build_impersonated_credentials():
    role_map = {"apac_analyst": _VALID_ROLE_SA}

    # Unmapped role rejection - must not leak role_sa_map values in error
    with pytest.raises(ImpersonationError) as exc_info:
        build_impersonated_credentials(
            role="unknown_role",
            role_sa_map=role_map,
            target_scopes=["https://www.googleapis.com/auth/bigquery"],
        )
    assert "unknown_role" in str(exc_info.value)
    assert _VALID_ROLE_SA not in str(exc_info.value)

    # Invalid lifetime
    with pytest.raises(ImpersonationError, match="lifetime_seconds must be between"):
        build_impersonated_credentials(
            role="apac_analyst",
            role_sa_map=role_map,
            target_scopes=["https://www.googleapis.com/auth/bigquery"],
            lifetime_seconds=10,
        )

    # Empty scopes
    with pytest.raises(ImpersonationError, match="target_scopes cannot be empty"):
        build_impersonated_credentials(
            role="apac_analyst",
            role_sa_map=role_map,
            target_scopes=[],
        )

    # Valid build with mock source credentials
    fake_source = MagicMock()
    creds, target_sa = build_impersonated_credentials(
        role="apac_analyst",
        role_sa_map=role_map,
        target_scopes=["https://www.googleapis.com/auth/bigquery"],
        source_credentials=fake_source,
    )
    assert target_sa == _VALID_ROLE_SA
    assert creds is not None


def test_adk_bigquery_executor_explicit_credentials_required():
    executor = AdkBigQueryExecutor(
        project="test-project",
        require_explicit_credentials=True,
        credentials=None,
    )
    with pytest.raises(SqlExecutionError, match="explicit credentials are required when SQL_AUTH_MODE is not 'adc'"):
        executor._get_credentials()


def test_build_sql_executor_impersonated_sa_mode(monkeypatch):
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "test-project")
    fake_creds = MagicMock()

    # Missing credentials in impersonated_sa mode
    with pytest.raises(SqlExecutionError, match="impersonated_sa auth mode requires verified impersonated credentials"):
        build_sql_executor(auth_mode="impersonated_sa", impersonated_credentials=None)

    # Valid executor
    executor = build_sql_executor(
        auth_mode="impersonated_sa",
        impersonated_credentials=fake_creds,
        job_labels={"bqca-role": "apac_analyst"},
    )
    assert isinstance(executor, AdkBigQueryExecutor)
    assert executor._credentials is fake_creds
    assert executor._job_labels == {"bqca-role": "apac_analyst"}
    assert executor._require_explicit_credentials is True


def test_redact_service_account_emails():
    raw = (
        f"Permission denied for serviceAccount:{_VALID_ROLE_SA} on table "
        "and agent host agent-host@project.iam.gserviceaccount.com failed."
    )
    redacted = redact_service_account_emails(raw, replacement="role:apac_analyst")
    assert _VALID_ROLE_SA not in redacted
    assert "agent-host@project.iam.gserviceaccount.com" not in redacted
    assert "serviceAccount:role:apac_analyst" in redacted


def test_forged_raw_slug_rejected_in_session_state(monkeypatch):
    monkeypatch.setenv("SQL_AUTH_MODE", "impersonated_sa")
    monkeypatch.setenv("SQL_ROLE_SA_MAP_JSON", _ROLE_MAP_JSON)
    monkeypatch.setenv("SQL_ROLE_ASSERTION_HMAC_SECRET", _TEST_HMAC_SECRET)

    ctx = _ShimContext({
        "bq-caapi-role-assertion": "apac_analyst",
        "sql_generation_context": {"candidate_sources": []},
    })

    event = asyncio.run(_raw_execute_sql_once(ctx, "SELECT 1;"))
    assert event.actions.route == "error"
    assert event.output["status"] == "query_error"
    assert "Invalid HMAC assertion format" in event.output["error"]


def test_full_execute_sql_once_and_finish_answer_impersonated_sa(monkeypatch):
    monkeypatch.setenv("SQL_AUTH_MODE", "impersonated_sa")
    monkeypatch.setenv("SQL_ROLE_SA_MAP_JSON", _ROLE_MAP_JSON)
    monkeypatch.setenv("SQL_ROLE_ASSERTION_HMAC_SECRET", _TEST_HMAC_SECRET)
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "test-project")

    assertion = mint_hmac_role_assertion(
        role="apac_analyst",
        subject="user-123@example.com",
        hmac_secret=_TEST_HMAC_SECRET,
    )

    class _MockExecutor:
        def __init__(self):
            self.executed_sql = None

        def execute(self, sql: str) -> ExecResult:
            self.executed_sql = sql
            return ExecResult(
                status="SUCCESS",
                rows=(),
                row_count=0,
                truncated=False,
            )

    mock_exec = _MockExecutor()
    monkeypatch.setattr(sql_runtime, "build_sql_executor", lambda **_kwargs: mock_exec)

    ctx = _ShimContext({
        "bq-caapi-role-assertion": assertion,
        "sql_generation_context": {
            "candidate_sources": ["test-project.analytics.users"],
            "question": "Show my users",
        },
    })

    event = asyncio.run(_raw_execute_sql_once(ctx, "SELECT * FROM `test-project.analytics.users`;"))
    assert event.actions.route == "success"
    assert event.output["status"] == "query_executed"
    assert event.output["auth"]["mode"] == "impersonated_sa"
    assert event.output["auth"]["source"] == "impersonated-role-sa"
    assert event.output["auth"]["role"] == "apac_analyst"
    assert event.output["auth"]["job_labels"]["bqca-role"] == "apac_analyst"
    assert len(event.output["auth"]["job_labels"]["bqca-user-hash"]) == 16

    # 0-row finish_answer test -> downgrade to TIER_3_REVIEW_REQUIRED
    ctx.state["sql_execution_result"] = event.output
    finish_event = asyncio.run(_raw_finish_answer(ctx, "No users were returned."))
    assert finish_event.output["trust_tier"] == "TIER_3_REVIEW_REQUIRED"
    assert finish_event.output["trust_sub_mode"] == "REVIEW_REQUIRED"
    assert "Query returned 0 rows under role-scoped RLS" in finish_event.output["trust_reasons"][0]


def test_execute_sql_once_redacts_sa_in_execution_error(monkeypatch):
    monkeypatch.setenv("SQL_AUTH_MODE", "impersonated_sa")
    monkeypatch.setenv("SQL_ROLE_SA_MAP_JSON", _ROLE_MAP_JSON)
    monkeypatch.setenv("SQL_ROLE_ASSERTION_HMAC_SECRET", _TEST_HMAC_SECRET)
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "test-project")

    assertion = mint_hmac_role_assertion(
        role="apac_analyst",
        subject="user-123@example.com",
        hmac_secret=_TEST_HMAC_SECRET,
    )

    class _FailingExecutor:
        def execute(self, sql: str) -> ExecResult:
            return ExecResult(
                status="ERROR",
                error=f"Access denied for {_VALID_ROLE_SA} on dataset",
            )

    monkeypatch.setattr(sql_runtime, "build_sql_executor", lambda **_kwargs: _FailingExecutor())

    ctx = _ShimContext({
        "bq-caapi-role-assertion": assertion,
        "sql_generation_context": {
            "candidate_sources": ["test-project.analytics.users"],
        },
    })

    event = asyncio.run(_raw_execute_sql_once(ctx, "SELECT * FROM `test-project.analytics.users`;"))
    assert event.actions.route == "error"
    assert event.output["status"] == "query_error"
    assert _VALID_ROLE_SA not in event.output["error"]
    assert "role:apac_analyst" in event.output["error"]


def test_ca_trust_create_chat_client_impersonation(monkeypatch):
    mock_client_cls = MagicMock()
    monkeypatch.setattr("google.cloud.geminidataanalytics_v1beta.DataChatServiceClient", mock_client_cls)

    role_map = {"apac_analyst": _VALID_ROLE_SA}
    fake_source = MagicMock()

    client = ca_trust.create_chat_client(
        "us",
        impersonated_role="apac_analyst",
        role_sa_map=role_map,
        source_credentials=fake_source,
    )
    assert client is not None
    assert mock_client_cls.called

    # Test ambiguous auth parameters rejection
    with pytest.raises(ValueError, match="Ambiguous auth parameters"):
        ca_trust.create_chat_client(
            "us",
            user_access_token="valid-token",
            impersonated_role="apac_analyst",
            role_sa_map=role_map,
        )
