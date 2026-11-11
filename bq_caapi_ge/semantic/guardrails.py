"""Runtime SQL policy and dry-run guardrails.

This module MUST NOT import google.adk, pydantic, flask, or google.cloud.dataplex
at top level so core-only base installs can import it cleanly.
"""

from __future__ import annotations

from dataclasses import dataclass

from semantic.sql_lex import has_multiple_statements


class SqlPolicyError(ValueError):
    """Raised when a SQL query violates runtime security or resource policy."""


@dataclass(frozen=True)
class DryRunSummary:
    """Telemetry extracted from a BigQuery dry-run job."""

    statement_type: str
    referenced_sources: frozenset[str] = frozenset()
    total_bytes_processed: int = 0


def validate_dry_run_summary(
    sql: str,
    summary: DryRunSummary,
    *,
    allowed_sources: frozenset[str] | None = None,
    max_bytes_billed: int | None = None,
) -> None:
    """Validates dry-run telemetry against allowed sources and scan limits.

    Args:
        sql: The raw SQL string to validate.
        summary: Dry-run telemetry from BigQuery.
        allowed_sources: Optional set of allowed fully-qualified table names
            (`project.dataset.table`). If provided, queries referencing
            unauthorized tables or queries with no referenced tables are rejected.
        max_bytes_billed: Optional byte scan ceiling. If provided, queries whose
            estimated total_bytes_processed exceeds this are rejected.

    Raises:
        SqlPolicyError: If the SQL or dry-run summary violates policy.
    """
    if not sql or not sql.strip():
        raise SqlPolicyError("SQL query cannot be empty")

    if has_multiple_statements(sql):
        raise SqlPolicyError("Multiple SQL statements are not allowed")

    statement_type = (summary.statement_type or "").strip().upper()
    if statement_type != "SELECT":
        raise SqlPolicyError(
            f"Only SELECT queries are allowed; received statement_type: {statement_type or 'UNKNOWN'!r}"
        )

    if allowed_sources is not None:
        if not summary.referenced_sources:
            raise SqlPolicyError("Query did not reference any allowed source table")
        unauthorized = sorted(summary.referenced_sources - allowed_sources)
        if unauthorized:
            raise SqlPolicyError(f"Query references unauthorized sources: {unauthorized}")

    if max_bytes_billed is not None and summary.total_bytes_processed > max_bytes_billed:
        raise SqlPolicyError(
            f"Estimated query scan ({summary.total_bytes_processed} bytes) exceeds limit ({max_bytes_billed} bytes)"
        )
