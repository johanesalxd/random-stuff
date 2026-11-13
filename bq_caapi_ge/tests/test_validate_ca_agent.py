"""Unit and regression tests for validate_ca_agent CLI."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
from unittest.mock import patch

import google.auth.exceptions
import pytest
import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.validate_ca_agent import (  # noqa: E402
    get_chat_client,
    load_questions,
    load_verified_queries,
    main,
)
from semantic.ca_trust import TrustAssessment, TrustTier  # noqa: E402


def test_validate_ca_agent_help() -> None:
    """Verifies that --help succeeds cleanly from an external temporary directory."""
    script = PROJECT_ROOT / "scripts" / "validate_ca_agent.py"
    res = subprocess.run(
        [sys.executable, str(script), "--help"],
        cwd=tempfile.gettempdir(),
        capture_output=True,
        text=True,
        check=False,
    )
    assert res.returncode == 0
    assert "validate_ca_agent.py" in res.stdout or "usage:" in res.stdout.lower()


def test_load_questions_flat_list(tmp_path: Path) -> None:
    """Verifies loading flat list questions from YAML."""
    yaml_file = tmp_path / "questions.yaml"
    yaml_content = [
        "What is total revenue?",
        {"question": "How many orders?", "expected_note": "42"},
    ]
    with yaml_file.open("w", encoding="utf-8") as f:
        yaml.safe_dump(yaml_content, f)

    suites = load_questions(None, str(yaml_file), default_agent="order_agent")
    assert len(suites) == 1
    agent_id, questions = suites[0]
    assert agent_id == "order_agent"
    assert len(questions) == 2
    assert questions[0] == ("What is total revenue?", "")
    assert questions[1] == ("How many orders?", "42")


def test_load_questions_suites(tmp_path: Path) -> None:
    """Verifies loading multi-agent suites format from YAML."""
    yaml_file = tmp_path / "suites.yaml"
    data = {
        "suites": [
            {
                "agent_id": "agent_alpha",
                "questions": ["Question A1", "Question A2"],
            },
            {
                "agent_id": "agent_beta",
                "questions": [{"question": "Question B1", "expected_note": "Expected B"}],
            },
        ]
    }
    with yaml_file.open("w", encoding="utf-8") as f:
        yaml.safe_dump(data, f)

    suites = load_questions(None, str(yaml_file), default_agent=None)
    assert len(suites) == 2
    assert suites[0][0] == "agent_alpha"
    assert len(suites[0][1]) == 2
    assert suites[1][0] == "agent_beta"
    assert suites[1][1] == [("Question B1", "Expected B")]


def test_load_verified_queries(tmp_path: Path) -> None:
    """Verifies parsing exported verified queries JSON file."""
    json_file = tmp_path / "verified_queries.json"
    data = [
        {
            "question": "What is our completed revenue?",
            "sql": "SELECT SUM(sale_price) FROM order_items WHERE status = 'Complete'",
            "query_id": "completed_revenue",
        }
    ]
    with json_file.open("w", encoding="utf-8") as f:
        json.dump(data, f)

    specs = load_verified_queries(str(json_file))
    assert len(specs) == 1
    assert specs[0].question == "What is our completed revenue?"
    assert specs[0].query_id == "completed_revenue"


def test_max_tier_threshold_behavior() -> None:
    """Verifies that responses below max_tier return non-zero exit code while passing tiers return 0."""
    tier_1_assessment = TrustAssessment(
        tier=TrustTier.TIER_1_VERIFIED_OR_COMPILED,
        sub_mode="AUTHORED_VERIFIED_QUERY",
    )
    tier_2_assessment = TrustAssessment(
        tier=TrustTier.TIER_2_GROUNDED,
        sub_mode="DYNAMIC_SQL_GROUNDED",
    )
    tier_3_assessment = TrustAssessment(
        tier=TrustTier.TIER_3_REVIEW_REQUIRED,
        sub_mode="REVIEW_REQUIRED",
    )

    # 1. Tier 2 max-tier accepts Tier 1 and Tier 2 -> exit code 0
    with patch("scripts.validate_ca_agent.get_chat_client"), \
         patch("scripts.validate_ca_agent.stream_stateless_chat", return_value=tier_1_assessment):
        ret_t1 = main([
            "--project", "test-project-123",
            "--agent", "test_agent",
            "-q", "What is total revenue?",
            "--max-tier", "2",
        ])
        assert ret_t1 == 0

    with patch("scripts.validate_ca_agent.get_chat_client"), \
         patch("scripts.validate_ca_agent.stream_stateless_chat", return_value=tier_2_assessment):
        ret_ok = main([
            "--project", "test-project-123",
            "--agent", "test_agent",
            "-q", "What is total revenue?",
            "--max-tier", "2",
        ])
        assert ret_ok == 0

    # 2. Tier 2 max-tier rejects Tier 3 -> exit code 1
    with patch("scripts.validate_ca_agent.get_chat_client"), \
         patch("scripts.validate_ca_agent.stream_stateless_chat", return_value=tier_3_assessment):
        ret_fail = main([
            "--project", "test-project-123",
            "--agent", "test_agent",
            "-q", "What is total revenue?",
            "--max-tier", "2",
        ])
        assert ret_fail == 1


def test_mutual_exclusion_token_and_impersonation(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verifies that specifying CA_USER_ACCESS_TOKEN and --impersonate-role simultaneously is rejected."""
    monkeypatch.setenv("CA_USER_ACCESS_TOKEN", "mock-token-xyz")
    ret = main([
        "--project", "test-project-123",
        "--agent", "test_agent",
        "-q", "What is total revenue?",
        "--impersonate-role", "analyst",
    ])
    assert ret == 1


