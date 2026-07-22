"""Compatibility checks for the installed ADK 2 workflow API."""

from __future__ import annotations

import asyncio

import pytest
from pydantic import BaseModel

pytest.importorskip("google.adk")

from google.adk.agents import LlmAgent  # noqa: E402
from google.adk.agents.context import Context  # noqa: E402
from google.adk.events.event import Event  # noqa: E402
from google.adk.runners import Runner  # noqa: E402
from google.adk.sessions import InMemorySessionService  # noqa: E402
from google.adk.tools.google_tool import GoogleTool  # noqa: E402
from google.adk.workflow import Workflow, node  # noqa: E402
from google.genai import types  # noqa: E402


class _Decision(BaseModel):
    route: str
    reason: str


def _route_decision(node_input: dict[str, str]) -> Event:
    return Event(output=node_input, route=node_input["route"])


def _covered(node_input: dict[str, str]) -> dict[str, str]:
    return node_input


def _refused(node_input: dict[str, str]) -> dict[str, str]:
    return node_input


def test_workflow_accepts_structured_llm_node_and_routed_edges():
    """Tests installed ADK graph construction accepts the target node pattern."""
    selector = LlmAgent(
        name="compatibility_selector",
        model="gemini-2.5-flash",
        instruction="Select a route.",
        output_schema=_Decision,
    )

    workflow = Workflow(
        name="compatibility_graph",
        edges=[
            ("START", selector, _route_decision),
            (
                _route_decision,
                {
                    "covered": _covered,
                    "refuse": _refused,
                },
            ),
        ],
    )

    assert workflow.graph is not None
    assert selector.output_schema is _Decision


def _initialize(node_input: object) -> Event:
    del node_input
    return Event(output={"value": "ready"}, state={"marker": "workflow"})


def _route_dynamic(node_input: dict[str, str]) -> Event:
    return Event(output=node_input, route="run")


def _dynamic_child(node_input: dict[str, str]) -> dict[str, str]:
    return {**node_input, "child": "completed"}


def _inspect_context(value: str, tool_context: Context) -> dict[str, str]:
    return {"value": value, "marker": tool_context.state["marker"]}


_context_tool = GoogleTool(func=_inspect_context)


@node(rerun_on_resume=True)
async def _run_dynamic(ctx: Context, node_input: dict[str, str]) -> Event:
    tool_result = await _context_tool.run_async(
        args={"value": node_input["value"]},
        tool_context=ctx,
    )
    child_result = await ctx.run_node(_dynamic_child, tool_result)
    return Event(output=child_result, state={"attempts": 1})


def test_workflow_runs_routing_state_dynamic_node_and_google_tool_context():
    """Tests the target graph primitives execute together under ADK 2.5."""

    async def run_workflow() -> tuple[list[object], dict[str, object]]:
        workflow = Workflow(
            name="compatibility_runtime",
            edges=[
                ("START", _initialize, _route_dynamic),
                (_route_dynamic, {"run": _run_dynamic}),
            ],
        )
        session_service = InMemorySessionService()
        await session_service.create_session(
            app_name="compatibility_app",
            user_id="user",
            session_id="session",
        )
        runner = Runner(
            agent=workflow,
            app_name="compatibility_app",
            session_service=session_service,
        )
        message = types.Content(
            role="user",
            parts=[types.Part(text="run")],
        )
        outputs = []
        async for event in runner.run_async(
            user_id="user",
            session_id="session",
            new_message=message,
        ):
            if event.output is not None:
                outputs.append(event.output)
        session = await session_service.get_session(
            app_name="compatibility_app",
            user_id="user",
            session_id="session",
        )
        return outputs, dict(session.state)

    outputs, state = asyncio.run(run_workflow())

    assert {"value": "ready", "marker": "workflow", "child": "completed"} in outputs
    assert state["marker"] == "workflow"
    assert state["attempts"] == 1
