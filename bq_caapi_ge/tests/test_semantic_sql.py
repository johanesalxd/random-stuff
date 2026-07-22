"""Tests for Phase 8 guarded SQL generation and execution."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
import sys

import pytest

pytest.importorskip("google.adk")

from google.adk.agents import LlmAgent  # noqa: E402
from google.adk.models import BaseLlm, LlmRequest, LlmResponse  # noqa: E402
from google.adk.runners import Runner  # noqa: E402
from google.adk.sessions import InMemorySessionService  # noqa: E402
from google.adk.workflow import Workflow  # noqa: E402
from google.genai import types  # noqa: E402
from pydantic import Field  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from semantic import sql_runtime  # noqa: E402
from semantic.execution import (  # noqa: E402
    DEVELOPER_MODE,
    PLAN_MODE,
    AdkBigQueryExecutor,
    ExecResult,
    SqlExecutionError,
    build_sql_executor,
    resolve_execution_mode,
)
from semantic.sql_policy import (  # noqa: E402
    extract_table_references,
    validate_sql,
)
from semantic.sql_runtime import (  # noqa: E402
    GENERATE_SQL_INSTRUCTION,
    GeneratedSql,
    apply_sql_policy,
    dry_run_sql,
    enforce_sql_policy,
    enter_sql_generation,
    finish_sql_refusal,
    finish_sql_result,
    maybe_execute_sql,
    plan_repair,
    recover_invalid_sql,
    repair_sql,
    run_dry_run,
    run_execution,
)

_READINGS = "example-project.climate.readings"
_PERMITTED = [_READINGS]


# --- SQL policy ------------------------------------------------------------


def test_policy_allows_in_scope_select():
    result = validate_sql(
        f"SELECT station_id FROM `{_READINGS}`", permitted_sources=_PERMITTED
    )
    assert result.allowed
    assert result.referenced_sources == (_READINGS,)
    assert result.out_of_scope == ()


def test_policy_extracts_tables_excluding_ctes():
    qualified, unqualified = extract_table_references(
        f"WITH x AS (SELECT * FROM `{_READINGS}`) SELECT * FROM x"
    )
    assert qualified == (_READINGS,)
    assert unqualified == ()


def test_policy_rejects_out_of_scope_source():
    result = validate_sql(
        "SELECT * FROM `example-project.climate.secret`", permitted_sources=_PERMITTED
    )
    assert not result.allowed
    assert result.out_of_scope == ("example-project.climate.secret",)


def test_policy_rejects_unqualified_reference():
    result = validate_sql("SELECT * FROM readings", permitted_sources=_PERMITTED)
    assert not result.allowed
    assert any("fully qualified" in v for v in result.violations)


@pytest.mark.parametrize(
    "sql",
    [
        "DELETE FROM `example-project.climate.readings` WHERE TRUE",
        "CREATE TABLE `example-project.climate.x` AS SELECT 1",
        "UPDATE `example-project.climate.readings` SET a = 1 WHERE TRUE",
        "CALL example.proc()",
    ],
)
def test_policy_rejects_non_select(sql):
    result = validate_sql(sql, permitted_sources=_PERMITTED)
    assert not result.allowed


def test_policy_rejects_multiple_statements():
    result = validate_sql(
        f"SELECT 1 FROM `{_READINGS}`; SELECT 2 FROM `{_READINGS}`",
        permitted_sources=_PERMITTED,
    )
    assert not result.allowed
    assert any("exactly one statement" in v for v in result.violations)


def test_policy_rejects_empty_and_unparseable():
    assert not validate_sql("", permitted_sources=_PERMITTED).allowed
    assert not validate_sql("SELECT FROM WHERE", permitted_sources=_PERMITTED).allowed


# --- execution boundary ----------------------------------------------------


def _fake_execute_fn(dry_result=None, exec_result=None, error=None):
    def fake(**kwargs):
        if error is not None:
            return {"status": "ERROR", "error_details": error}
        if kwargs["dry_run"]:
            return dry_result
        return exec_result

    return fake


def test_executor_maps_dry_run_bytes():
    fn = _fake_execute_fn(
        dry_result={
            "status": "SUCCESS",
            "dry_run_info": {"statistics": {"totalBytesProcessed": "2048"}},
        }
    )
    executor = AdkBigQueryExecutor(project="p", credentials=object(), execute_fn=fn)
    result = executor.dry_run("SELECT 1 FROM `p.d.t`")
    assert result.ok
    assert result.mode == PLAN_MODE
    assert result.total_bytes_processed == 2048


def test_executor_maps_execute_rows_and_truncation():
    fn = _fake_execute_fn(
        exec_result={
            "status": "SUCCESS",
            "rows": [{"a": 1}, {"a": 2}],
            "result_is_likely_truncated": True,
        }
    )
    executor = AdkBigQueryExecutor(project="p", credentials=object(), execute_fn=fn)
    result = executor.execute("SELECT a FROM `p.d.t`")
    assert result.ok
    assert result.mode == DEVELOPER_MODE
    assert result.row_count == 2
    assert result.truncated is True
    assert result.to_context()["rows"] == [{"a": 1}, {"a": 2}]


def test_executor_maps_error():
    fn = _fake_execute_fn(error="bad query")
    executor = AdkBigQueryExecutor(project="p", credentials=object(), execute_fn=fn)
    result = executor.dry_run("SELECT 1 FROM `p.d.t`")
    assert not result.ok
    assert result.error == "bad query"


def test_executor_uses_blocked_read_only_settings():
    executor = AdkBigQueryExecutor(project="compute-project", credentials=object())
    settings = executor._get_settings()
    assert str(settings.write_mode).endswith("BLOCKED")
    assert settings.compute_project_id == "compute-project"


def test_build_sql_executor_requires_project(monkeypatch):
    monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)
    with pytest.raises(SqlExecutionError):
        build_sql_executor()


def test_build_sql_executor_returns_adk_executor(monkeypatch):
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "compute-project")
    assert isinstance(build_sql_executor(), AdkBigQueryExecutor)


def test_resolve_execution_mode_defaults_to_plan(monkeypatch):
    monkeypatch.delenv("SQL_EXECUTION_MODE", raising=False)
    assert resolve_execution_mode() == PLAN_MODE
    assert resolve_execution_mode("developer") == DEVELOPER_MODE
    assert resolve_execution_mode("anything-else") == PLAN_MODE


# --- runtime pure logic ----------------------------------------------------


class _FakeExecutor:
    def __init__(self, dry=None, execu=None):
        self._dry = dry or ExecResult(
            status="SUCCESS", mode=PLAN_MODE, total_bytes_processed=1000
        )
        self._exec = execu or ExecResult(
            status="SUCCESS", mode=DEVELOPER_MODE, rows=({"n": 1},), row_count=1
        )
        self.dry_calls: list[str] = []
        self.exec_calls: list[str] = []

    def dry_run(self, sql):
        self.dry_calls.append(sql)
        return self._dry

    def execute(self, sql):
        self.exec_calls.append(sql)
        return self._exec


def _generated(sql):
    return {
        "sql": sql,
        "interpretation": "interpretation",
        "unresolved_assumptions": [],
        "referenced_sources": [_READINGS],
    }


def test_apply_sql_policy_routes_allowed_and_rejected():
    payload, route = apply_sql_policy(
        _generated(f"SELECT station_id FROM `{_READINGS}`"), _PERMITTED
    )
    assert route == "allowed"
    assert payload["sql_policy"]["allowed"] is True
    assert payload["interpretation"] == "interpretation"

    _, rejected = apply_sql_policy(
        _generated("SELECT * FROM `example-project.climate.secret`"), _PERMITTED
    )
    assert rejected == "rejected"


def test_run_dry_run_routes_by_executor_result():
    ok_payload, ok_route = run_dry_run({"sql": "SELECT 1"}, _FakeExecutor())
    assert ok_route == "valid"
    assert ok_payload["dry_run"]["total_bytes_processed"] == 1000

    executor = _FakeExecutor(dry=ExecResult(status="ERROR", mode=PLAN_MODE, error="x"))
    _, bad_route = run_dry_run({"sql": "SELECT 1"}, executor)
    assert bad_route == "invalid"


def test_run_execution_skips_in_plan_mode():
    executor = _FakeExecutor()
    plan = run_execution({"sql": "SELECT 1"}, None, mode=PLAN_MODE)
    assert plan["execution"]["status"] == "SKIPPED"
    assert executor.exec_calls == []

    developer = run_execution({"sql": "SELECT 1"}, executor, mode=DEVELOPER_MODE)
    assert developer["execution"]["status"] == "SUCCESS"
    assert executor.exec_calls == ["SELECT 1"]


def test_plan_repair_retries_then_exhausts():
    payload, route, attempts = plan_repair(
        {"sql": "bad", "sql_policy": {"violations": ["out-of-scope"]}},
        generation_context={"question": "q", "permitted_sources": _PERMITTED},
        attempts=0,
    )
    assert route == "retry"
    assert attempts == 1
    assert payload["previous_error"]

    exhausted, route2, attempts2 = plan_repair(
        {"sql": "bad", "sql_policy": {"violations": ["out-of-scope"]}},
        generation_context={},
        attempts=1,
    )
    assert route2 == "exhausted"
    assert attempts2 == 1
    assert exhausted["refusal_reason"]


def test_enter_sql_generation_persists_permitted_sources():
    event = enter_sql_generation(
        {
            "question": "count",
            "catalog_route": "narrow",
            "catalog_context": [{"source": _READINGS}],
            "catalog_permitted_sources": [_READINGS],
        }
    )
    assert event.output["permitted_sources"] == [_READINGS]
    assert event.actions.state_delta["sql_permitted_sources"] == [_READINGS]
    assert event.actions.state_delta["temp:sql_repair_attempts"] == 0


def test_enter_sql_generation_uses_broad_discovered_sources():
    event = enter_sql_generation(
        {
            "question": "count",
            "catalog_route": "broad",
            "catalog_discovered_sources": [_READINGS],
        }
    )
    assert event.output["permitted_sources"] == [_READINGS]


def test_finish_terminals_set_status():
    planned = finish_sql_result(
        run_execution({"sql": "SELECT 1"}, None, mode=PLAN_MODE)
    )
    assert planned["status"] == "sql_planned"
    assert planned["next_step"] == "return_result"

    refusal = finish_sql_refusal(
        {"sql_policy": {"violations": ["sql references out-of-scope sources: x"]}}
    )
    assert refusal["status"] == "sql_refused"
    assert "out-of-scope" in refusal["refusal_reason"]


def test_recover_invalid_sql_replaces_malformed_output():
    response = LlmResponse(
        content=types.Content(role="model", parts=[types.Part(text='{"sql": 123}')])
    )
    recovered = recover_invalid_sql(None, response)
    assert recovered is not None
    payload = json.loads(recovered.content.parts[0].text)
    assert payload["sql"] == ""


def test_recover_invalid_sql_preserves_valid_and_provider_errors():
    valid = LlmResponse(
        content=types.Content(
            role="model",
            parts=[types.Part(text=GeneratedSql(sql="SELECT 1").model_dump_json())],
        )
    )
    assert recover_invalid_sql(None, valid) is None
    provider_error = LlmResponse(error_code="RESOURCE_EXHAUSTED", error_message="q")
    assert recover_invalid_sql(None, provider_error) is None


# --- workflow integration --------------------------------------------------


class _ScriptedLlm(BaseLlm):
    response: LlmResponse
    requests: list[LlmRequest] = Field(default_factory=list, exclude=True)

    async def generate_content_async(self, llm_request, stream: bool = False):
        assert stream is False
        self.requests.append(llm_request)
        yield self.response


def _sql_response(payload):
    return LlmResponse(
        content=types.Content(
            role="model", parts=[types.Part(text=json.dumps(payload))]
        )
    )


def _grounded(node_input):
    from google.adk.events.event import Event

    return Event(
        output={
            "question": "count observations by station",
            "catalog_route": "narrow",
            "catalog_context": [
                {"source": _READINGS, "fields": [{"name": "reading_id"}]}
            ],
            "catalog_permitted_sources": [_READINGS],
            "status": "catalog_context_grounded",
        }
    )


def _sql_agent(payload):
    scripted = _ScriptedLlm(model="scripted-sql", response=_sql_response(payload))
    return LlmAgent(
        name="guarded_sql_generator",
        model=scripted,
        instruction=GENERATE_SQL_INSTRUCTION,
        output_schema=GeneratedSql,
        after_model_callback=recover_invalid_sql,
    )


async def _run_sql(sql_agent):
    workflow = Workflow(
        name="sql_generation_test",
        edges=[
            ("START", _grounded, enter_sql_generation),
            (enter_sql_generation, sql_agent),
            (sql_agent, enforce_sql_policy),
            (enforce_sql_policy, {"allowed": dry_run_sql, "rejected": repair_sql}),
            (dry_run_sql, {"valid": maybe_execute_sql, "invalid": repair_sql}),
            (repair_sql, {"retry": sql_agent, "exhausted": finish_sql_refusal}),
            (maybe_execute_sql, finish_sql_result),
        ],
    )
    session_service = InMemorySessionService()
    await session_service.create_session(
        app_name="sql_test", user_id="user", session_id="session"
    )
    runner = Runner(
        agent=workflow, app_name="sql_test", session_service=session_service
    )
    outputs = []
    async for event in runner.run_async(
        user_id="user",
        session_id="session",
        new_message=types.Content(role="user", parts=[types.Part(text="q")]),
    ):
        if event.output is not None:
            outputs.append(event.output)
    return outputs


def test_workflow_plan_mode_generates_and_stops_at_dry_run(monkeypatch):
    monkeypatch.delenv("SQL_EXECUTION_MODE", raising=False)
    executor = _FakeExecutor()
    monkeypatch.setattr(sql_runtime, "build_sql_executor", lambda: executor)
    agent = _sql_agent(_generated(f"SELECT station_id FROM `{_READINGS}`"))

    outputs = asyncio.run(_run_sql(agent))

    final = outputs[-1]
    assert final["status"] == "sql_planned"
    assert final["sql_policy"]["allowed"] is True
    assert final["dry_run"]["total_bytes_processed"] == 1000
    assert final["execution"]["status"] == "SKIPPED"
    assert executor.exec_calls == []


def test_workflow_developer_mode_executes(monkeypatch):
    monkeypatch.setenv("SQL_EXECUTION_MODE", "developer")
    executor = _FakeExecutor()
    monkeypatch.setattr(sql_runtime, "build_sql_executor", lambda: executor)
    agent = _sql_agent(_generated(f"SELECT station_id FROM `{_READINGS}`"))

    outputs = asyncio.run(_run_sql(agent))

    final = outputs[-1]
    assert final["status"] == "sql_executed"
    assert final["execution"]["status"] == "SUCCESS"
    assert executor.exec_calls == [f"SELECT station_id FROM `{_READINGS}`"]


def test_workflow_out_of_scope_sql_refused_after_repair(monkeypatch):
    monkeypatch.delenv("SQL_EXECUTION_MODE", raising=False)
    executor = _FakeExecutor()
    monkeypatch.setattr(sql_runtime, "build_sql_executor", lambda: executor)
    agent = _sql_agent(_generated("SELECT * FROM `example-project.climate.secret`"))

    outputs = asyncio.run(_run_sql(agent))

    final = outputs[-1]
    assert final["status"] == "sql_refused"
    assert "out-of-scope" in final["refusal_reason"]
    # One initial attempt plus exactly one bounded repair retry.
    assert len(agent.model.requests) == 2
    assert executor.dry_calls == []


def test_workflow_dry_run_error_refused(monkeypatch):
    monkeypatch.delenv("SQL_EXECUTION_MODE", raising=False)
    executor = _FakeExecutor(
        dry=ExecResult(status="ERROR", mode=PLAN_MODE, error="unknown column")
    )
    monkeypatch.setattr(sql_runtime, "build_sql_executor", lambda: executor)
    agent = _sql_agent(_generated(f"SELECT bad FROM `{_READINGS}`"))

    outputs = asyncio.run(_run_sql(agent))

    final = outputs[-1]
    assert final["status"] == "sql_refused"
    assert "unknown column" in final["refusal_reason"]
