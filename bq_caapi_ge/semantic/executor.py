"""BigQuery developer execution for contract-validated semantic queries."""

from __future__ import annotations

import datetime as dt
import decimal
import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from semantic.types import CompiledQuery, QueryParameter


class ExecutionError(RuntimeError):
    """Raised when a contract-validated query cannot execute."""


@dataclass(frozen=True)
class ExecutionResult:
    """BigQuery developer execution result returned to the ADK workflow."""

    rows: tuple[dict[str, Any], ...]
    job_id: str | None
    execution_mode: str
    truncation_status: str = "unknown"


@dataclass
class _ReadOnlyToolContext:
    """Minimal context required by the lower-level read-only ADK query helper."""

    state: dict[str, Any] = field(default_factory=dict)


def execute_adk_bigquery_adc_query(
    compiled: CompiledQuery,
    *,
    project: str | None,
    location: str | None = None,
    max_results: int = 100,
    maximum_bytes_billed: int | None = None,
    credentials: Any | None = None,
    dry_run: bool = False,
    execute_sql_tool: Any | None = None,
) -> ExecutionResult:
    """Executes a compiled query through ADK's BigQuery integration.

    Args:
        compiled: Contract-compiled SQL and query parameters.
        project: Google Cloud project used for BigQuery compute and billing.
        location: Optional BigQuery job location.
        max_results: Maximum rows to return from the ADK BigQuery tool.
        maximum_bytes_billed: Optional maximum bytes billed for the query.
        credentials: Optional Google credentials, primarily for tests.
        dry_run: If true, validate and estimate without executing the query.
        execute_sql_tool: Optional execute_sql-compatible callable for tests.

    Returns:
        Query rows and ADK-native execution metadata.

    Raises:
        ExecutionError: If the query cannot execute through ADK BigQuery tools.
    """
    if not compiled.compiled_from_contract:
        raise ExecutionError("only contract-compiled queries can execute")
    if compiled.parameters:
        raise ExecutionError(
            "lower-level ADK BigQuery execution does not support compiled query "
            "parameters yet"
        )
    if not project:
        raise ExecutionError(
            "GOOGLE_CLOUD_PROJECT must be set for ADK BigQuery execution"
        )
    _validate_max_results(max_results)
    _validate_maximum_bytes_billed(maximum_bytes_billed)

    try:
        import google.auth
        from google.adk.integrations.bigquery import query_tool
        from google.adk.integrations.bigquery.bigquery_credentials import (
            BIGQUERY_SCOPES,
        )
        from google.adk.integrations.bigquery.config import (
            BigQueryToolConfig,
            WriteMode,
        )

        query_credentials = (
            credentials or google.auth.default(scopes=BIGQUERY_SCOPES)[0]
        )
        settings = BigQueryToolConfig(
            write_mode=WriteMode.BLOCKED,
            maximum_bytes_billed=maximum_bytes_billed,
            max_query_result_rows=max_results,
            application_name="bq-caapi-legacy-contract-compiler",
            compute_project_id=project,
            location=location,
            job_labels={"semantic_contract_compiled": "true"},
        )
        execute_sql = execute_sql_tool or query_tool.get_execute_sql(settings)
        result = execute_sql(
            project_id=project,
            query=compiled.sql,
            credentials=query_credentials,
            settings=settings,
            tool_context=_ReadOnlyToolContext(),
            dry_run=dry_run,
        )
        if not isinstance(result, dict):
            raise ExecutionError("ADK BigQuery returned a malformed response")
        if result.get("status") != "SUCCESS":
            error_details = result.get("error_details", "unknown ADK BigQuery error")
            raise ExecutionError(f"ADK BigQuery execution failed: {error_details}")
        rows = result.get("rows", [])
        if not isinstance(rows, list):
            raise ExecutionError("ADK BigQuery returned malformed rows")
        if len(rows) > max_results:
            raise ExecutionError("ADK BigQuery returned more rows than requested")
        if any(not isinstance(row, dict) for row in rows):
            raise ExecutionError("ADK BigQuery returned a malformed row")
        safe_rows = tuple(_json_safe(row) for row in rows)
        json.dumps(safe_rows)
        return ExecutionResult(
            rows=safe_rows,
            job_id=_job_id_from_adk_result(result),
            execution_mode="adk_bigquery_adc",
            truncation_status=(
                "possible" if result.get("result_is_likely_truncated") else "none"
            ),
        )
    except ExecutionError:
        raise
    except Exception as error:
        raise ExecutionError(
            f"failed to execute contract-validated query with ADK BigQuery: {error}"
        ) from error


