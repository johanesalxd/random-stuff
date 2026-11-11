"""Tests for semantic guardrails and dry-run policy enforcement."""

from __future__ import annotations

from pathlib import Path
import sys

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from semantic.execution import (  # noqa: E402
    AdkBigQueryExecutor,
    SqlExecutionError,
    build_sql_executor,
)
from semantic.guardrails import (  # noqa: E402
    DryRunSummary,
    SqlPolicyError,
    validate_dry_run_summary,
)


def test_validate_dry_run_summary_rejects_empty_sql() -> None:
    summary = DryRunSummary(
        statement_type="SELECT",
        referenced_sources=frozenset({"proj.ds.tbl"}),
        total_bytes_processed=100,
    )
    with pytest.raises(SqlPolicyError, match="cannot be empty"):
        validate_dry_run_summary("", summary)
    with pytest.raises(SqlPolicyError, match="cannot be empty"):
        validate_dry_run_summary("   \n\t  ", summary)


def test_validate_dry_run_summary_accepts_single_statement_with_trailing_semicolon() -> None:
    summary = DryRunSummary(
        statement_type="SELECT",
        referenced_sources=frozenset({"proj.ds.tbl"}),
        total_bytes_processed=100,
    )
    validate_dry_run_summary("SELECT 1 FROM `proj.ds.tbl`;", summary)
    validate_dry_run_summary(
        "SELECT 1 FROM `proj.ds.tbl`;  -- trailing comment\n",
        summary,
    )


def test_validate_dry_run_summary_rejects_multiple_statements() -> None:
    summary = DryRunSummary(
        statement_type="SELECT",
        referenced_sources=frozenset({"proj.ds.tbl"}),
        total_bytes_processed=100,
    )
    with pytest.raises(SqlPolicyError, match="Multiple SQL statements"):
        validate_dry_run_summary("SELECT 1; SELECT 2;", summary)
    with pytest.raises(SqlPolicyError, match="Multiple SQL statements"):
        validate_dry_run_summary("SELECT 1; DROP TABLE `proj.ds.tbl`;", summary)


def test_validate_dry_run_summary_enforces_select_only() -> None:
    summary = DryRunSummary(
        statement_type="INSERT",
        referenced_sources=frozenset({"proj.ds.tbl"}),
    )
    with pytest.raises(SqlPolicyError, match="Only SELECT queries are allowed"):
        validate_dry_run_summary("INSERT INTO `proj.ds.tbl` VALUES (1)", summary)

    empty_stmt_summary = DryRunSummary(statement_type="")
    with pytest.raises(SqlPolicyError, match="Only SELECT queries are allowed"):
        validate_dry_run_summary("SELECT 1", empty_stmt_summary)


def test_validate_dry_run_summary_enforces_allowed_sources() -> None:
    allowed = frozenset({"proj.ds.orders", "proj.ds.users"})

    # Empty referenced sources (tableless query or system probe)
    with pytest.raises(SqlPolicyError, match="did not reference any allowed source"):
        validate_dry_run_summary(
            "SELECT 1",
            DryRunSummary(statement_type="SELECT", referenced_sources=frozenset()),
            allowed_sources=allowed,
        )

    # Unauthorized table
    with pytest.raises(SqlPolicyError, match="unauthorized sources: \\['proj.ds.salary'\\]"):
        validate_dry_run_summary(
            "SELECT * FROM `proj.ds.salary`",
            DryRunSummary(
                statement_type="SELECT",
                referenced_sources=frozenset({"proj.ds.orders", "proj.ds.salary"}),
            ),
            allowed_sources=allowed,
        )

    # Valid subset of allowed sources
    validate_dry_run_summary(
        "SELECT * FROM `proj.ds.orders`",
        DryRunSummary(
            statement_type="SELECT",
            referenced_sources=frozenset({"proj.ds.orders"}),
        ),
        allowed_sources=allowed,
    )


def test_validate_dry_run_summary_enforces_max_bytes_billed() -> None:
    summary_over = DryRunSummary(
        statement_type="SELECT",
        referenced_sources=frozenset({"proj.ds.tbl"}),
        total_bytes_processed=5_000_000,
    )
    with pytest.raises(SqlPolicyError, match="Estimated query scan .* exceeds limit"):
        validate_dry_run_summary(
            "SELECT * FROM `proj.ds.tbl`",
            summary_over,
            max_bytes_billed=1_000_000,
        )

    summary_under = DryRunSummary(
        statement_type="SELECT",
        referenced_sources=frozenset({"proj.ds.tbl"}),
        total_bytes_processed=500_000,
    )
    validate_dry_run_summary(
        "SELECT * FROM `proj.ds.tbl`",
        summary_under,
        max_bytes_billed=1_000_000,
    )


