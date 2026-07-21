"""Tests for the Phase 1 certified analytics ADK skeleton."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

pytest.importorskip("google.adk")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from advanced.app.certified_analytics import agent  # noqa: E402


def test_route_static_intent_completed_orders_is_certified():
    """Tests completed-order questions route to the certified branch."""
    node_input = {
        "question": "Completed orders by country",
        "normalized_question": "completed orders by country",
    }

    event = agent._route_static_intent(node_input)

    assert event.actions.route == "certified"
    assert event.output == node_input


def test_certified_response_marks_phase_1_metadata():
    """Tests certified static responses include contract metadata."""
    response = agent._certified_response(
        {
            "question": "Completed orders by country",
            "normalized_question": "completed orders by country",
        }
    )

    assert response["certified"] is True
    assert response["mode"] == "certified"
    assert response["metric"] == "completed_order_count"
    assert response["contract_version"] == "thelook_orders:v1"


def test_route_static_intent_unknown_question_refuses():
    """Tests unsupported questions route to refusal without fallback."""
    event = agent._route_static_intent(
        {
            "question": "Show inventory by SKU",
            "normalized_question": "show inventory by sku",
        }
    )

    assert event.actions.route == "refuse"


def test_refusal_response_is_not_certified():
    """Tests out-of-coverage static responses are not certified."""
    response = agent._refusal_response(
        {
            "question": "Show inventory by SKU",
            "normalized_question": "show inventory by sku",
        }
    )

    assert response["certified"] is False
    assert response["mode"] == "out_of_coverage"
    assert "No exploratory fallback" in response["message"]
