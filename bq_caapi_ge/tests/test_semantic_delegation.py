"""Tests for the deterministic CA data-agent fallback (Phase 11)."""

from __future__ import annotations

import asyncio
from pathlib import Path
import sys

import pytest
from pydantic import Field

pytest.importorskip("google.adk")

from google.adk.events.event import Event  # noqa: E402
from google.adk.models import BaseLlm, LlmRequest, LlmResponse  # noqa: E402
from google.adk.runners import Runner  # noqa: E402
from google.adk.sessions import InMemorySessionService  # noqa: E402
from google.adk.workflow import Workflow  # noqa: E402
from google.genai import types  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

agent = pytest.importorskip("advanced.app.semantic_analytics.agent")  # noqa: E402
from semantic.catalog_runtime import finish_clarification  # noqa: E402
from semantic.delegation_runtime import (  # noqa: E402
    decide_fallback_route,
    finish_data_agent_result,
    resolve_fallback_mode,
    route_grounding_fallback,
    route_sql_fallback,
)
from semantic.sql_runtime import finish_sql_refusal  # noqa: E402

_TOKEN_KEY = "AUTH_RESOURCE_SEMANTIC_ANALYTICS"


class _ScriptedLlm(BaseLlm):
    response: LlmResponse
    requests: list[LlmRequest] = Field(default_factory=list, exclude=True)

    async def generate_content_async(
        self, llm_request: LlmRequest, stream: bool = False
    ):
        assert stream is False
        self.requests.append(llm_request)
        yield self.response


# --- resolve_fallback_mode ---------------------------------------------------


def test_resolve_fallback_mode_defaults_to_kc(monkeypatch):
    """Tests the fallback is off by default."""
    monkeypatch.delenv("SEMANTIC_FALLBACK_MODE", raising=False)
    assert resolve_fallback_mode() == "kc"


def test_resolve_fallback_mode_accepts_known_values():
    """Tests explicit modes resolve and unknown values fall back to kc."""
    assert resolve_fallback_mode("data_agent") == "data_agent"
    assert resolve_fallback_mode("REFUSE") == "refuse"
    assert resolve_fallback_mode("nonsense") == "kc"


# --- decide_fallback_route (pure matrix) -------------------------------------


def _route(mode, execution_mode, auth_mode, has_token, trigger):
    return decide_fallback_route(
        mode=mode,
        execution_mode=execution_mode,
        auth_mode=auth_mode,
        has_token=has_token,
        trigger=trigger,
    )


def test_decide_route_kc_keeps_existing_terminals():
    """Tests the default kc mode keeps clarify (grounding) and refuse (sql)."""
    assert _route("kc", "developer", "user", True, "grounding") == "clarify"
    assert _route("kc", "developer", "user", True, "sql") == "refuse"


def test_decide_route_refuse_always_refuses():
    """Tests refuse mode refuses at both triggers regardless of creds."""
    assert _route("refuse", "developer", "user", True, "grounding") == "refuse"
    assert _route("refuse", "developer", "user", True, "sql") == "refuse"


def test_decide_route_data_agent_delegates_with_user_token():
    """Tests data_agent mode delegates in developer+user mode with a token."""
    assert _route("data_agent", "developer", "user", True, "grounding") == "delegate"
    assert _route("data_agent", "developer", "user", True, "sql") == "delegate"


def test_decide_route_suppressed_in_plan_mode():
    """Tests plan mode suppresses delegation (CA would execute SQL)."""
    assert _route("data_agent", "plan", "user", True, "grounding") == "clarify"
    assert _route("data_agent", "plan", "user", True, "sql") == "refuse"


def test_decide_route_suppressed_in_adc_mode():
    """Tests adc mode suppresses delegation (Option X: never the shared SA)."""
    assert _route("data_agent", "developer", "adc", True, "grounding") == "clarify"
    assert _route("data_agent", "developer", "adc", True, "sql") == "refuse"


def test_decide_route_fails_closed_without_token():
    """Tests user mode without a token refuses rather than delegating."""
    assert _route("data_agent", "developer", "user", False, "grounding") == "refuse"
    assert _route("data_agent", "developer", "user", False, "sql") == "refuse"


# --- node-level routing and provenance ---------------------------------------


def _seed_node(output, state):
    def seed(node_input):
        return Event(output=output, state=dict(state))

    seed.__name__ = "seed_fallback_input"
    return seed


async def _run(workflow, question="How broad is everything?"):
    session_service = InMemorySessionService()
    await session_service.create_session(
        app_name="delegation_test", user_id="u", session_id="s"
    )
    runner = Runner(
        agent=workflow,
        app_name="delegation_test",
        session_service=session_service,
    )
    outputs = []
    async for event in runner.run_async(
        user_id="u",
        session_id="s",
        new_message=types.Content(role="user", parts=[types.Part(text=question)]),
    ):
        if event.output is not None:
            outputs.append(event.output)
    return outputs