def test_adk_bigquery_executor_rejects_multi_statement_before_dry_run() -> None:
    dry_run_called = False

    def fake_dry_run(sql: str) -> DryRunSummary:
        nonlocal dry_run_called
        dry_run_called = True
        return DryRunSummary(statement_type="SELECT")

    executor = AdkBigQueryExecutor(
        project="proj",
        allowed_sources=frozenset({"proj.ds.tbl"}),
        dry_run_fn=fake_dry_run,
        execute_fn=lambda **kwargs: {"status": "SUCCESS", "rows": []},
    )

    res = executor.execute("SELECT 1; SELECT 2;")
    assert not res.ok
    assert "SQL policy violation: Multiple SQL statements" in res.error
    assert not dry_run_called


def test_adk_bigquery_executor_blocks_unauthorized_sources_before_execution() -> None:
    execute_called = False

    def fake_execute(**kwargs):
        nonlocal execute_called
        execute_called = True
        return {"status": "SUCCESS", "rows": []}

    def fake_dry_run(sql: str) -> DryRunSummary:
        # Dry-run returns INFORMATION_SCHEMA table
        return DryRunSummary(
            statement_type="SELECT",
            referenced_sources=frozenset({"proj.ds.INFORMATION_SCHEMA.COLUMNS"}),
            total_bytes_processed=10_000,
        )

    executor = AdkBigQueryExecutor(
        project="proj",
        allowed_sources=frozenset({"proj.ds.orders"}),
        dry_run_fn=fake_dry_run,
        execute_fn=fake_execute,
    )

    res = executor.execute("SELECT * FROM `proj.ds.INFORMATION_SCHEMA.COLUMNS`")
    assert not res.ok
    assert "SQL policy violation" in res.error
    assert "unauthorized sources" in res.error
    assert not execute_called


def test_adk_bigquery_executor_blocks_byte_limit_exceeded() -> None:
    execute_called = False

    def fake_execute(**kwargs):
        nonlocal execute_called
        execute_called = True
        return {"status": "SUCCESS", "rows": []}

    def fake_dry_run(sql: str) -> DryRunSummary:
        return DryRunSummary(
            statement_type="SELECT",
            referenced_sources=frozenset({"proj.ds.orders"}),
            total_bytes_processed=50_000_000,
        )

    executor = AdkBigQueryExecutor(
        project="proj",
        allowed_sources=frozenset({"proj.ds.orders"}),
        max_bytes_billed=10_000_000,
        dry_run_fn=fake_dry_run,
        execute_fn=fake_execute,
    )

    res = executor.execute("SELECT * FROM `proj.ds.orders`")
    assert not res.ok
    assert "SQL policy violation" in res.error
    assert "exceeds limit (10000000 bytes)" in res.error
    assert not execute_called


def test_adk_bigquery_executor_reports_dry_run_failure() -> None:
    def fake_dry_run(sql: str) -> DryRunSummary:
        raise RuntimeError("dataset not found: 404")

    executor = AdkBigQueryExecutor(
        project="proj",
        allowed_sources=frozenset({"proj.ds.orders"}),
        dry_run_fn=fake_dry_run,
        execute_fn=lambda **kwargs: {"status": "SUCCESS", "rows": []},
    )

    res = executor.execute("SELECT * FROM `proj.ds.orders`")
    assert not res.ok
    assert "SQL dry-run failed: dataset not found: 404" in res.error
    assert "SQL policy violation" not in res.error


def test_build_sql_executor_prefers_alt_compute_project_and_parses_max_bytes(monkeypatch) -> None:
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "fallback-proj")
    monkeypatch.setenv("BQ_COMPUTE_PROJECT", "preferred-proj")
    monkeypatch.setenv("SQL_MAX_BYTES_BILLED", "10485760")

    executor = build_sql_executor(allowed_sources=frozenset({"p.d.t"}))
    assert isinstance(executor, AdkBigQueryExecutor)
    assert executor._project == "preferred-proj"
    assert executor._max_bytes_billed == 10_485_760
    assert executor._allowed_sources == frozenset({"p.d.t"})

    settings = executor._get_settings()
    assert settings.maximum_bytes_billed == 10_485_760


def test_build_sql_executor_rejects_invalid_max_bytes(monkeypatch) -> None:
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "proj")
    monkeypatch.setenv("SQL_MAX_BYTES_BILLED", "-50")
    with pytest.raises(SqlExecutionError, match="positive integer"):
        build_sql_executor()

    monkeypatch.setenv("SQL_MAX_BYTES_BILLED", "not-a-number")
    with pytest.raises(SqlExecutionError, match="positive integer"):
        build_sql_executor()
