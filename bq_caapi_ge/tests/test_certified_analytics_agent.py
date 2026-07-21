"""Tests for the certified analytics ADK workflow."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

pytest.importorskip("google.adk")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from advanced.app.certified_analytics import agent  # noqa: E402
from semantic.executor import ExecutionResult  # noqa: E402
from semantic.grounding import GroundingError, GroundingResult  # noqa: E402
from semantic.types import QueryIntent  # noqa: E402


def test_select_contract_intent_completed_orders_is_covered():
    """Tests completed-order questions route to contract compilation."""
    node_input = {
        "question": "Completed orders by country",
        "normalized_question": "completed orders by country",
    }

    event = agent._select_contract_intent(node_input)

    assert event.actions.route == "covered"
    assert event.output["intent"].metric == "completed_order_count"
    assert event.output["intent"].dimensions == ("country",)


def test_load_catalog_metadata_disabled_by_default(monkeypatch):
    """Tests catalog retrieval is explicit when disabled."""
    monkeypatch.delenv("SEMANTIC_GROUNDING_MODE", raising=False)

    output = agent._load_catalog_metadata(
        {
            "question": "Completed orders by country",
            "normalized_question": "completed orders by country",
        }
    )

    assert output["grounding"]["status"] == "disabled"
    assert output["grounding"]["mode"] == "disabled"
    assert output["grounding"]["assets"] == []


def test_load_catalog_metadata_uses_adk_bigquery_adc(monkeypatch):
    """Tests ADK catalog metadata is loaded before intent selection."""
    calls = {}

    def fake_grounding(question, project, location, dataset_id, page_size):
        calls["question"] = question
        calls["project"] = project
        calls["location"] = location
        calls["dataset_id"] = dataset_id
        calls["page_size"] = page_size
        return GroundingResult(
            status="success",
            mode="adk_bigquery_adc",
            assets=({"display_name": "orders"},),
        )

    monkeypatch.setenv("SEMANTIC_GROUNDING_MODE", "adk_bigquery_adc")
    monkeypatch.setenv("SEMANTIC_GROUNDING_PAGE_SIZE", "2")
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "project-a")
    monkeypatch.setenv("DATAPLEX_LOCATION", "us")
    monkeypatch.setenv("BIGQUERY_DATASET_ID", "thelook_ecommerce")
    monkeypatch.setattr(agent, "load_adk_bigquery_catalog_adc", fake_grounding)

    output = agent._load_catalog_metadata(
        {
            "question": "Completed orders by country",
            "normalized_question": "completed orders by country",
        }
    )

    assert calls == {
        "question": "Completed orders by country",
        "project": "project-a",
        "location": "us",
        "dataset_id": "thelook_ecommerce",
        "page_size": 2,
    }
    assert output["grounding"]["status"] == "success"
    assert output["grounding"]["assets"] == [{"display_name": "orders"}]


def test_load_catalog_metadata_continues_on_retrieval_error(monkeypatch):
    """Tests catalog errors do not block contract-only selection."""

    def fake_grounding(**_kwargs):
        raise GroundingError("permission denied")

    monkeypatch.setenv("SEMANTIC_GROUNDING_MODE", "adk_bigquery_adc")
    monkeypatch.setattr(agent, "load_adk_bigquery_catalog_adc", fake_grounding)

    output = agent._load_catalog_metadata(
        {
            "question": "Completed orders by country",
            "normalized_question": "completed orders by country",
        }
    )

    assert output["grounding"]["status"] == "error"
    assert output["grounding"]["mode"] == "adk_bigquery_adc"
    assert "permission denied" in output["grounding"]["error"]


def test_compiled_contract_response_includes_sql_metadata(monkeypatch):
    """Tests contract-valid SQL is not presented as a certified answer."""
    monkeypatch.delenv("SEMANTIC_EXECUTION_MODE", raising=False)

    response = agent._compiled_contract_response(
        {
            "question": "Completed orders by country",
            "normalized_question": "completed orders by country",
            "intent": QueryIntent(
                metric="completed_order_count",
                dimensions=("country",),
            ),
            "grounding": {
                "status": "success",
                "mode": "adk_bigquery_adc",
                "assets": [{"display_name": "orders"}],
            },
        }
    )

    assert response["certified"] is False
    assert response["contract_validated"] is True
    assert response["intent_assurance"] == "prototype_full_match_grammar"
    assert response["mode"] == "contract_compilation"
    assert response["metric"] == "completed_order_count"
    assert response["contract_version"] == "thelook_ecommerce:v1"
    assert response["dimensions"] == ["country"]
    assert "COUNT(DISTINCT orders.order_id)" in response["sql"]
    assert "FROM `thelook_ecommerce.orders` AS orders" in response["sql"]
    assert response["parameters"] == []
    assert response["job_id"] is None
    assert response["rows"] == []
    assert response["execution_mode"] == "compile_only"
    assert response["execution_status"] == "not_executed"
    assert response["credential_mode"] == "none"
    assert response["truncation_status"] == "not_applicable"
    assert response["grounding"] == {
        "status": "success",
        "mode": "adk_bigquery_adc",
        "asset_count": 1,
        "used_for_intent_selection": False,
    }


def test_compiled_contract_response_executes_adc_developer_mode(monkeypatch):
    """Tests ADC developer mode returns rows and BigQuery job metadata."""
    calls = {}

    def fake_execute(compiled, project, location, max_results, maximum_bytes_billed):
        calls["compiled"] = compiled
        calls["project"] = project
        calls["location"] = location
        calls["max_results"] = max_results
        calls["maximum_bytes_billed"] = maximum_bytes_billed
        return ExecutionResult(
            rows=({"country": "US", "completed_order_count": 10},),
            job_id="job_123",
            execution_mode="adc_developer",
        )

    monkeypatch.setenv("SEMANTIC_EXECUTION_MODE", "adc_developer")
    monkeypatch.setenv("SEMANTIC_MAX_RESULTS", "5")
    monkeypatch.setenv("SEMANTIC_MAXIMUM_BYTES_BILLED", "10485760")
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "project-a")
    monkeypatch.setenv("BIGQUERY_LOCATION", "us")
    monkeypatch.setattr(agent, "execute_adc_developer_query", fake_execute)

    response = agent._compiled_contract_response(
        {
            "question": "Completed orders by country",
            "normalized_question": "completed orders by country",
            "intent": QueryIntent(
                metric="completed_order_count",
                dimensions=("country",),
            ),
        }
    )

    assert response["certified"] is False
    assert response["job_id"] == "job_123"
    assert response["rows"] == [{"country": "US", "completed_order_count": 10}]
    assert response["execution_mode"] == "adc_developer"
    assert response["developer_mode"] is True
    assert response["credential_mode"] == "adc"
    assert response["execution_status"] == "succeeded"
    assert calls["project"] == "project-a"
    assert calls["location"] == "us"
    assert calls["max_results"] == 5
    assert calls["maximum_bytes_billed"] == 10_485_760
    assert calls["compiled"].metric == "completed_order_count"


def test_compiled_contract_response_executes_adk_bigquery_adc_mode(monkeypatch):
    """Tests lower-level ADK BigQuery ADC mode returns developer results."""
    calls = {}

    def fake_execute(compiled, project, location, max_results, maximum_bytes_billed):
        calls["compiled"] = compiled
        calls["project"] = project
        calls["location"] = location
        calls["max_results"] = max_results
        calls["maximum_bytes_billed"] = maximum_bytes_billed
        return ExecutionResult(
            rows=({"country": "US", "completed_order_count": 10},),
            job_id=None,
            execution_mode="adk_bigquery_adc",
        )

    monkeypatch.setenv("SEMANTIC_EXECUTION_MODE", "adk_bigquery_adc")
    monkeypatch.setenv("SEMANTIC_MAX_RESULTS", "5")
    monkeypatch.setenv("SEMANTIC_MAXIMUM_BYTES_BILLED", "10485760")
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "project-a")
    monkeypatch.setenv("BIGQUERY_LOCATION", "us")
    monkeypatch.setattr(agent, "execute_adk_bigquery_adc_query", fake_execute)

    response = agent._compiled_contract_response(
        {
            "question": "Completed orders by country",
            "normalized_question": "completed orders by country",
            "intent": QueryIntent(
                metric="completed_order_count",
                dimensions=("country",),
            ),
        }
    )

    assert response["certified"] is False
    assert response["job_id"] is None
    assert response["rows"] == [{"country": "US", "completed_order_count": 10}]
    assert response["execution_mode"] == "adk_bigquery_adc"
    assert response["developer_mode"] is True
    assert response["credential_mode"] == "adc"
    assert calls["project"] == "project-a"
    assert calls["location"] == "us"
    assert calls["max_results"] == 5
    assert calls["maximum_bytes_billed"] == 10_485_760
    assert calls["compiled"].metric == "completed_order_count"


def test_compiled_contract_response_execution_error_preserves_sql(monkeypatch):
    """Tests execution failures retain compiled SQL for auditability."""
    monkeypatch.setenv("SEMANTIC_EXECUTION_MODE", "unsupported")

    response = agent._compiled_contract_response(
        {
            "question": "Completed orders by country",
            "normalized_question": "completed orders by country",
            "intent": QueryIntent(
                metric="completed_order_count",
                dimensions=("country",),
            ),
        }
    )

    assert response["certified"] is False
    assert response["mode"] == "execution_error"
    assert response["coverage_status"] == "contract_execution_failed"
    assert response["execution_mode"] == "unsupported"
    assert response["metric"] == "completed_order_count"
    assert "COUNT(DISTINCT orders.order_id)" in response["sql"]
    assert "unsupported semantic execution mode" in response["reason"]


def test_select_contract_intent_unknown_question_refuses():
    """Tests unsupported questions route to refusal without fallback."""
    event = agent._select_contract_intent(
        {
            "question": "Show inventory by SKU",
            "normalized_question": "show inventory by sku",
        }
    )

    assert event.actions.route == "refuse"


def test_compiled_contract_response_refuses_validation_failure():
    """Tests validation failures do not fall back or appear certified."""
    response = agent._compiled_contract_response(
        {
            "question": "Completed orders by user",
            "normalized_question": "completed orders by user",
            "intent": QueryIntent(
                metric="completed_order_count",
                dimensions=("user_id",),
            ),
        }
    )

    assert response["certified"] is False
    assert response["mode"] == "out_of_coverage"
    assert response["coverage_status"] == "contract_validation_failed"
    assert "not allowed" in response["reason"]
    assert "No exploratory fallback" in response["message"]


def test_select_contract_intent_preserves_unsupported_dimension():
    """Tests unsupported dimensions reach compiler validation instead of dropping."""
    event = agent._select_contract_intent(
        {
            "question": "Completed orders by user",
            "normalized_question": "completed orders by user",
        }
    )

    assert event.actions.route == "covered"
    assert event.output["intent"].dimensions == ("user_id",)

    response = agent._compiled_contract_response(event.output)
    assert response["certified"] is False
    assert response["coverage_status"] == "contract_validation_failed"


@pytest.mark.parametrize(
    "question",
    [
        "Sales for cancelled orders in 2025",
        "Completed orders last quarter",
        "Revenue where country is US",
        "Top countries by revenue",
        "Revenue for France",
        "Revenue by product category",
    ],
)
def test_select_contract_intent_refuses_unrepresented_constraints(question):
    """Tests the prototype selector fails closed on unrepresented constraints."""
    event = agent._select_contract_intent(
        {
            "question": question,
            "normalized_question": question.lower(),
        }
    )

    assert event.actions.route == "refuse"
    assert event.output["coverage_status"] == "unsupported_question_constraints"


def test_select_contract_intent_preserves_top_user_limit():
    """Tests the full-match prototype grammar preserves an explicit limit."""
    event = agent._select_contract_intent(
        {
            "question": "Top 5 users by sales",
            "normalized_question": "top 5 users by sales",
        }
    )

    assert event.actions.route == "covered"
    assert event.output["intent"].metric == "top_users_by_completed_revenue"
    assert event.output["intent"].limit == 5


def test_select_contract_intent_singular_top_user_means_one():
    """Tests singular ranking language preserves an implied limit of one."""
    event = agent._select_contract_intent(
        {
            "question": "Best customer by revenue",
            "normalized_question": "best customer by revenue",
        }
    )

    assert event.actions.route == "covered"
    assert event.output["intent"].limit == 1


@pytest.mark.parametrize("limit", ["0", "1001", "9" * 5000])
def test_select_contract_intent_refuses_unsafe_top_user_limit(limit):
    """Tests prototype ranking limits are bounded before integer conversion."""
    question = f"Top {limit} users by sales"

    event = agent._select_contract_intent(
        {
            "question": question,
            "normalized_question": question.lower(),
        }
    )

    assert event.actions.route == "refuse"


def test_select_contract_intent_does_not_match_incomplete_as_complete():
    """Tests metric phrase matching uses word boundaries."""
    event = agent._select_contract_intent(
        {
            "question": "Incomplete orders",
            "normalized_question": "incomplete orders",
        }
    )

    assert event.actions.route == "refuse"


def test_refusal_response_is_not_certified():
    """Tests out-of-coverage responses are not certified."""
    response = agent._refusal_response(
        {
            "question": "Show inventory by SKU",
            "normalized_question": "show inventory by sku",
        }
    )

    assert response["certified"] is False
    assert response["mode"] == "out_of_coverage"
    assert "No exploratory fallback" in response["message"]
