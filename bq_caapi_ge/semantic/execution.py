"""Guarded BigQuery execution boundary for Phase 8.

Execution is delegated to the ADK BigQuery tool (`execute_sql`) configured in
read-only mode, which enforces `SELECT`-only access, a maximum bytes-billed cost
cap, a maximum result-row cap, and dry-run validation. This module wraps that tool
behind an injectable :class:`SqlExecutor` boundary so the workflow stays
deterministic and unit tests inject fakes without live calls.

Execution mode is fail-safe: the default is plan mode (dry run only). Real query
execution occurs only when ``SQL_EXECUTION_MODE`` is explicitly set to
``developer``, and always with Application Default Credentials.
"""

from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Any, Callable, Protocol, runtime_checkable

_EXECUTION_MODE_ENV = "SQL_EXECUTION_MODE"
_MAX_BYTES_ENV = "SQL_MAX_BYTES_BILLED"
_MAX_ROWS_ENV = "SQL_MAX_RESULT_ROWS"
_LOCATION_ENV = "BIGQUERY_LOCATION"
_COMPUTE_PROJECT_ENV = "GOOGLE_CLOUD_PROJECT"

PLAN_MODE = "plan"
DEVELOPER_MODE = "developer"
_DEFAULT_MAX_RESULT_ROWS = 50
_APPLICATION_NAME = "semantic-analytics"


class SqlExecutionError(ValueError):
    """Raised when the executor is unconfigured or unavailable."""


@dataclass(frozen=True)
class ExecResult:
    """Normalized result of a dry run or execution."""

    status: str
    mode: str
    rows: tuple[dict[str, Any], ...] = ()
    row_count: int = 0
    truncated: bool = False
    total_bytes_processed: int | None = None
    error: str = ""

    @property
    def ok(self) -> bool:
        """Returns whether the operation succeeded."""
        return self.status == "SUCCESS"

    def to_context(self) -> dict[str, Any]:
        """Returns a JSON-safe representation for provenance payloads."""
        context: dict[str, Any] = {
            "status": self.status,
            "mode": self.mode,
            "row_count": self.row_count,
            "truncated": self.truncated,
            "total_bytes_processed": self.total_bytes_processed,
        }
        if self.error:
            context["error"] = self.error
        if self.mode == DEVELOPER_MODE:
            context["rows"] = list(self.rows)
        return context


@runtime_checkable
class SqlExecutor(Protocol):
    """Injectable boundary for guarded, read-only BigQuery access."""

    def dry_run(self, sql: str) -> ExecResult:
        """Validates a query and estimates cost without executing it."""
        ...

    def execute(self, sql: str) -> ExecResult:
        """Executes a read-only query and returns bounded rows."""
        ...


class _ToolContextShim:
    """Minimal stand-in for ADK ToolContext.

    The ADK read-only (BLOCKED) and dry-run paths never read the tool context; it
    is used only by protected write mode, which this executor does not enable.
    """

    def __init__(self) -> None:
        self.state: dict[str, Any] = {}


