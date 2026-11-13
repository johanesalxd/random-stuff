"""One-shot, read-only BigQuery execution for the V2 semantic workflow."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import os
from typing import Any, Callable, Protocol, runtime_checkable

from semantic.guardrails import (
    DryRunSummary,
    SqlPolicyError,
    validate_dry_run_summary,
)
from semantic.sql_lex import has_multiple_statements

_AUTH_MODE_ENV = "SQL_AUTH_MODE"
_MAX_ROWS_ENV = "SQL_MAX_RESULT_ROWS"
_LOCATION_ENV = "BIGQUERY_LOCATION"
_ALT_COMPUTE_PROJECT_ENV = "BQ_COMPUTE_PROJECT"
_COMPUTE_PROJECT_ENV = "GOOGLE_CLOUD_PROJECT"
_MAX_BYTES_ENV = "SQL_MAX_BYTES_BILLED"

ADC_AUTH_MODE = "adc"
USER_AUTH_MODE = "user"
IMPERSONATED_SA_AUTH_MODE = "impersonated_sa"
_DEFAULT_MAX_RESULT_ROWS = 50
_APPLICATION_NAME = "semantic-analytics"


class SqlExecutionError(ValueError):
    """Raised when SQL execution is unconfigured or unavailable."""


@dataclass(frozen=True)
class ExecResult:
    """Normalized result of one BigQuery execution."""

    status: str
    rows: tuple[dict[str, Any], ...] = ()
    row_count: int = 0
    truncated: bool = False
    error: str = ""

    @property
    def ok(self) -> bool:
        """Returns whether execution succeeded."""
        return self.status == "SUCCESS"

    def to_context(self) -> dict[str, Any]:
        """Returns a JSON-safe representation for workflow output."""
        context: dict[str, Any] = {
            "status": self.status,
            "rows": list(self.rows),
            "row_count": self.row_count,
            "truncated": self.truncated,
        }
        if self.error:
            context["error"] = self.error
        return context


@runtime_checkable
class SqlExecutor(Protocol):
    """Injectable boundary for one-shot BigQuery execution."""

    def execute(self, sql: str) -> ExecResult:
        """Executes SQL once and returns bounded rows or an error."""
        ...


class _ToolContextShim:
    """Minimal context required by the ADK BigQuery integration."""

    def __init__(self) -> None:
        self.state: dict[str, Any] = {}


class AdkBigQueryExecutor:
    """One-shot executor backed by ADK BigQuery ``execute_sql``."""

    def __init__(
        self,
        *,
        project: str,
        max_result_rows: int = _DEFAULT_MAX_RESULT_ROWS,
        location: str | None = None,
        credentials: Any = None,
        execute_fn: Callable[..., dict[str, Any]] | None = None,
        allowed_sources: frozenset[str] | None = None,
        max_bytes_billed: int | None = None,
        dry_run_fn: Callable[[str], DryRunSummary] | None = None,
        require_explicit_credentials: bool = False,
        job_labels: Mapping[str, str] | None = None,
    ):
        self._project = project
        self._max_result_rows = max_result_rows
        self._location = location
        self._credentials = credentials
        self._execute_fn = execute_fn
        self._allowed_sources = allowed_sources
        self._max_bytes_billed = max_bytes_billed
        self._dry_run_fn = dry_run_fn
        self._require_explicit_credentials = require_explicit_credentials
        self._job_labels = dict(job_labels) if job_labels else None
        self._settings_obj: Any = None

    def execute(self, sql: str) -> ExecResult:
        """Executes SQL once through the read-only ADK integration."""
        if self._allowed_sources is not None or self._max_bytes_billed is not None:
            try:
                self._enforce_guardrails(sql)
            except SqlPolicyError as error:
                return ExecResult(status="ERROR", error=f"SQL policy violation: {error}")
            except Exception as error:
                return ExecResult(status="ERROR", error=f"SQL dry-run failed: {error}")

        try:
            raw = self._get_execute_fn()(
                project_id=self._project,
                query=sql,
                credentials=self._get_credentials(),
                settings=self._get_settings(),
                tool_context=_ToolContextShim(),
                dry_run=False,
            )
        except Exception as error:  # pragma: no cover - defensive provider boundary
            return ExecResult(status="ERROR", error=str(error))
        return _map_result(raw, max_result_rows=self._max_result_rows)

    def _enforce_guardrails(self, sql: str) -> None:
        if not sql or not sql.strip():
            raise SqlPolicyError("SQL query cannot be empty")
        if has_multiple_statements(sql):
            raise SqlPolicyError("Multiple SQL statements are not allowed")

        if self._dry_run_fn is not None:
            summary = self._dry_run_fn(sql)
        else:
            try:
                from google.cloud import bigquery
            except ImportError as error:  # pragma: no cover - dependency guard
                raise SqlExecutionError(
                    "google-cloud-bigquery is required for dry-run guardrails"
                ) from error
            client = bigquery.Client(
                project=self._project,
                credentials=self._get_credentials(),
                location=self._location,
            )
            job_kwargs: dict[str, Any] = {
                "dry_run": True,
                "use_query_cache": False,
            }
            if self._job_labels:
                job_kwargs["labels"] = dict(self._job_labels)
            job = client.query(
                sql,
                job_config=bigquery.QueryJobConfig(**job_kwargs),
            )
            summary = DryRunSummary(
                statement_type=str(job.statement_type or ""),
                referenced_sources=frozenset(
                    f"{t.project}.{t.dataset_id}.{t.table_id}"
                    for t in (job.referenced_tables or ())
                ),
                total_bytes_processed=int(job.total_bytes_processed or 0),
            )
        validate_dry_run_summary(
            sql,
            summary,
            allowed_sources=self._allowed_sources,
            max_bytes_billed=self._max_bytes_billed,
        )

    def _get_execute_fn(self) -> Callable[..., dict[str, Any]]:
        if self._execute_fn is None:
            try:
                from google.adk.integrations.bigquery import query_tool
            except ImportError as error:  # pragma: no cover - dependency guard
                raise SqlExecutionError(
                    "google-adk is required for live SQL execution"
                ) from error
            self._execute_fn = query_tool.execute_sql
        return self._execute_fn

    def _get_credentials(self) -> Any:
        if self._credentials is None:
            if self._require_explicit_credentials:
                raise SqlExecutionError(
                    "explicit credentials are required when SQL_AUTH_MODE is not 'adc'"
                )
            try:
                import google.auth
            except ImportError as error:  # pragma: no cover - dependency guard
                raise SqlExecutionError(
                    "google-auth is required for live SQL execution"
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
                    "google-adk is required for live SQL execution"
                ) from error
            kwargs: dict[str, Any] = {
                "write_mode": WriteMode.BLOCKED,
                "max_query_result_rows": self._max_result_rows,
                "compute_project_id": self._project,
                "location": self._location,
                "application_name": _APPLICATION_NAME,
            }
            if self._max_bytes_billed is not None:
                kwargs["maximum_bytes_billed"] = self._max_bytes_billed
            if self._job_labels:
                kwargs["job_labels"] = dict(self._job_labels)
            self._settings_obj = BigQueryToolConfig(**kwargs)
        return self._settings_obj


def resolve_auth_mode(raw: str | None = None) -> str:
    """Returns the configured execution identity mode.

    Args:
        raw: Explicit mode override. When omitted, reads ``SQL_AUTH_MODE``.

    Returns:
        ``adc``, ``user``, or ``impersonated_sa``.

    Raises:
        SqlExecutionError: If the configured mode is unknown.
    """
    value = raw if raw is not None else os.getenv(_AUTH_MODE_ENV, ADC_AUTH_MODE)
    mode = value.strip().lower()
    if mode not in {ADC_AUTH_MODE, USER_AUTH_MODE, IMPERSONATED_SA_AUTH_MODE}:
        raise SqlExecutionError(f"unsupported SQL_AUTH_MODE: {value!r}")
    return mode


def build_sql_executor(
    *,
    access_token: str | None = None,
    auth_mode: str | None = None,
    allowed_sources: frozenset[str] | None = None,
    impersonated_credentials: Any = None,
    job_labels: Mapping[str, str] | None = None,
) -> SqlExecutor:
    """Builds the configured one-shot BigQuery executor.

    Args:
        access_token: End-user OAuth token required in ``user`` mode.
        auth_mode: Optional mode override.
        allowed_sources: Optional set of allowed fully-qualified source tables.
        impersonated_credentials: Verified impersonated credentials for ``impersonated_sa`` mode.
        job_labels: Optional BigQuery job labels to attach to queries.

    Returns:
        A configured :class:`AdkBigQueryExecutor`.

    Raises:
        SqlExecutionError: If project or user credentials are missing.
    """
    project = (
        os.getenv(_ALT_COMPUTE_PROJECT_ENV)
        or os.getenv(_COMPUTE_PROJECT_ENV)
        or ""
    ).strip()
    if not project:
        raise SqlExecutionError(
            f"{_COMPUTE_PROJECT_ENV} or {_ALT_COMPUTE_PROJECT_ENV} must be set to build the SQL executor"
        )
    mode = resolve_auth_mode(auth_mode)
    credentials: Any = None
    require_explicit_credentials = False
    if mode == USER_AUTH_MODE:
        if not access_token:
            raise SqlExecutionError(
                "user auth mode requires a per-request OAuth access token"
            )
        credentials = _build_user_credentials(access_token)
        require_explicit_credentials = True
    elif mode == IMPERSONATED_SA_AUTH_MODE:
        if impersonated_credentials is None:
            raise SqlExecutionError(
                "impersonated_sa auth mode requires verified impersonated credentials"
            )
        credentials = impersonated_credentials
        require_explicit_credentials = True
    elif mode == ADC_AUTH_MODE:
        require_explicit_credentials = False

    max_bytes = _optional_positive_int_env(_MAX_BYTES_ENV)
    return AdkBigQueryExecutor(
        project=project,
        max_result_rows=_positive_int_env(
            _MAX_ROWS_ENV,
            _DEFAULT_MAX_RESULT_ROWS,
        ),
        location=os.getenv(_LOCATION_ENV, "").strip() or None,
        credentials=credentials,
        allowed_sources=allowed_sources,
        max_bytes_billed=max_bytes,
        require_explicit_credentials=require_explicit_credentials,
        job_labels=job_labels,
    )


def _build_user_credentials(access_token: str) -> Any:
    try:
        from google.oauth2.credentials import Credentials
    except ImportError as error:  # pragma: no cover - dependency guard
        raise SqlExecutionError(
            "google-auth is required for user-token execution"
        ) from error
    return Credentials(token=access_token)


def _map_result(raw: dict[str, Any], *, max_result_rows: int) -> ExecResult:
    if not isinstance(raw, dict):
        return ExecResult(status="ERROR", error="unexpected executor result")
    if raw.get("status") != "SUCCESS":
        return ExecResult(
            status="ERROR",
            error=str(raw.get("error_details", "unknown execution error")),
        )
    raw_rows = tuple(raw.get("rows", []) or ())
    rows = raw_rows[:max_result_rows]
    truncated = bool(raw.get("result_is_likely_truncated", False)) or (
        len(raw_rows) > max_result_rows
    )
    return ExecResult(
        status="SUCCESS",
        rows=rows,
        row_count=len(rows),
        truncated=truncated,
    )


def _positive_int_env(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return value if value > 0 else default


def _optional_positive_int_env(name: str) -> int | None:
    raw = os.getenv(name, "").strip()
    if not raw:
        return None
    try:
        value = int(raw)
    except ValueError as error:
        raise SqlExecutionError(
            f"{name} must be a positive integer; received {raw!r}"
        ) from error
    if value <= 0:
        raise SqlExecutionError(
            f"{name} must be a positive integer; received {raw!r}"
        )
    return value
