"""Tests for V2 one-shot SQL generation and execution."""

from __future__ import annotations

import asyncio
from pathlib import Path
import sys

import pytest
from pydantic import Field

pytest.importorskip("google.adk")

from google.adk.agents import LlmAgent  # noqa: E402
from google.adk.events.event import Event  # noqa: E402
from google.adk.models import BaseLlm, LlmRequest, LlmResponse  # noqa: E402
from google.adk.runners import Runner  # noqa: E402
from google.adk.sessions import InMemorySessionService  # noqa: E402
from google.adk.workflow import Workflow  # noqa: E402
from google.genai import types  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from semantic import sql_runtime  # noqa: E402
from semantic.execution import (  # noqa: E402
    ADC_AUTH_MODE,
    USER_AUTH_MODE,
    AdkBigQueryExecutor,
    ExecResult,
    SqlExecutionError,
    build_sql_executor,
    resolve_auth_mode,
)
from semantic.sql_runtime import (  # noqa: E402
    GENERATE_SQL_INSTRUCTION,
    SUMMARIZE_RESULT_INSTRUCTION,
    enter_sql_generation,
    execute_sql_once,
    finish_answer,
    finish_query_error,
    normalize_sql,
    prepare_result_summary,
    resolve_sql_auth,
)

_READINGS = "example-project.climate.readings"
_SQL = f"SELECT COUNT(DISTINCT reading_id) AS total FROM `{_READINGS}`"


def _fake_execute_fn(result=None, error=None):
    def fake(**kwargs):
        if error is not None:
            return {"status": "ERROR", "error_details": error}
        return result or {"status": "SUCCESS", "rows": [{"total": 3}]}

    return fake


def test_executor_executes_once_and_maps_rows():
    calls = []

    def execute(**kwargs):
        calls.append(kwargs)
        return {
            "status": "SUCCESS",
            "rows": [{"total": 3}, {"total": 4}],
            "result_is_likely_truncated": True,
        }

    executor = AdkBigQueryExecutor(
        project="compute-project",
        credentials=object(),
        execute_fn=execute,
    )

    result = executor.execute(_SQL)

    assert result.ok
    assert result.rows == ({"total": 3}, {"total": 4})
    assert result.truncated is True
    assert len(calls) == 1
    assert calls[0]["dry_run"] is False


def test_executor_maps_error():
    executor = AdkBigQueryExecutor(
        project="compute-project",
        credentials=object(),
        execute_fn=_fake_execute_fn(error="bad query"),
    )
    result = executor.execute("bad")
    assert not result.ok
    assert result.error == "bad query"


def test_executor_clamps_rows_independently():
    executor = AdkBigQueryExecutor(
        project="compute-project",
        max_result_rows=2,
        credentials=object(),
        execute_fn=_fake_execute_fn(
            result={
                "status": "SUCCESS",
                "rows": [{"n": 1}, {"n": 2}, {"n": 3}],
            }
        ),
    )
    result = executor.execute(_SQL)
    assert result.rows == ({"n": 1}, {"n": 2})
    assert result.truncated is True


def test_executor_uses_blocked_write_mode_without_cost_cap():
    executor = AdkBigQueryExecutor(project="compute-project", credentials=object())
    settings = executor._get_settings()
    assert str(settings.write_mode).endswith("BLOCKED")
    assert settings.compute_project_id == "compute-project"
    assert settings.maximum_bytes_billed is None


def test_build_sql_executor_requires_project(monkeypatch):
    monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)
    with pytest.raises(SqlExecutionError):
        build_sql_executor()


def test_resolve_auth_mode_is_strict(monkeypatch):
    monkeypatch.delenv("SQL_AUTH_MODE", raising=False)
    assert resolve_auth_mode() == ADC_AUTH_MODE
    assert resolve_auth_mode("user") == USER_AUTH_MODE
    with pytest.raises(SqlExecutionError, match="unsupported"):
        resolve_auth_mode("typo")


