"""Tests for certified BigQuery query execution."""

from __future__ import annotations

import datetime as dt
import decimal
import sys
from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("google.adk")
pytest.importorskip("google.cloud.bigquery")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from semantic.executor import (  # noqa: E402
    ExecutionError,
    execute_adc_developer_query,
    execute_adk_bigquery_adc_query,
)
from semantic.types import CompiledQuery, QueryParameter  # noqa: E402


class _FakeRow:
    def __init__(self, values: dict[str, Any]):
        self._values = values

    def items(self):
        return self._values.items()


class _FakeRowIterator(list):
    def __init__(self, rows: list[_FakeRow], total_rows: int):
        super().__init__(rows)
        self.total_rows = total_rows


class _FakeQueryJob:
    job_id = "job_123"

    def __init__(
        self,
        rows: list[_FakeRow],
        total_rows: int | None = None,
        expose_total_rows: bool = True,
    ):
        self._rows = rows
        self._total_rows = total_rows if total_rows is not None else len(rows)
        self._expose_total_rows = expose_total_rows
        self.max_results = None

    def result(self, max_results: int):
        self.max_results = max_results
        if not self._expose_total_rows:
            return list(self._rows)
        return _FakeRowIterator(self._rows, self._total_rows)


class _FakeDryRunJob:
    def __init__(self, statement_type: str):
        self.statement_type = statement_type


class _FakeClient:
    def __init__(self, query_job: _FakeQueryJob, statement_type: str = "SELECT"):
        self.query_job = query_job
        self.statement_type = statement_type
        self.sql = None
        self.job_config = None
        self.location = None
        self.query_count = 0

    def query(self, sql: str, job_config: Any, location: str | None):
        self.query_count += 1
        self.sql = sql
        self.location = location
        if job_config.dry_run:
            return _FakeDryRunJob(self.statement_type)
        self.job_config = job_config
        return self.query_job


def test_execute_adc_developer_query_runs_contract_sql_with_parameters():
    """Tests developer execution passes SQL, parameters, and location to BQ."""
    compiled = CompiledQuery(
        sql="SELECT @p1_country AS country",
        parameters=(QueryParameter("p1_country", "US"),),
        metric="completed_order_count",
        dimensions=("country",),
        contract_version="thelook_ecommerce:v1",
        contract_certified=True,
    )
    query_job = _FakeQueryJob([_FakeRow({"country": "US"})])
    client = _FakeClient(query_job)

    result = execute_adc_developer_query(
        compiled,
        client=client,
        location="us",
        max_results=25,
        maximum_bytes_billed=10_485_760,
    )

    assert client.sql == compiled.sql
    assert client.query_count == 2
    assert client.location == "us"
    assert query_job.max_results == 25
    assert result.job_id == "job_123"
    assert result.execution_mode == "adc_developer"
    assert result.rows == ({"country": "US"},)
    assert client.job_config.query_parameters[0].name == "p1_country"
    assert client.job_config.query_parameters[0].type_ == "STRING"
    assert client.job_config.query_parameters[0].value == "US"
    assert client.job_config.maximum_bytes_billed == 10_485_760
    assert result.truncation_status == "none"


def test_execute_adc_developer_query_serializes_rows_for_adk_output():
    """Tests BigQuery row values are converted into JSON-safe values."""
    compiled = CompiledQuery(
        sql="SELECT 1",
        parameters=(),
        metric="completed_revenue",
        dimensions=(),
        contract_version="thelook_ecommerce:v1",
        contract_certified=True,
    )
    query_job = _FakeQueryJob(
        [
            _FakeRow(
                {
                    "revenue": decimal.Decimal("12.34"),
                    "created_date": dt.date(2024, 1, 2),
                    "payload": b"ok",
                    "nested": _FakeRow({"id": 1}),
                    "duration": dt.timedelta(seconds=90),
                }
            )
        ]
    )

    result = execute_adc_developer_query(compiled, client=_FakeClient(query_job))

    assert result.rows == (
        {
            "revenue": "12.34",
            "created_date": "2024-01-02",
            "payload": "ok",
            "nested": {"id": 1},
            "duration": "0:01:30",
        },
    )


