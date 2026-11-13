"""Unit and smoke tests for verify_bqca_audit CLI."""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import tempfile
from unittest.mock import MagicMock, patch

from google.cloud import bigquery

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.verify_bqca_audit import (  # noqa: E402
    main,
    prove_audit_logs,
    prove_labels,
    prove_live,
)


def test_verify_bqca_audit_help() -> None:
    """Verifies that --help succeeds when invoked from an arbitrary working directory."""
    script = PROJECT_ROOT / "scripts" / "verify_bqca_audit.py"
    res = subprocess.run(
        [sys.executable, str(script), "--help"],
        cwd=tempfile.gettempdir(),
        capture_output=True,
        text=True,
        check=False,
    )
    assert res.returncode == 0
    assert "verify_bqca_audit.py" in res.stdout or "usage:" in res.stdout.lower()


def test_invalid_project_rejection() -> None:
    """Verifies that malformed GCP project IDs are rejected with non-zero exit code."""
    ret = main(["--project", "INVALID_PROJECT!", "--bq-region", "region-us"])
    assert ret == 1


def test_invalid_bq_region_rejection() -> None:
    """Verifies that malformed BigQuery region identifiers are rejected."""
    ret = main(["--project", "test-project-123", "--bq-region", "us-central1"])
    assert ret == 1


def test_prove_labels_parameterization() -> None:
    """Verifies that prove_labels uses bigquery.ScalarQueryParameter and does not format raw inputs into SQL."""
    mock_client = MagicMock(spec=bigquery.Client)
    mock_query_job = MagicMock()
    mock_query_job.result.return_value = [
        {
            "data_agent_id": "test_agent",
            "bqca_role": "analyst",
            "bqca_user_hash": "abc1234",
            "jobs": 10,
            "bytes_billed": 1024 * 1024 * 1024,
            "est_cost_usd": 0.0061,
        }
    ]
    mock_client.query.return_value = mock_query_job

    rows = prove_labels(
        client=mock_client,
        project="test-project-123",
        bq_region="region-us",
        lookback_days=45,
        tib_rate_usd=6.25,
    )

    assert len(rows) == 1
    assert rows[0]["data_agent_id"] == "test_agent"
    assert mock_client.query.call_count == 1
    call_args, call_kwargs = mock_client.query.call_args
    sql_text = call_args[0]
    assert "@lookback_days" in sql_text
    assert "@tib_rate_usd" in sql_text
    job_config = call_kwargs["job_config"]
    params = {p.name: p.value for p in job_config.query_parameters}
    assert params["lookback_days"] == 45
    assert params["tib_rate_usd"] == 6.25


def test_mtls_banner_stripping_in_audit_logs() -> None:
    """Verifies that mTLS enterprise certificate proxy banner lines are stripped before JSON parsing."""
    raw_stdout = (
        "Created enterprise-certificate-proxy configuration file at /tmp/cert.json\n"
        "Some other client info line\n"
        "[\n"
        "  {\n"
        '    "protoPayload": {\n'
        '      "serviceName": "geminidataanalytics.googleapis.com",\n'
        '      "methodName": "google.cloud.geminidataanalytics.v1beta.DataChatService.Chat"\n'
        "    }\n"
        "  },\n"
        "  {\n"
        '    "protoPayload": {\n'
        '      "serviceName": "geminidataanalytics.googleapis.com",\n'
        '      "methodName": "google.cloud.geminidataanalytics.v1beta.A2AService.Chat"\n'
        "    }\n"
        "  }\n"
        "]\n"
    )

    mock_proc = subprocess.CompletedProcess(
        args=["gcloud", "logging", "read"],
        returncode=0,
        stdout=raw_stdout,
        stderr="",
    )

    with patch("shutil.which", return_value="/usr/bin/gcloud"), patch("subprocess.run", return_value=mock_proc):
        tally = prove_audit_logs(project="test-project-123", lookback_days=14)

    assert tally == {
        "google.cloud.geminidataanalytics.v1beta.DataChatService.Chat": 1,
        "google.cloud.geminidataanalytics.v1beta.A2AService.Chat": 1,
    }


def test_bounded_live_job_polling() -> None:
    """Verifies that prove_live polls INFORMATION_SCHEMA until a job is found or timeout is reached."""
    mock_client = MagicMock(spec=bigquery.Client)
    mock_query_job_empty = MagicMock()
    mock_query_job_empty.result.return_value = []

    mock_query_job_found = MagicMock()
    mock_query_job_found.result.return_value = [
        {
            "job_id": "bqux_job_12345",
            "creation_time": "2026-11-13T10:00:00Z",
            "statement_type": "SELECT",
            "total_bytes_billed": 2048,
            "ca_bq_job": "true",
            "data_agent_id": "order_data_agent",
            "bqca_role": None,
        }
    ]

    mock_client.query.side_effect = [mock_query_job_empty, mock_query_job_found]

    mock_assessment = MagicMock()
    mock_assessment.tier.value = "TIER_1_VERIFIED_OR_COMPILED"
    mock_assessment.sub_mode = "AUTHORED_VERIFIED_QUERY"
    mock_assessment.final_sql = "SELECT 1"
    mock_assessment.reasons = ()

    with patch("scripts.verify_bqca_audit.create_chat_client"), \
         patch("scripts.verify_bqca_audit.stream_stateless_chat", return_value=mock_assessment), \
         patch("time.sleep", return_value=None):
        matched = prove_live(
            client=mock_client,
            project="test-project-123",
            agent="order_data_agent",
            question="How many orders were placed?",
            poll_timeout_seconds=6,
        )

    assert len(matched) == 1
    assert matched[0]["job_id"] == "bqux_job_12345"
    assert mock_client.query.call_count == 2
    # Verify the poll query uses the data-agent-id label filter
    call_args, _ = mock_client.query.call_args_list[0]
    poll_sql = call_args[0]
    assert "l.key = 'data-agent-id' AND l.value = @agent_id" in poll_sql


def test_prove_labels_handles_null_values() -> None:
    """Verifies that prove_labels handles None bytes and cost gracefully without formatting crash."""
    mock_client = MagicMock(spec=bigquery.Client)
    mock_query_job = MagicMock()
    mock_query_job.result.return_value = [
        {
            "data_agent_id": "null_test_agent",
            "bqca_role": None,
            "bqca_user_hash": None,
            "jobs": 1,
            "bytes_billed": None,
            "est_cost_usd": None,
        }
    ]
    mock_client.query.return_value = mock_query_job

    rows = prove_labels(
        client=mock_client,
        project="test-project-123",
        bq_region="region-us",
        lookback_days=30,
        tib_rate_usd=6.25,
    )
    assert len(rows) == 1
    assert rows[0]["data_agent_id"] == "null_test_agent"


def test_main_handles_google_api_call_error() -> None:
    """Verifies that GoogleAPICallError in prove_labels results in clean exit code 1."""
    import google.api_core.exceptions

    with patch("scripts.verify_bqca_audit.bigquery.Client"), \
         patch("scripts.verify_bqca_audit.prove_labels", side_effect=google.api_core.exceptions.GoogleAPICallError("Quota exceeded")):
        ret = main(["--project", "test-project-123"])
        assert ret == 1