def test_build_sql_executor_binds_user_token(monkeypatch):
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "compute-project")
    executor = build_sql_executor(access_token="tok-123", auth_mode="user")
    assert isinstance(executor, AdkBigQueryExecutor)
    assert executor._credentials.token == "tok-123"


def test_build_sql_executor_user_mode_requires_token(monkeypatch):
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "compute-project")
    with pytest.raises(SqlExecutionError, match="access token"):
        build_sql_executor(auth_mode="user")


def test_resolve_sql_auth_reads_configured_state_key(monkeypatch):
    monkeypatch.setenv("SQL_AUTH_MODE", "user")
    monkeypatch.setenv("ADK_OAUTH_TOKEN_STATE_KEY", "custom_token")
    assert resolve_sql_auth({"custom_token": "tok-9"}) == ("user", "tok-9")
    with pytest.raises(ValueError, match="OAuth"):
        resolve_sql_auth({})


def test_normalize_sql_removes_one_outer_fence():
    assert normalize_sql(f"```sql\n{_SQL}\n```") == _SQL
    assert normalize_sql(_SQL) == _SQL
    assert normalize_sql("```python\nprint('x')\n```").startswith("```python")


def _grounded_payload():
    return {
        "question": "Count completed observations",
        "reasoning_path": "semantic_narrow",
        "semantic_context_ids": ["weather"],
        "semantic_context_versions": ["weather:v1"],
        "semantic_contexts": [
            {
                "metrics": [
                    {
                        "name": "completed_observations",
                        "expression": "readings.reading_id",
                        "required_filters": ["readings.status = 'Complete'"],
                    }
                ]
            }
        ],
        "catalog_route": "narrow",
        "catalog_context": [
            {
                "source": _READINGS,
                "fields": [
                    {"name": "reading_id", "type": "STRING"},
                    {"name": "status", "type": "STRING"},
                ],
            }
        ],
        "knowledge_catalog_context": [
            {"context": {"relationships": [{"name": "reading_status"}]}}
        ],
        "catalog_permitted_sources": [_READINGS],
    }


def test_enter_sql_generation_preserves_semantics_and_catalog_context():
    event = enter_sql_generation(_grounded_payload())
    assert event.output["semantic_contexts"][0]["metrics"][0]["required_filters"] == [
        "readings.status = 'Complete'"
    ]
    assert event.output["knowledge_catalog_context"]
    assert event.output["candidate_sources"] == [_READINGS]
    stored = event.actions.state_delta["sql_generation_context"]
    assert stored == event.output


class _FakeExecutor:
    def __init__(self, result=None):
        self.result = result or ExecResult(
            status="SUCCESS",
            rows=({"total": 3},),
            row_count=1,
        )
        self.calls: list[str] = []

    def execute(self, sql):
        self.calls.append(sql)
        return self.result


class _ScriptedLlm(BaseLlm):
    response: LlmResponse
    requests: list[LlmRequest] = Field(default_factory=list, exclude=True)

    async def generate_content_async(self, llm_request, stream: bool = False):
        assert stream is False
        self.requests.append(llm_request)
        yield self.response


def _scripted_model(text):
    return _ScriptedLlm(
        model="scripted",
        response=LlmResponse(
            content=types.Content(role="model", parts=[types.Part(text=text)])
        ),
    )


def _grounded(node_input):
    del node_input
    return Event(output=_grounded_payload())