def test_execute_adc_developer_query_rejects_uncertified_query():
    """Tests only contract-certified compiled queries can execute."""
    compiled = CompiledQuery(
        sql="SELECT 1",
        parameters=(),
        metric="unsupported",
        dimensions=(),
        contract_version="thelook_ecommerce:v1",
        contract_certified=False,
    )

    with pytest.raises(ExecutionError, match="only contract-certified"):
        execute_adc_developer_query(compiled, client=_FakeClient(_FakeQueryJob([])))


def test_execute_adc_developer_query_uses_array_parameters():
    """Tests list-valued filters compile to BigQuery array parameters."""
    compiled = CompiledQuery(
        sql="SELECT * FROM t WHERE country IN UNNEST(@p1_country)",
        parameters=(QueryParameter("p1_country", ["US", "UK"]),),
        metric="completed_revenue",
        dimensions=(),
        contract_version="thelook_ecommerce:v1",
        contract_certified=True,
    )
    client = _FakeClient(_FakeQueryJob([]))

    execute_adc_developer_query(compiled, client=client)

    parameter = client.job_config.query_parameters[0]
    assert parameter.name == "p1_country"
    assert parameter.array_type == "STRING"
    assert parameter.values == ["US", "UK"]


def test_execute_adk_bigquery_adc_query_runs_with_blocked_writes():
    """Tests ADK-native execution uses read-only BigQuery tool settings."""
    calls = {}

    def fake_execute_sql(
        project_id, query, credentials, settings, tool_context, dry_run
    ):
        calls["project_id"] = project_id
        calls["query"] = query
        calls["credentials"] = credentials
        calls["settings"] = settings
        calls["tool_context"] = tool_context
        calls["dry_run"] = dry_run
        return {"status": "SUCCESS", "rows": [{"country": "US"}]}

    compiled = CompiledQuery(
        sql="SELECT 'US' AS country",
        parameters=(),
        metric="completed_order_count",
        dimensions=("country",),
        contract_version="thelook_ecommerce:v1",
        contract_certified=True,
    )

    result = execute_adk_bigquery_adc_query(
        compiled,
        project="project-a",
        location="us",
        max_results=25,
        maximum_bytes_billed=10_485_760,
        credentials=object(),
        execute_sql_tool=fake_execute_sql,
    )

    assert calls["project_id"] == "project-a"
    assert calls["query"] == compiled.sql
    assert calls["credentials"] is not None
    assert calls["settings"].write_mode.value == "blocked"
    assert calls["settings"].compute_project_id == "project-a"
    assert calls["settings"].location == "us"
    assert calls["settings"].max_query_result_rows == 25
    assert calls["settings"].maximum_bytes_billed == 10_485_760
    assert calls["tool_context"].state == {}
    assert calls["dry_run"] is False
    assert result.rows == ({"country": "US"},)
    assert result.job_id is None
    assert result.execution_mode == "adk_bigquery_adc"
    assert result.truncation_status == "none"


def test_execute_adk_bigquery_adc_query_rejects_compiled_parameters():
    """Tests ADK-native execution refuses unsupported parameter bindings."""
    compiled = CompiledQuery(
        sql="SELECT @p1_country AS country",
        parameters=(QueryParameter("p1_country", "US"),),
        metric="completed_order_count",
        dimensions=("country",),
        contract_version="thelook_ecommerce:v1",
        contract_certified=True,
    )

    with pytest.raises(ExecutionError, match="does not support compiled query"):
        execute_adk_bigquery_adc_query(
            compiled,
            project="project-a",
            credentials=object(),
            execute_sql_tool=lambda **_: {"status": "SUCCESS"},
        )