def execute_adc_developer_query(
    compiled: CompiledQuery,
    *,
    client: Any | None = None,
    project: str | None = None,
    location: str | None = None,
    max_results: int = 100,
    maximum_bytes_billed: int | None = None,
) -> ExecutionResult:
    """Executes a compiled query with local Application Default Credentials.

    Args:
        compiled: Contract-compiled SQL and query parameters.
        client: Optional BigQuery client, primarily for tests.
        project: Optional Google Cloud project for the BigQuery client.
        location: Optional BigQuery job location.
        max_results: Maximum rows to materialize for the response.
        maximum_bytes_billed: Optional maximum bytes billed for the query.

    Returns:
        Query rows, job ID, and execution mode metadata.

    Raises:
        ExecutionError: If the query is not validated or execution fails.
    """
    if not compiled.compiled_from_contract:
        raise ExecutionError("only contract-compiled queries can execute")
    _validate_max_results(max_results)
    _validate_maximum_bytes_billed(maximum_bytes_billed)

    try:
        from google.cloud import bigquery

        query_client = client or bigquery.Client(project=project, location=location)
        query_parameters = _to_bigquery_parameters(compiled.parameters)
        dry_run_config = bigquery.QueryJobConfig(
            query_parameters=query_parameters,
            maximum_bytes_billed=maximum_bytes_billed,
            dry_run=True,
        )
        dry_run_job = query_client.query(
            compiled.sql,
            job_config=dry_run_config,
            location=location,
        )
        if dry_run_job.statement_type != "SELECT":
            raise ExecutionError("developer execution only supports SELECT statements")

        job_config = bigquery.QueryJobConfig(
            query_parameters=query_parameters,
            maximum_bytes_billed=maximum_bytes_billed,
        )
        query_job = query_client.query(
            compiled.sql,
            job_config=job_config,
            location=location,
        )
        row_iterator = query_job.result(max_results=max_results)
        rows = tuple(_row_to_dict(row) for row in row_iterator)
        if len(rows) > max_results:
            raise ExecutionError("BigQuery returned more rows than requested")
        json.dumps(rows)
        total_rows = getattr(row_iterator, "total_rows", None)
        return ExecutionResult(
            rows=rows,
            job_id=query_job.job_id,
            execution_mode="adc_developer",
            truncation_status=(
                "confirmed"
                if isinstance(total_rows, int) and total_rows > len(rows)
                else "none"
                if isinstance(total_rows, int)
                else "unknown"
            ),
        )
    except ExecutionError:
        raise
    except Exception as error:
        raise ExecutionError(
            f"failed to execute contract-validated query: {error}"
        ) from error


def _to_bigquery_parameters(
    parameters: tuple[QueryParameter, ...],
) -> list[Any]:
    return [_to_bigquery_parameter(parameter) for parameter in parameters]


def _to_bigquery_parameter(
    parameter: QueryParameter,
) -> Any:
    from google.cloud import bigquery

    value = parameter.value
    if isinstance(value, list):
        if not value:
            raise ExecutionError(
                f"array query parameter {parameter.name} must not be empty"
            )
        parameter_types = {_parameter_type(item) for item in value}
        if len(parameter_types) != 1:
            raise ExecutionError(
                f"array query parameter {parameter.name} must contain one value type"
            )
        return bigquery.ArrayQueryParameter(
            parameter.name,
            parameter_types.pop(),
            value,
        )
    return bigquery.ScalarQueryParameter(
        parameter.name,
        _parameter_type(value),
        value,
    )


def _parameter_type(value: Any) -> str:
    if isinstance(value, bool):
        return "BOOL"
    if isinstance(value, int):
        return "INT64"
    if isinstance(value, float):
        return "FLOAT64"
    if isinstance(value, str):
        return "STRING"
    raise ExecutionError(f"unsupported query parameter type: {type(value).__name__}")


def _validate_maximum_bytes_billed(maximum_bytes_billed: int | None) -> None:
    if maximum_bytes_billed is None:
        return
    if maximum_bytes_billed < 10_485_760:
        raise ExecutionError("maximum_bytes_billed must be at least 10485760")


def _validate_max_results(max_results: int) -> None:
    if isinstance(max_results, bool) or not 1 <= max_results <= 1000:
        raise ExecutionError("max_results must be between 1 and 1000")


def _row_to_dict(row: Any) -> dict[str, Any]:
    return {key: _json_safe(value) for key, value in dict(row.items()).items()}


def _job_id_from_adk_result(result: dict[str, Any]) -> str | None:
    dry_run_info = result.get("dry_run_info", {})
    if not isinstance(dry_run_info, dict):
        raise ExecutionError("ADK BigQuery returned malformed dry-run metadata")
    job_reference = dry_run_info.get("jobReference", {})
    if not isinstance(job_reference, dict):
        raise ExecutionError("ADK BigQuery returned a malformed job reference")
    job_id = job_reference.get("jobId")
    if job_id is None:
        return None
    if not isinstance(job_id, str):
        raise ExecutionError("ADK BigQuery returned a malformed job ID")
    return job_id


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, bool | int | float | str):
        return value
    if isinstance(value, decimal.Decimal):
        return str(value)
    if isinstance(value, dt.datetime | dt.date | dt.time):
        return value.isoformat()
    if isinstance(value, dt.timedelta):
        return str(value)
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if hasattr(value, "items"):
        return {str(key): _json_safe(item) for key, item in value.items()}
    return str(value)
