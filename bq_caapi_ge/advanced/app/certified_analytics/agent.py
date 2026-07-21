"""ADK 2 workflow skeleton for certified analytics."""

from __future__ import annotations

from typing import Any

from google.adk.events.event import Event
from google.adk.workflow import Workflow


CERTIFIED_METRIC = "completed_order_count"
CONTRACT_VERSION = "thelook_orders:v1"


def _extract_text(node_input: Any) -> str:
    if isinstance(node_input, str):
        return node_input.strip()

    parts = getattr(node_input, "parts", None)
    if parts:
        text_parts = [getattr(part, "text", "") for part in parts]
        return " ".join(part for part in text_parts if part).strip()

    return str(node_input).strip()


def _normalize_question(node_input: Any) -> dict[str, str]:
    question = _extract_text(node_input)
    return {"question": question, "normalized_question": question.lower()}


def _route_static_intent(node_input: dict[str, str]) -> Event:
    normalized_question = node_input["normalized_question"]
    if "completed" in normalized_question and "order" in normalized_question:
        return Event(output=node_input, route="certified")
    return Event(output=node_input, route="refuse")


def _certified_response(node_input: dict[str, str]) -> dict[str, object]:
    question = node_input["question"]
    return {
        "certified": True,
        "mode": "certified",
        "coverage_status": "covered_static_phase_1",
        "metric": CERTIFIED_METRIC,
        "contract_version": CONTRACT_VERSION,
        "question": question,
        "message": (
            "Phase 1 static certified response. SQL compilation and BigQuery "
            "execution are not implemented yet."
        ),
    }


def _refusal_response(node_input: dict[str, str]) -> dict[str, object]:
    question = node_input["question"]
    return {
        "certified": False,
        "mode": "out_of_coverage",
        "coverage_status": "unsupported_static_phase_1",
        "question": question,
        "message": (
            "This Phase 1 skeleton only covers completed-order questions. "
            "No exploratory fallback was invoked."
        ),
    }


root_agent = Workflow(
    name="certified_analytics",
    description=(
        "Local ADK 2 workflow skeleton for certified semantic-layer analytics."
    ),
    edges=[
        ("START", _normalize_question),
        (_normalize_question, _route_static_intent),
        (
            _route_static_intent,
            {
                "certified": _certified_response,
                "refuse": _refusal_response,
            },
        ),
    ],
)