def test_execute_adk_bigquery_adc_query_requires_project():
    """Tests ADK-native execution requires an explicit compute project."""
    compiled = CompiledQuery(
        sql="SELECT 1",
        parameters=(),
        metric="completed_order_count",
        dimensions=(),
        contract_version="thelook_ecommerce:v1",
        contract_certified=True,
    )

    with pytest.raises(ExecutionError, match="GOOGLE_CLOUD_PROJECT"):
        execute_adk_bigquery_adc_query(
            compiled,
            project=None,
            credentials=object(),
            execute_sql_tool=lambda **_: {"status": "SUCCESS"},
        )


def test_execute_adk_bigquery_adc_query_raises_tool_errors():
    """Tests ADK-native tool failures surface as execution errors."""
    compiled = CompiledQuery(
        sql="SELECT 1",
        parameters=(),
        metric="completed_order_count",
        dimensions=(),
        contract_version="thelook_ecommerce:v1",
        contract_certified=True,
    )

    with pytest.raises(ExecutionError, match="permission denied"):
        execute_adk_bigquery_adc_query(
            compiled,
            project="project-a",
            credentials=object(),
            execute_sql_tool=lambda **_: {
                "status": "ERROR",
                "error_details": "permission denied",
            },
        )


def test_execute_adk_bigquery_adc_query_wraps_tool_exceptions():
    """Tests unexpected ADK helper failures become execution errors."""
    compiled = CompiledQuery(
        sql="SELECT 1",
        parameters=(),
        metric="completed_order_count",
        dimensions=(),
        contract_version="thelook_ecommerce:v1",
        contract_certified=True,
    )

    def fail_tool(**_kwargs):
        raise RuntimeError("credentials unavailable")

    with pytest.raises(ExecutionError, match="credentials unavailable"):
        execute_adk_bigquery_adc_query(
            compiled,
            project="project-a",
            credentials=object(),
            execute_sql_tool=fail_tool,
        )


def test_execute_adc_developer_query_reports_truncated_results():
    """Tests direct ADC execution reports when BigQuery has additional rows."""
    compiled = CompiledQuery(
        sql="SELECT country FROM t",
        parameters=(),
        metric="completed_order_count",
        dimensions=("country",),
        contract_version="thelook_ecommerce:v1",
        contract_certified=True,
    )
    query_job = _FakeQueryJob([_FakeRow({"country": "US"})], total_rows=2)

    result = execute_adc_developer_query(
        compiled,
        client=_FakeClient(query_job),
        max_results=1,
    )

    assert result.truncation_status == "confirmed"


def test_execute_adc_developer_query_reports_unknown_completeness():
    """Tests missing total-row metadata does not imply a complete result."""
    compiled = CompiledQuery(
        sql="SELECT country FROM t",
        parameters=(),
        metric="completed_order_count",
        dimensions=("country",),
        contract_version="thelook_ecommerce:v1",
        contract_certified=True,
    )
    query_job = _FakeQueryJob(
        [_FakeRow({"country": "US"})],
        expose_total_rows=False,
    )

    result = execute_adc_developer_query(
        compiled,
        client=_FakeClient(query_job),
        max_results=1,
    )

    assert result.truncation_status == "unknown"


@pytest.mark.parametrize("value", [[], ["US", 1]])
def test_execute_adc_developer_query_rejects_unsafe_array_parameters(value):
    """Tests empty and heterogeneous arrays are rejected before execution."""
    compiled = CompiledQuery(
        sql="SELECT * FROM t WHERE country IN UNNEST(@p1_country)",
        parameters=(QueryParameter("p1_country", value),),
        metric="completed_revenue",
        dimensions=(),
        contract_version="thelook_ecommerce:v1",
        contract_certified=True,
    )

    with pytest.raises(ExecutionError, match="array query parameter"):
        execute_adc_developer_query(
            compiled,
            client=_FakeClient(_FakeQueryJob([])),
        )


