"""One-shot, read-only BigQuery execution for the V2 semantic workflow."""

from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Any, Callable, Protocol, runtime_checkable

_AUTH_MODE_ENV = "SQL_AUTH_MODE"
_MAX_ROWS_ENV = "SQL_MAX_RESULT_ROWS"
_LOCATION_ENV = "BIGQUERY_LOCATION"
_COMPUTE_PROJECT_ENV = "GOOGLE_CLOUD_PROJECT"

ADC_AUTH_MODE = "adc"
USER_AUTH_MODE = "user"
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
    ):
        self._project = project
        self._max_result_rows = max_result_rows
        self._location = location
        self._credentials = credentials
        self._execute_fn = execute_fn
        self._settings_obj: Any = None

    def execute(self, sql: str) -> ExecResult:
        """Executes SQL once through the read-only ADK integration."""
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
            self._settings_obj = BigQueryToolConfig(
                write_mode=WriteMode.BLOCKED,
                max_query_result_rows=self._max_result_rows,
                compute_project_id=self._project,
                location=self._location,
                application_name=_APPLICATION_NAME,
            )
        return self._settings_obj


def resolve_auth_mode(raw: str | None = None) -> str:
    """Returns the configured execution identity mode.

    Args:
        raw: Explicit mode override. When omitted, reads ``SQL_AUTH_MODE``.

    Returns:
        ``adc`` or ``user``.

    Raises:
        SqlExecutionError: If the configured mode is unknown.
    """
    value = raw if raw is not None else os.getenv(_AUTH_MODE_ENV, ADC_AUTH_MODE)
    mode = value.strip().lower()
    if mode not in {ADC_AUTH_MODE, USER_AUTH_MODE}:
        raise SqlExecutionError(f"unsupported SQL_AUTH_MODE: {value!r}")
    return mode


def build_sql_executor(
    *, access_token: str | None = None, auth_mode: str | None = None
) -> SqlExecutor:
    """Builds the configured one-shot BigQuery executor.

    Args:
        access_token: End-user OAuth token required in ``user`` mode.
        auth_mode: Optional mode override.

    Returns:
        A configured :class:`AdkBigQueryExecutor`.

    Raises:
        SqlExecutionError: If project or user credentials are missing.
    """
    project = os.getenv(_COMPUTE_PROJECT_ENV, "").strip()
    if not project:
        raise SqlExecutionError(
            f"{_COMPUTE_PROJECT_ENV} must be set to build the SQL executor"
        )
    mode = resolve_auth_mode(auth_mode)
    credentials: Any = None
    if mode == USER_AUTH_MODE:
        if not access_token:
            raise SqlExecutionError(
                "user auth mode requires a per-request OAuth access token"
            )
        credentials = _build_user_credentials(access_token)
    return AdkBigQueryExecutor(
        project=project,
        max_result_rows=_positive_int_env(
            _MAX_ROWS_ENV,
            _DEFAULT_MAX_RESULT_ROWS,
        ),
        location=os.getenv(_LOCATION_ENV, "").strip() or None,
        credentials=credentials,
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
