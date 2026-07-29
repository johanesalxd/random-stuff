"""Deterministic CA data-agent fallback gating (Phase 11).

When the guarded custom path cannot serve a question -- broad grounding is
insufficient (the "too broad" exit) or SQL generation is refused after bounded
repair (the "error" exit) -- these deterministic gate nodes decide whether to
delegate to a Conversational Analytics data agent, keep the existing
clarify/refuse terminal, or fail closed.

The delegation decision is fully deterministic: it reads the feature flag, the
execution mode, the auth mode, and whether a per-user OAuth token is present. The
model never chooses to delegate. This module owns no CA transport; it only routes.
It must not import ``google.adk.tools.data_agent`` or any of the historical
compiler/executor modules, keeping the fallback decision hermetically testable.
"""

from __future__ import annotations

from collections.abc import Mapping
import os
from typing import Any

from google.adk.agents.context import Context
from google.adk.events.event import Event
from google.adk.workflow import node

from semantic.execution import (
    DEVELOPER_MODE,
    USER_AUTH_MODE,
    resolve_auth_mode,
    resolve_execution_mode,
)

_FALLBACK_MODE_ENV = "SEMANTIC_FALLBACK_MODE"

KC_MODE = "kc"
DATA_AGENT_MODE = "data_agent"
REFUSE_MODE = "refuse"

GROUNDING_TRIGGER = "grounding"
SQL_TRIGGER = "sql"

# Reuse the same session-state key and default the SQL executor reads, so the
# CA fallback runs under the same per-user token as guarded execution.
_TOKEN_STATE_KEY_ENV = "ADK_OAUTH_TOKEN_STATE_KEY"
_DEFAULT_TOKEN_STATE_KEY = "AUTH_RESOURCE_SEMANTIC_ANALYTICS"

# Where the delegating gate stashes the raw question for the terminal to report.
_QUESTION_STATE_KEY = "temp:data_agent_question"

# The SQL-generation context the SQL runtime persists; carries the question on the
# SQL-refusal path where the node input no longer holds it.
_SQL_CONTEXT_STATE_KEY = "sql_generation_context"


def resolve_fallback_mode(raw: str | None = None) -> str:
    """Resolve the configured fallback mode.

    Args:
        raw: An explicit override; when ``None`` the ``SEMANTIC_FALLBACK_MODE``
            environment variable is consulted.

    Returns:
        One of ``kc`` (default), ``data_agent``, or ``refuse``.
    """
    value = raw if raw is not None else os.getenv(_FALLBACK_MODE_ENV, KC_MODE)
    normalized = value.strip().lower()
    if normalized in (DATA_AGENT_MODE, REFUSE_MODE):
        return normalized
    return KC_MODE


def decide_fallback_route(
    *,
    mode: str,
    execution_mode: str,
    auth_mode: str,
    has_token: bool,
    trigger: str,
) -> str:
    """Decide the fallback route deterministically.

    Args:
        mode: The resolved fallback mode (``kc``/``data_agent``/``refuse``).
        execution_mode: The resolved SQL execution mode (``plan``/``developer``).
        auth_mode: The resolved SQL auth mode (``adc``/``user``).
        has_token: Whether a per-user OAuth token is present in state.
        trigger: ``grounding`` (too broad) or ``sql`` (error) trigger point.

    Returns:
        ``delegate`` to hand off to CA, ``clarify`` for the grounding terminal,
        or ``refuse`` for the refusal terminal.
    """
    default = "clarify" if trigger == GROUNDING_TRIGGER else "refuse"
    if mode == KC_MODE:
        return default
    if mode == REFUSE_MODE:
        return "refuse"
    # data_agent mode: delegation executes CA SQL, so gate it deterministically.
    if execution_mode != DEVELOPER_MODE:
        # plan mode never executes; suppress to the normal terminal.
        return default
    if auth_mode != USER_AUTH_MODE:
        # Option X: CA runs only under the caller's token, never the shared SA.
        return default
    if not has_token:
        # user mode without a token: fail closed rather than delegate.
        return "refuse"
    return "delegate"


def _token_state_key() -> str:
    return (
        os.getenv(_TOKEN_STATE_KEY_ENV, _DEFAULT_TOKEN_STATE_KEY).strip()
        or _DEFAULT_TOKEN_STATE_KEY
    )


def _has_token(state: Mapping[str, Any]) -> bool:
    return bool(str(state.get(_token_state_key(), "") or "").strip())


def _resolve_route(state: Mapping[str, Any], *, trigger: str) -> str:
    return decide_fallback_route(
        mode=resolve_fallback_mode(),
        execution_mode=resolve_execution_mode(),
        auth_mode=resolve_auth_mode(),
        has_token=_has_token(state),
        trigger=trigger,
    )


def _emit(node_input: Any, question: str, route: str) -> Event:
    if route == "delegate":
        return Event(
            output=question,
            route="delegate",
            state={_QUESTION_STATE_KEY: question},
        )
    return Event(output=node_input, route=route)


@node
async def route_grounding_fallback(ctx: Context, node_input: dict[str, Any]) -> Event:
    """Route the "too broad" grounding exit to CA, clarify, or refuse.

    Args:
        ctx: Current ADK workflow context.
        node_input: The broad-grounding payload (carries ``question``).

    Returns:
        Routed event: ``delegate``, ``clarify``, or ``refuse``.
    """
    question = ""
    if isinstance(node_input, dict):
        question = str(node_input.get("question", ""))
    route = _resolve_route(ctx.state, trigger=GROUNDING_TRIGGER)
    return _emit(node_input, question, route)


@node
async def route_sql_fallback(ctx: Context, node_input: dict[str, Any]) -> Event:
    """Route the "error" SQL-refusal exit to CA or refuse.

    Args:
        ctx: Current ADK workflow context.
        node_input: The exhausted-repair payload.

    Returns:
        Routed event: ``delegate`` or ``refuse``.
    """
    context = ctx.state.get(_SQL_CONTEXT_STATE_KEY, {})
    question = ""
    if isinstance(context, dict):
        question = str(context.get("question", ""))
    route = _resolve_route(ctx.state, trigger=SQL_TRIGGER)
    return _emit(node_input, question, route)


@node
async def finish_data_agent_result(ctx: Context, node_input: Any) -> Event:
    """Return the CA fallback answer with explicit delegation provenance.

    Args:
        ctx: Current ADK workflow context.
        node_input: The delegating ``LlmAgent`` text output.

    Returns:
        Event carrying the CA answer, labelled ``reasoning_path=data_agent`` with
        ``guardrail_coverage=none`` because CA authored and executed the SQL
        outside the custom pre-execution guardrails.
    """
    answer = node_input if isinstance(node_input, str) else str(node_input or "")
    question = str(ctx.state.get(_QUESTION_STATE_KEY, "") or "")
    return Event(
        output={
            "status": "data_agent_answered",
            "reasoning_path": "data_agent",
            "guardrail_coverage": "none",
            "question": question,
            "answer": answer,
            "fallback_mode": DATA_AGENT_MODE,
            "next_step": "return_result",
        }
    )