def test_execute_adc_developer_query_rejects_low_bytes_limit():
    """Tests cost guardrails reject limits below BigQuery's minimum."""
    compiled = CompiledQuery(
        sql="SELECT 1",
        parameters=(),
        metric="completed_order_count",
        dimensions=(),
        contract_version="thelook_ecommerce:v1",
        contract_certified=True,
    )

    with pytest.raises(ExecutionError, match="at least 10485760"):
        execute_adc_developer_query(
            compiled,
            client=_FakeClient(_FakeQueryJob([])),
            maximum_bytes_billed=1,
        )


@pytest.mark.parametrize("max_results", [0, 1001])
def test_execute_adc_developer_query_rejects_unbounded_result_limit(max_results):
    """Tests developer result limits remain bounded."""
    compiled = CompiledQuery(
        sql="SELECT 1",
        parameters=(),
        metric="completed_order_count",
        dimensions=(),
        contract_version="thelook_ecommerce:v1",
        contract_certified=True,
    )

    with pytest.raises(ExecutionError, match="between 1 and 1000"):
        execute_adc_developer_query(
            compiled,
            client=_FakeClient(_FakeQueryJob([])),
            max_results=max_results,
        )


def test_execute_adc_developer_query_rejects_non_select_statement():
    """Tests direct ADC execution verifies statement type before execution."""
    compiled = CompiledQuery(
        sql="DELETE FROM dataset.table WHERE TRUE",
        parameters=(),
        metric="completed_order_count",
        dimensions=(),
        contract_version="thelook_ecommerce:v1",
        contract_certified=True,
    )
    client = _FakeClient(_FakeQueryJob([]), statement_type="DELETE")

    with pytest.raises(ExecutionError, match="only supports SELECT"):
        execute_adc_developer_query(compiled, client=client)

    assert client.query_count == 1


@pytest.mark.parametrize(
    "response",
    [
        None,
        {"status": "SUCCESS", "rows": None},
        {"status": "SUCCESS", "rows": ["not-a-row"]},
        {"status": "SUCCESS", "dry_run_info": "invalid"},
        {
            "status": "SUCCESS",
            "dry_run_info": {"jobReference": {"jobId": 123}},
        },
    ],
)
def test_execute_adk_bigquery_adc_query_rejects_malformed_results(response):
    """Tests malformed ADK helper results become execution errors."""
    compiled = CompiledQuery(
        sql="SELECT 1",
        parameters=(),
        metric="completed_order_count",
        dimensions=(),
        contract_version="thelook_ecommerce:v1",
        contract_certified=True,
    )

    with pytest.raises(ExecutionError, match="malformed"):
        execute_adk_bigquery_adc_query(
            compiled,
            project="project-a",
            credentials=object(),
            execute_sql_tool=lambda **_: response,
        )


def test_execute_adk_bigquery_adc_query_reports_possible_truncation():
    """Tests the ADK helper's likelihood flag is not treated as confirmed."""
    compiled = CompiledQuery(
        sql="SELECT 1",
        parameters=(),
        metric="completed_order_count",
        dimensions=(),
        contract_version="thelook_ecommerce:v1",
        contract_certified=True,
    )

    result = execute_adk_bigquery_adc_query(
        compiled,
        project="project-a",
        credentials=object(),
        execute_sql_tool=lambda **_: {
            "status": "SUCCESS",
            "rows": [{"value": 1}],
            "result_is_likely_truncated": True,
        },
    )

    assert result.truncation_status == "possible"


def test_execute_adk_bigquery_adc_query_rejects_excess_rows():
    """Tests helper responses cannot exceed the configured result limit."""
    compiled = CompiledQuery(
        sql="SELECT 1",
        parameters=(),
        metric="completed_order_count",
        dimensions=(),
        contract_version="thelook_ecommerce:v1",
        contract_certified=True,
    )

    with pytest.raises(ExecutionError, match="more rows than requested"):
        execute_adk_bigquery_adc_query(
            compiled,
            project="project-a",
            max_results=1,
            credentials=object(),
            execute_sql_tool=lambda **_: {
                "status": "SUCCESS",
                "rows": [{"value": 1}, {"value": 2}],
            },
        )