def _grounding_workflow(fallback_agent, *, output, state):
    return Workflow(
        name="grounding_fallback_test",
        edges=[
            ("START", _seed_node(output, state), route_grounding_fallback),
            (
                route_grounding_fallback,
                {
                    "delegate": fallback_agent,
                    "clarify": finish_clarification,
                    "refuse": finish_sql_refusal,
                },
            ),
            (fallback_agent, finish_data_agent_result),
        ],
    )


def _sql_workflow(fallback_agent, *, output, state):
    return Workflow(
        name="sql_fallback_test",
        edges=[
            ("START", _seed_node(output, state), route_sql_fallback),
            (
                route_sql_fallback,
                {"delegate": fallback_agent, "refuse": finish_sql_refusal},
            ),
            (fallback_agent, finish_data_agent_result),
        ],
    )


def _scripted_fallback(text="The total is 31,132."):
    scripted = _ScriptedLlm(
        model="scripted-fallback",
        response=LlmResponse(
            content=types.Content(role="model", parts=[types.Part(text=text)])
        ),
    )
    return agent.data_agent_fallback.model_copy(
        update={"model": scripted, "parent_agent": None}
    )


def test_grounding_fallback_delegates_and_reports_provenance(monkeypatch):
    """Tests the grounding gate delegates to CA and labels the answer."""
    monkeypatch.setenv("SEMANTIC_FALLBACK_MODE", "data_agent")
    monkeypatch.setenv("SQL_EXECUTION_MODE", "developer")
    monkeypatch.setenv("SQL_AUTH_MODE", "user")
    workflow = _grounding_workflow(
        _scripted_fallback(),
        output={"question": "How many completed orders?"},
        state={_TOKEN_KEY: "user-token"},
    )

    final = asyncio.run(_run(workflow))[-1]

    assert final["reasoning_path"] == "data_agent"
    assert final["guardrail_coverage"] == "none"
    assert final["status"] == "data_agent_answered"
    assert final["answer"] == "The total is 31,132."
    assert final["question"] == "How many completed orders?"


def test_grounding_fallback_suppressed_in_plan_mode(monkeypatch):
    """Tests plan mode keeps the clarify terminal instead of delegating."""
    monkeypatch.setenv("SEMANTIC_FALLBACK_MODE", "data_agent")
    monkeypatch.setenv("SQL_EXECUTION_MODE", "plan")
    monkeypatch.setenv("SQL_AUTH_MODE", "user")
    workflow = _grounding_workflow(
        _scripted_fallback(),
        output={"question": "Anything at all?"},
        state={_TOKEN_KEY: "user-token"},
    )

    final = asyncio.run(_run(workflow))[-1]

    assert final["status"] == "catalog_context_insufficient"
    assert "reasoning_path" not in final or final.get("reasoning_path") != "data_agent"


def test_grounding_fallback_refuses_without_token(monkeypatch):
    """Tests user mode without a token fails closed to refusal."""
    monkeypatch.setenv("SEMANTIC_FALLBACK_MODE", "data_agent")
    monkeypatch.setenv("SQL_EXECUTION_MODE", "developer")
    monkeypatch.setenv("SQL_AUTH_MODE", "user")
    workflow = _grounding_workflow(
        _scripted_fallback(),
        output={"question": "No token here."},
        state={},
    )

    final = asyncio.run(_run(workflow))[-1]

    assert final["status"] == "sql_refused"


def test_sql_fallback_delegates_using_stored_question(monkeypatch):
    """Tests the sql gate delegates and recovers the question from state."""
    monkeypatch.setenv("SEMANTIC_FALLBACK_MODE", "data_agent")
    monkeypatch.setenv("SQL_EXECUTION_MODE", "developer")
    monkeypatch.setenv("SQL_AUTH_MODE", "user")
    workflow = _sql_workflow(
        _scripted_fallback("Revenue by category returned."),
        output={"refusal_reason": "policy rejected"},
        state={
            _TOKEN_KEY: "user-token",
            "sql_generation_context": {"question": "Revenue by category?"},
        },
    )

    final = asyncio.run(_run(workflow))[-1]

    assert final["reasoning_path"] == "data_agent"
    assert final["answer"] == "Revenue by category returned."
    assert final["question"] == "Revenue by category?"


def test_sql_fallback_defaults_off_keeps_refusal(monkeypatch):
    """Tests the default kc mode leaves the sql-refusal terminal unchanged."""
    monkeypatch.delenv("SEMANTIC_FALLBACK_MODE", raising=False)
    monkeypatch.setenv("SQL_EXECUTION_MODE", "developer")
    monkeypatch.setenv("SQL_AUTH_MODE", "user")
    workflow = _sql_workflow(
        _scripted_fallback(),
        output={"refusal_reason": "policy rejected"},
        state={_TOKEN_KEY: "user-token"},
    )

    final = asyncio.run(_run(workflow))[-1]

    assert final["status"] == "sql_refused"