class AdkBigQueryExecutor:
    """Read-only executor backed by the ADK BigQuery `execute_sql` tool."""

    def __init__(
        self,
        *,
        project: str,
        max_bytes_billed: int | None = None,
        max_result_rows: int = _DEFAULT_MAX_RESULT_ROWS,
        location: str | None = None,
        credentials: Any = None,
        execute_fn: Callable[..., dict[str, Any]] | None = None,
    ):
        self._project = project
        self._max_bytes_billed = max_bytes_billed
        self._max_result_rows = max_result_rows
        self._location = location
        self._credentials = credentials
        self._execute_fn = execute_fn
        self._settings_obj: Any = None

    def dry_run(self, sql: str) -> ExecResult:
        return self._run(sql, dry_run=True, mode=PLAN_MODE)

    def execute(self, sql: str) -> ExecResult:
        return self._run(sql, dry_run=False, mode=DEVELOPER_MODE)

    def _run(self, sql: str, *, dry_run: bool, mode: str) -> ExecResult:
        execute_fn = self._get_execute_fn()
        try:
            raw = execute_fn(
                project_id=self._project,
                query=sql,
                credentials=self._get_credentials(),
                settings=self._get_settings(),
                tool_context=_ToolContextShim(),
                dry_run=dry_run,
            )
        except Exception as error:  # pragma: no cover - defensive; ADK returns dicts
            return ExecResult(status="ERROR", mode=mode, error=str(error))
        return _map_result(raw, mode=mode)

    def _get_execute_fn(self) -> Callable[..., dict[str, Any]]:
        if self._execute_fn is None:
            try:
                from google.adk.integrations.bigquery import query_tool
            except ImportError as error:  # pragma: no cover - dependency guard
                raise SqlExecutionError(
                    "google-adk is required for the live SQL executor"
                ) from error
            self._execute_fn = query_tool.execute_sql
        return self._execute_fn

    def _get_credentials(self) -> Any:
        if self._credentials is None:
            try:
                import google.auth
            except ImportError as error:  # pragma: no cover - dependency guard
                raise SqlExecutionError(
                    "google-auth is required for the live SQL executor"
                ) from error
            self._credentials, _ = google.auth.default()
        return self._credentials

    def _get_settings(self) -> Any:
        if self._settings_obj is None:
            try:
                from google.adk.integrations.bigquery.config import (
                    BigQueryToolConfig,
                    WriteMode,
                )
            except ImportError as error:  # pragma: no cover - dependency guard
                raise SqlExecutionError(
                    "google-adk is required for the live SQL executor"
                ) from error
            self._settings_obj = BigQueryToolConfig(
                write_mode=WriteMode.BLOCKED,
                maximum_bytes_billed=self._max_bytes_billed,
                max_query_result_rows=self._max_result_rows,
                compute_project_id=self._project,
                location=self._location,
                application_name=_APPLICATION_NAME,
            )
        return self._settings_obj


def resolve_execution_mode(raw: str | None = None) -> str:
    """Returns the effective execution mode, defaulting to plan (dry run only)."""
    value = raw if raw is not None else os.getenv(_EXECUTION_MODE_ENV, PLAN_MODE)
    return DEVELOPER_MODE if value.strip().lower() == DEVELOPER_MODE else PLAN_MODE


def build_sql_executor() -> SqlExecutor:
    """Returns the configured live read-only executor.

    Raises:
        SqlExecutionError: If the compute project is not configured.
    """
    project = os.getenv(_COMPUTE_PROJECT_ENV, "").strip()
    if not project:
        raise SqlExecutionError(
            f"{_COMPUTE_PROJECT_ENV} must be set to build the SQL executor"
        )
    return AdkBigQueryExecutor(
        project=project,
        max_bytes_billed=_int_env(_MAX_BYTES_ENV),
        max_result_rows=_int_env(_MAX_ROWS_ENV, _DEFAULT_MAX_RESULT_ROWS)
        or _DEFAULT_MAX_RESULT_ROWS,
        location=os.getenv(_LOCATION_ENV, "").strip() or None,
    )


def _map_result(raw: dict[str, Any], *, mode: str) -> ExecResult:
    if not isinstance(raw, dict):
        return ExecResult(status="ERROR", mode=mode, error="unexpected executor result")
    if raw.get("status") != "SUCCESS":
        return ExecResult(
            status="ERROR",
            mode=mode,
            error=str(raw.get("error_details", "unknown execution error")),
        )
    if "dry_run_info" in raw:
        return ExecResult(
            status="SUCCESS",
            mode=mode,
            total_bytes_processed=_extract_bytes(raw.get("dry_run_info")),
        )
    rows = tuple(raw.get("rows", []) or ())
    return ExecResult(
        status="SUCCESS",
        mode=mode,
        rows=rows,
        row_count=len(rows),
        truncated=bool(raw.get("result_is_likely_truncated", False)),
    )


def _extract_bytes(dry_run_info: Any) -> int | None:
    if not isinstance(dry_run_info, dict):
        return None
    statistics = dry_run_info.get("statistics")
    if isinstance(statistics, dict):
        for key in ("totalBytesProcessed", "totalBytesBilled"):
            value = statistics.get(key)
            if value is not None:
                return _to_int(value)
        query_stats = statistics.get("query")
        if isinstance(query_stats, dict):
            value = query_stats.get("totalBytesProcessed")
            if value is not None:
                return _to_int(value)
    return None


def _to_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _int_env(name: str, default: int | None = None) -> int | None:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default