async def _run_query(generator_model, summarizer_model, state=None):
    generator = LlmAgent(
        name="test_sql_generator",
        model=generator_model,
        instruction=GENERATE_SQL_INSTRUCTION,
    )
    summarizer = LlmAgent(
        name="test_result_summarizer",
        model=summarizer_model,
        instruction=SUMMARIZE_RESULT_INSTRUCTION,
    )
    workflow = Workflow(
        name="query_test",
        edges=[
            ("START", _grounded, enter_sql_generation),
            (enter_sql_generation, generator),
            (generator, execute_sql_once),
            (
                execute_sql_once,
                {
                    "success": prepare_result_summary,
                    "error": finish_query_error,
                },
            ),
            (prepare_result_summary, summarizer),
            (summarizer, finish_answer),
        ],
    )
    service = InMemorySessionService()
    await service.create_session(
        app_name="query_test",
        user_id="u",
        session_id="s",
        state=state or {},
    )
    runner = Runner(agent=workflow, app_name="query_test", session_service=service)
    outputs = []
    async for event in runner.run_async(
        user_id="u",
        session_id="s",
        new_message=types.Content(role="user", parts=[types.Part(text="q")]),
    ):
        if event.output is not None:
            outputs.append(event.output)
    return outputs


def _request_text(model):
    return "".join(
        part.text or ""
        for content in model.requests[0].contents
        for part in content.parts or []
    )


def test_workflow_executes_once_and_summarizes(monkeypatch):
    monkeypatch.delenv("SQL_AUTH_MODE", raising=False)
    executor = _FakeExecutor()
    monkeypatch.setattr(sql_runtime, "build_sql_executor", lambda **_kwargs: executor)
    generator_model = _scripted_model(f"```sql\n{_SQL}\n```")
    summarizer_model = _scripted_model("There are 3 completed observations.")

    final = asyncio.run(_run_query(generator_model, summarizer_model))[-1]

    assert final["status"] == "answered"
    assert final["answer"] == "There are 3 completed observations."
    assert final["sql"] == _SQL
    assert final["rows"] == [{"total": 3}]
    assert final["semantic_context_ids"] == ["weather"]
    assert final["auth"]["mode"] == "adc"
    assert executor.calls == [_SQL]
    assert "required_filters" in _request_text(generator_model)
    assert "readings.status = 'Complete'" in _request_text(generator_model)
    assert '"total":3' in _request_text(summarizer_model).replace(" ", "")


def test_workflow_execution_error_returns_without_summary(monkeypatch):
    executor = _FakeExecutor(ExecResult(status="ERROR", error="unknown column"))
    monkeypatch.setattr(sql_runtime, "build_sql_executor", lambda **_kwargs: executor)
    generator_model = _scripted_model(_SQL)
    summarizer_model = _scripted_model("must not run")

    final = asyncio.run(_run_query(generator_model, summarizer_model))[-1]

    assert final["status"] == "query_error"
    assert final["error"] == "unknown column"
    assert executor.calls == [_SQL]
    assert summarizer_model.requests == []


def test_workflow_user_mode_fails_without_token(monkeypatch):
    monkeypatch.setenv("SQL_AUTH_MODE", "user")
    calls = []

    def build(**kwargs):
        calls.append(kwargs)
        return _FakeExecutor()

    monkeypatch.setattr(sql_runtime, "build_sql_executor", build)
    final = asyncio.run(_run_query(_scripted_model(_SQL), _scripted_model("unused")))[
        -1
    ]
    assert final["status"] == "query_error"
    assert "OAuth access token" in final["error"]
    assert calls == []


def test_workflow_user_mode_binds_token(monkeypatch):
    monkeypatch.setenv("SQL_AUTH_MODE", "user")
    executor = _FakeExecutor()
    calls = []

    def build(**kwargs):
        calls.append(kwargs)
        return executor

    monkeypatch.setattr(sql_runtime, "build_sql_executor", build)
    final = asyncio.run(
        _run_query(
            _scripted_model(_SQL),
            _scripted_model("There are 3."),
            state={"AUTH_RESOURCE_SEMANTIC_ANALYTICS": "tok-xyz"},
        )
    )[-1]
    assert final["status"] == "answered"
    assert final["auth"] == {"mode": "user", "source": "user-token"}
    assert calls == [{"access_token": "tok-xyz", "auth_mode": "user"}]