def test_google_auth_error_handled_gracefully() -> None:
    """Verifies that GoogleAuthError is caught cleanly without unhandled traceback."""
    with patch("scripts.validate_ca_agent.get_chat_client", side_effect=google.auth.exceptions.GoogleAuthError("No credentials")):
        ret = main([
            "--project", "test-project-123",
            "--agent", "test_agent",
            "-q", "What is total revenue?",
        ])
        assert ret == 1


def test_get_chat_client_impersonate_role_success(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verifies real get_chat_client succeeds with valid impersonation role and passes credentials to DataChatServiceClient."""
    monkeypatch.setenv(
        "SQL_ROLE_SA_MAP_JSON",
        '{"apac_analyst": "role-apac@my-project.iam.gserviceaccount.com"}',
    )
    mock_source_creds = patch("google.auth.default", return_value=(object(), "my-project"))
    mock_target_creds = object()
    mock_impersonated = patch(
        "google.auth.impersonated_credentials.Credentials",
        return_value=mock_target_creds,
    )
    mock_client_cls = patch(
        "google.cloud.geminidataanalytics_v1beta.DataChatServiceClient"
    )
    passing_assessment = TrustAssessment(
        tier=TrustTier.TIER_1_VERIFIED_OR_COMPILED,
        sub_mode="AUTHORED_VERIFIED_QUERY",
    )
    with mock_source_creds, mock_impersonated, mock_client_cls as mock_client, \
         patch("scripts.validate_ca_agent.stream_stateless_chat", return_value=passing_assessment):
        # 1. Test get_chat_client directly
        client = get_chat_client(
            location="global",
            project="my-project",
            impersonate_role="apac_analyst",
            user_access_token=None,
        )
        assert client is not None

        # 2. Call main without patching get_chat_client
        ret = main([
            "--project", "my-project",
            "--agent", "test_agent",
            "-q", "What is total revenue?",
            "--impersonate-role", "apac_analyst",
        ])
        assert ret == 0
        assert mock_client.call_count >= 1
        _, kwargs = mock_client.call_args
        assert kwargs.get("credentials") is mock_target_creds


def test_get_chat_client_impersonate_role_unmapped_exits_cleanly(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verifies that an unmapped role exits cleanly with return code 1 without traceback crash."""
    monkeypatch.setenv(
        "SQL_ROLE_SA_MAP_JSON",
        '{"apac_analyst": "role-apac@my-project.iam.gserviceaccount.com"}',
    )
    ret = main([
        "--project", "my-project",
        "--agent", "test_agent",
        "-q", "What is total revenue?",
        "--impersonate-role", "unknown_role",
    ])
    assert ret == 1
