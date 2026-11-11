"""Tests for the domain-neutral semantic analytics workflow."""

from __future__ import annotations

import asyncio
from dataclasses import replace
import json
from pathlib import Path
import sys

import pytest

pytest.importorskip("google.adk")

from pydantic import Field  # noqa: E402

from google.adk.runners import Runner  # noqa: E402
from google.adk.models import BaseLlm, LlmRequest, LlmResponse  # noqa: E402
from google.adk.sessions import InMemorySessionService  # noqa: E402
from google.adk.workflow import Workflow  # noqa: E402
from google.genai import types  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

agent = pytest.importorskip("advanced.app.semantic_analytics.agent")  # noqa: E402
from semantic.registry import load_contract, load_contracts  # noqa: E402
from semantic.runtime import (  # noqa: E402
    SemanticConceptSelection,
    SemanticFilterSelection,
    SemanticSelection,
    load_semantic_registry,
    recover_invalid_semantic_selection,
    resolve_selection,
    resolve_semantic_selection,
    try_compile_narrow_selection,
)
from semantic.types import Dimension, Table, TableSource  # noqa: E402


class _ScriptedLlm(BaseLlm):
    response: LlmResponse
    requests: list[LlmRequest] = Field(default_factory=list, exclude=True)

    async def generate_content_async(
        self,
        llm_request: LlmRequest,
        stream: bool = False,
    ):
        assert stream is False
        self.requests.append(llm_request)
        yield self.response


def _scripted_model(text: str) -> _ScriptedLlm:
    return _ScriptedLlm(
        model="scripted",
        response=LlmResponse(
            content=types.Content(role="model", parts=[types.Part(text=text)])
        ),
    )


def test_agent_builds_domain_neutral_semantic_workflow():
    """Tests the discoverable app exposes the semantic selection graph."""
    assert agent.root_agent.name == "semantic_analytics"
    assert agent.semantic_selector.output_schema is SemanticSelection
    assert agent.root_agent.graph is not None
    assert "untrusted data" in agent.semantic_selector.instruction


def test_load_semantic_registry_derives_unrelated_domain_from_yaml(
    monkeypatch,
    tmp_path,
):
    """Tests adding and naming an unrelated domain requires only YAML."""
    contract_path = _write_weather_contract(tmp_path)
    monkeypatch.setenv("SEMANTIC_CONTRACT_PATH", str(contract_path))

    event = load_semantic_registry("Temperature by sensor location")

    assert event.output == {
        "question": "Temperature by sensor location",
        "semantic_candidates": [
            {
                "id": "weather_observations",
                "version": 3,
                "description": "Weather station temperature observations.",
                "routing_terms": ["weather", "temperature", "stations"],
                "examples": ["What is the temperature by station?"],
                "relationships": [],
                "dimensions": [
                    {
                        "name": "sensor_location",
                        "label": "Weather Station",
                        "description": "Station reporting the observation.",
                        "synonyms": ["station"],
                    }
                ],
                "metrics": [
                    {
                        "name": "observation_total",
                        "label": "Reading Count",
                        "description": "Number of weather observations.",
                        "synonyms": [],
                    }
                ],
            }
        ],
    }
    assert event.actions.state_delta == {
        "semantic_question": "Temperature by sensor location",
        "temp:semantic_selector_output_invalid": False,
    }


def test_resolve_selection_expands_only_selected_concepts_and_sources(tmp_path):
    """Tests a valid selection produces a narrow source closure."""
    contract_path = _write_weather_contract(tmp_path)
    selection = SemanticSelection(
        selected_contexts=[
            SemanticConceptSelection(
                context_id="weather_observations",
                context_version=3,
                metric_ids=["observation_total"],
                dimension_ids=["sensor_location"],
            )
        ],
        reason="The configured metric and dimension match.",
    )

    output, route = resolve_selection(
        question="Count observations by station",
        contracts=load_contracts(contract_path),
        selection=selection,
    )

    assert route == "semantic_narrow"
    assert output["reasoning_path"] == "semantic_narrow"
    assert output["semantic_context_used"] is True
    assert output["semantic_context_ids"] == ["weather_observations"]
    assert output["semantic_context_versions"] == ["weather_observations:v3"]
    assert output["semantic_source_names"] == ["example-project.climate.readings"]
    assert [metric["name"] for metric in output["semantic_contexts"][0]["metrics"]] == [
        "observation_total"
    ]
    assert [
        dimension["name"] for dimension in output["semantic_contexts"][0]["dimensions"]
    ] == ["sensor_location"]
    assert output["next_step"] == "narrow_catalog_grounding"


def test_resolve_selection_metric_only_uses_base_table(monkeypatch):
    """Tests metric relationship guidance does not widen the source closure."""
    monkeypatch.delenv("SEMANTIC_CONTRACT_PATH", raising=False)
    contract = load_contract()
    selection = SemanticSelection(
        selected_contexts=[
            SemanticConceptSelection(
                context_id=contract.id,
                context_version=contract.version,
                metric_ids=["completed_revenue"],
            )
        ],
        reason="The configured metric matches.",
    )

    output, route = resolve_selection(
        question="Show completed revenue",
        contracts=(contract,),
        selection=selection,
    )

    assert route == "semantic_narrow"
    assert output["semantic_source_names"] == [
        "bigquery-public-data.thelook_ecommerce.order_items"
    ]
    context = output["semantic_contexts"][0]
    assert context["relationships"] == []
    assert context["metrics"][0]["relationship_path"] == []


def test_resolve_selection_rejects_relationship_outside_metric_path(monkeypatch):
    """Tests model-selected relationships cannot widen a metric source scope."""
    monkeypatch.delenv("SEMANTIC_CONTRACT_PATH", raising=False)
    contract = load_contract()
    selection = SemanticSelection(
        selected_contexts=[
            SemanticConceptSelection(
                context_id=contract.id,
                context_version=contract.version,
                metric_ids=["completed_order_count"],
                relationship_ids=["orders__order_items"],
            )
        ],
        reason="The relationship is configured but unrelated to the metric.",
    )

    output, route = resolve_selection(
        question="Count completed orders",
        contracts=(contract,),
        selection=selection,
    )

    assert route == "catalog_broad"
    assert output["semantic_source_names"] == []
    assert "outside the selected metric paths" in output["selection_error"]


def test_resolve_selection_adds_only_relationships_needed_for_dimension(monkeypatch):
    """Tests remote selected dimensions produce a connected minimal closure."""
    monkeypatch.delenv("SEMANTIC_CONTRACT_PATH", raising=False)
    contract = load_contract()
    selection = SemanticSelection(
        selected_contexts=[
            SemanticConceptSelection(
                context_id=contract.id,
                context_version=contract.version,
                metric_ids=["completed_revenue"],
                dimension_ids=["country"],
            )
        ],
        reason="The metric and geography dimension match.",
    )

    output, route = resolve_selection(
        question="Completed revenue by country",
        contracts=(contract,),
        selection=selection,
    )

    assert route == "semantic_narrow"
    assert [
        relationship["name"]
        for relationship in output["semantic_contexts"][0]["relationships"]
    ] == ["orders__order_items", "users__orders"]
    assert output["semantic_contexts"][0]["resolution"] == {
        "injected_dimension_ids": [],
        "injected_relationship_ids": ["orders__order_items", "users__orders"],
    }


def test_resolve_selection_routes_disconnected_concepts_broad(tmp_path):
    """Tests disconnected selected tables cannot use the narrow route."""
    contract = load_contracts(_write_weather_contract(tmp_path))[0]
    disconnected_contract = replace(
        contract,
        tables={
            **contract.tables,
            "forecasts": Table(
                name="forecasts",
                source=TableSource(
                    project="example-project",
                    dataset="climate",
                    table="forecasts",
                ),
                primary_key="forecast_id",
                grain="forecast",
            ),
        },
        dimensions={
            **contract.dimensions,
            "forecast_region": Dimension(
                name="forecast_region",
                label="Forecast Region",
                description="Region associated with a forecast.",
                table="forecasts",
                sql="forecasts.region_id",
            ),
        },
    )
    selection = SemanticSelection(
        selected_contexts=[
            SemanticConceptSelection(
                context_id=contract.id,
                context_version=contract.version,
                metric_ids=["observation_total"],
                dimension_ids=["forecast_region"],
            )
        ],
        reason="The selected concepts are disconnected.",
    )

    output, route = resolve_selection(
        question="Observations by forecast region",
        contracts=(disconnected_contract,),
        selection=selection,
    )

    assert route == "catalog_broad"
    assert output["route_cause"] == "invalid_selection"
    assert "disconnected tables" in output["selection_error"]


def test_resolve_selection_preserves_partial_context_for_broad_catalog(tmp_path):
    """Tests unresolved needs retain selected context during broad discovery."""
    contract_path = _write_weather_contract(tmp_path)
    selection = SemanticSelection(
        selected_contexts=[
            SemanticConceptSelection(
                context_id="weather_observations",
                context_version=3,
                metric_ids=["observation_total"],
            )
        ],
        requires_broad_catalog=True,
        reason="The requested forecast source is not configured.",
    )

    output, route = resolve_selection(
        question="Compare observations with forecasts",
        contracts=load_contracts(contract_path),
        selection=selection,
    )

    assert route == "catalog_broad"
    assert output["status"] == "semantic_context_partial"
    assert output["reasoning_path"] == "catalog_broad"
    assert output["semantic_context_used"] is True
    assert output["next_step"] == "broad_catalog_grounding"


def test_resolve_selection_routes_oversized_expanded_context_broad(monkeypatch):
    """Tests valid concept IDs cannot bypass the expanded-context size bound."""
    monkeypatch.delenv("SEMANTIC_CONTRACT_PATH", raising=False)
    contract = replace(load_contract(), description="x" * 100_000)
    selection = SemanticSelection(
        selected_contexts=[
            SemanticConceptSelection(
                context_id=contract.id,
                context_version=contract.version,
                metric_ids=["completed_revenue"],
            )
        ],
        reason="The configured metric matches.",
    )

    output, route = resolve_selection(
        question="Show completed revenue",
        contracts=(contract,),
        selection=selection,
    )

    assert route == "catalog_broad"
    assert output["route_cause"] == "context_limit_exceeded"
    assert output["semantic_contexts"] == []
    assert "100000 bytes" in output["selection_error"]


@pytest.mark.parametrize(
    ("selection", "expected_error"),
    [
        (
            SemanticSelection(
                selected_contexts=[],
                reason="No configured context applies.",
            ),
            None,
        ),
        (
            SemanticSelection(
                selected_contexts=[
                    SemanticConceptSelection(
                        context_id="invented_domain",
                        context_version=1,
                        metric_ids=["invented_metric"],
                    )
                ],
                reason="Invalid model output.",
            ),
            "unknown semantic context IDs: ['invented_domain']",
        ),
        (
            SemanticSelection(
                selected_contexts=[
                    SemanticConceptSelection(
                        context_id="weather_observations",
                        context_version=3,
                        metric_ids=["invented_metric"],
                    )
                ],
                reason="Invalid model output.",
            ),
            "unknown metric IDs for weather_observations: ['invented_metric']",
        ),
        (
            SemanticSelection(
                selected_contexts=[
                    SemanticConceptSelection(
                        context_id="weather_observations",
                        context_version=3,
                        metric_ids=["observation_total", "observation_total"],
                    )
                ],
                reason="Duplicate model output.",
            ),
            "duplicate metric IDs for weather_observations: ['observation_total']",
        ),
        (
            SemanticSelection(
                selected_contexts=[
                    SemanticConceptSelection(
                        context_id="weather_observations",
                        context_version=2,
                        metric_ids=["observation_total"],
                    )
                ],
                reason="Stale model output.",
            ),
            (
                "semantic context version changed for weather_observations: "
                "selected v2, current v3"
            ),
        ),
    ],
)
def test_resolve_selection_routes_misses_to_broad_catalog(
    tmp_path,
    selection,
    expected_error,
):
    """Tests empty and invalid selections continue to broad discovery."""
    contract_path = _write_weather_contract(tmp_path)

    output, route = resolve_selection(
        question="An unrelated question",
        contracts=load_contracts(contract_path),
        selection=selection,
    )

    assert route == "catalog_broad"
    assert output["status"] == "semantic_context_not_found"
    assert output["semantic_context_used"] is False
    assert output["semantic_context_ids"] == []
    assert output["semantic_contexts"] == []
    assert output["next_step"] == "broad_catalog_grounding"
    assert output.get("selection_error") == expected_error


def test_semantic_workflow_propagates_state_and_routes_without_model(
    monkeypatch,
    tmp_path,
):
    """Tests the active stateful node chain through an ADK Runner."""
    contract_path = _write_weather_contract(tmp_path)
    monkeypatch.setenv("SEMANTIC_CONTRACT_PATH", str(contract_path))

    outputs, session = asyncio.run(
        _run_workflow(_select_weather_concepts, "Count observations by station")
    )

    final_output = outputs[-1]
    assert final_output["reasoning_path"] == "semantic_narrow"
    assert final_output["semantic_source_names"] == ["example-project.climate.readings"]
    assert session.state["semantic_question"] == "Count observations by station"


def test_semantic_workflow_routes_malformed_selector_output_broad(
    monkeypatch,
    tmp_path,
):
    """Tests malformed output delivered to the resolver routes broad."""
    contract_path = _write_weather_contract(tmp_path)
    monkeypatch.setenv("SEMANTIC_CONTRACT_PATH", str(contract_path))

    outputs, _ = asyncio.run(
        _run_workflow(_select_malformed_context, "Count observations")
    )

    final_output = outputs[-1]
    assert final_output["reasoning_path"] == "catalog_broad"
    assert final_output["route_cause"] == "invalid_selection"
    assert final_output["semantic_context_used"] is False
    assert "validation error" in final_output["selection_error"]


def test_semantic_workflow_propagates_installed_llm_structured_output(
    monkeypatch,
    tmp_path,
):
    """Tests installed LlmAgent structured output reaches semantic routing."""
    contract_path = _write_weather_contract(tmp_path)
    monkeypatch.setenv("SEMANTIC_CONTRACT_PATH", str(contract_path))
    scripted_model = _ScriptedLlm(
        model="scripted-semantic-selector",
        response=LlmResponse(
            content=types.Content(
                role="model",
                parts=[types.Part(text=json.dumps(_weather_selection()))],
            )
        ),
    )
    selector = agent.semantic_selector.model_copy(
        update={"model": scripted_model, "parent_agent": None}
    )

    outputs, _ = asyncio.run(_run_workflow(selector, "Count observations by station"))

    final_output = outputs[-1]
    assert final_output["reasoning_path"] == "semantic_narrow"
    assert final_output["semantic_source_names"] == ["example-project.climate.readings"]
    request = scripted_model.requests[0]
    assert request.config.response_schema is SemanticSelection
    assert request.config.response_mime_type == "application/json"
    request_text = "".join(
        part.text or "" for content in request.contents for part in content.parts or []
    )
    assert "weather_observations" in request_text


def test_semantic_workflow_recovers_schema_invalid_llm_output_broad(
    monkeypatch,
    tmp_path,
):
    """Tests malformed successful model output continues with broad discovery."""
    contract_path = _write_weather_contract(tmp_path)
    monkeypatch.setenv("SEMANTIC_CONTRACT_PATH", str(contract_path))
    scripted_model = _ScriptedLlm(
        model="scripted-invalid-selector",
        response=LlmResponse(
            content=types.Content(
                role="model",
                parts=[
                    types.Part(
                        text=(
                            '{"selected_contexts":"not-a-list",'
                            '"reason":"Malformed output."}'
                        )
                    )
                ],
            )
        ),
    )
    selector = agent.semantic_selector.model_copy(
        update={"model": scripted_model, "parent_agent": None}
    )

    outputs, _ = asyncio.run(_run_workflow(selector, "Count observations"))

    final_output = outputs[-1]
    assert final_output["reasoning_path"] == "catalog_broad"
    assert final_output["route_cause"] == "invalid_selection"
    assert final_output["semantic_context_used"] is False
    assert final_output["selection_error"] == (
        "semantic selector returned schema-invalid output"
    )


def test_selector_recovery_preserves_provider_errors():
    """Tests provider failures remain hard failures instead of semantic misses."""
    response = LlmResponse(
        error_code="RESOURCE_EXHAUSTED",
        error_message="Provider quota exceeded.",
    )

    assert recover_invalid_semantic_selection(None, response) is None


def _select_weather_concepts(node_input):
    assert node_input["semantic_candidates"][0]["id"] == "weather_observations"
    return _weather_selection()


def _weather_selection():
    return {
        "selected_contexts": [
            {
                "context_id": "weather_observations",
                "context_version": 3,
                "metric_ids": ["observation_total"],
                "dimension_ids": ["sensor_location"],
                "relationship_ids": [],
            }
        ],
        "requires_broad_catalog": False,
        "reason": "Configured concepts match.",
    }


def _select_malformed_context(node_input):
    assert node_input["semantic_candidates"]
    return {
        "selected_contexts": "not-a-list",
        "reason": "Malformed output.",
    }


def _finish_narrow_node(node_input):
    return node_input


def _finish_broad_node(node_input):
    return node_input


async def _run_workflow(selector, question):
    selector_name = getattr(selector, "name", None) or selector.__name__
    workflow = Workflow(
        name=f"semantic_runtime_{selector_name.strip('_')}",
        edges=[
            ("START", load_semantic_registry, selector),
            (selector, resolve_semantic_selection),
            (
                resolve_semantic_selection,
                {
                    "semantic_narrow": _finish_narrow_node,
                    "catalog_broad": _finish_broad_node,
                },
            ),
        ],
    )
    session_service = InMemorySessionService()
    await session_service.create_session(
        app_name="semantic_test",
        user_id="user",
        session_id="session",
    )
    runner = Runner(
        agent=workflow,
        app_name="semantic_test",
        session_service=session_service,
    )
    outputs = []
    async for event in runner.run_async(
        user_id="user",
        session_id="session",
        new_message=types.Content(
            role="user",
            parts=[types.Part(text=question)],
        ),
    ):
        if event.output is not None:
            outputs.append(event.output)
    session = await session_service.get_session(
        app_name="semantic_test",
        user_id="user",
        session_id="session",
    )
    return outputs, session


def _write_weather_contract(tmp_path: Path) -> Path:
    contract_path = tmp_path / "weather.yaml"
    contract_path.write_text(
        """id: weather_observations
version: 3
owner: climate-team
description: Weather station temperature observations.
routing_terms: [weather, temperature, stations]
examples:
  - What is the temperature by station?
tables:
  readings:
    source:
      project: example-project
      dataset: climate
      table: readings
    primary_key: reading_id
    grain: weather reading
joins: {}
dimensions:
  sensor_location:
    label: Weather Station
    description: Station reporting the observation.
    table: readings
    sql: readings.station_id
    synonyms: [station]
metrics:
  observation_total:
    label: Reading Count
    description: Number of weather observations.
    type: count_distinct
    base_table: readings
    sql: readings.reading_id
    allowed_dimensions: [sensor_location]
    join_path: []
    allowed_filters: {}
""",
        encoding="utf-8",
    )
    return contract_path


class _MultiResponseLlm(BaseLlm):
    model: str = "multi"
    responses: list[LlmResponse] = Field(default_factory=list)
    requests: list[LlmRequest] = Field(default_factory=list, exclude=True)

    async def generate_content_async(
        self,
        llm_request: LlmRequest,
        stream: bool = False,
    ):
        assert stream is False
        self.requests.append(llm_request)
        idx = min(len(self.requests) - 1, len(self.responses) - 1)
        yield self.responses[idx]


def test_negative_tier1_eligibility_routes_to_tier2() -> None:
    contracts_by_id = {c.id: c for c in load_contracts()}
    contract = contracts_by_id["thelook_orders"]

    # 1. "Which 5 users generated the most completed revenue?" without limit=5 (limit=None)
    sel1 = SemanticSelection(
        selected_contexts=[
            SemanticConceptSelection(
                context_id=contract.id,
                context_version=contract.version,
                metric_ids=["top_users_by_completed_revenue"],
                dimension_ids=["user_id"],
                limit=None,
            )
        ],
        reason="Top users without matching limit",
    )
    res1 = try_compile_narrow_selection(
        "Which 5 users generated the most completed revenue?",
        sel1,
        contracts_by_id,
    )
    assert res1 is None

    # 2. "Top five users by completed revenue" without limit=5 (spelled out "five", limit=10)
    sel2 = SemanticSelection(
        selected_contexts=[
            SemanticConceptSelection(
                context_id=contract.id,
                context_version=contract.version,
                metric_ids=["top_users_by_completed_revenue"],
                dimension_ids=["user_id"],
                limit=10,
            )
        ],
        reason="Top users with mismatched limit",
    )
    res2 = try_compile_narrow_selection(
        "Top five users by completed revenue",
        sel2,
        contracts_by_id,
    )
    assert res2 is None

    # 3. "Completed revenue in 2025" (temporal word without filter)
    sel3 = SemanticSelection(
        selected_contexts=[
            SemanticConceptSelection(
                context_id=contract.id,
                context_version=contract.version,
                metric_ids=["completed_revenue"],
                dimension_ids=[],
            )
        ],
        reason="Completed revenue in 2025",
    )
    res3 = try_compile_narrow_selection(
        "Completed revenue in 2025",
        sel3,
        contracts_by_id,
    )
    assert res3 is None

    # 4. "Completed revenue from female users by country" (unmodeled token "female")
    sel4 = SemanticSelection(
        selected_contexts=[
            SemanticConceptSelection(
                context_id=contract.id,
                context_version=contract.version,
                metric_ids=["completed_revenue"],
                dimension_ids=["country"],
            )
        ],
        reason="Completed revenue with female modifier",
    )
    res4 = try_compile_narrow_selection(
        "Completed revenue from female users by country",
        sel4,
        contracts_by_id,
    )
    assert res4 is None


def test_h1_and_m4_tier1_eligibility_and_canonical_positives() -> None:
    contracts_by_id = {c.id: c for c in load_contracts()}
    orders_contract = contracts_by_id["thelook_orders"]
    inv_contract = contracts_by_id["thelook_inventory"]

    # 1. H1-1: "Who are the bottom 5 users by completed revenue?" -> None
    sel_h1_1 = SemanticSelection(
        selected_contexts=[
            SemanticConceptSelection(
                context_id=orders_contract.id,
                context_version=orders_contract.version,
                metric_ids=["top_users_by_completed_revenue"],
                dimension_ids=["user_id"],
                limit=5,
            )
        ],
        reason="Bottom users",
    )
    assert (
        try_compile_narrow_selection(
            "Who are the bottom 5 users by completed revenue?",
            sel_h1_1,
            contracts_by_id,
        )
        is None
    )

    # 2. H1-2: "What is the average completed revenue in the United States?" -> None (metric is sum, not avg)
    sel_h1_2 = SemanticSelection(
        selected_contexts=[
            SemanticConceptSelection(
                context_id=orders_contract.id,
                context_version=orders_contract.version,
                metric_ids=["completed_revenue"],
                dimension_ids=["country"],
                filters=[
                    SemanticFilterSelection(
                        dimension_id="country",
                        op="=",
                        values=["United States"],
                    )
                ],
            )
        ],
        reason="Average completed revenue",
    )
    assert (
        try_compile_narrow_selection(
            "What is the average completed revenue in the United States?",
            sel_h1_2,
            contracts_by_id,
        )
        is None
    )

    # 3. H1-3: "What share of completed revenue is from the United States?" -> None (metric is sum, not ratio)
    sel_h1_3 = SemanticSelection(
        selected_contexts=[
            SemanticConceptSelection(
                context_id=orders_contract.id,
                context_version=orders_contract.version,
                metric_ids=["completed_revenue"],
                dimension_ids=["country"],
                filters=[
                    SemanticFilterSelection(
                        dimension_id="country",
                        op="=",
                        values=["United States"],
                    )
                ],
            )
        ],
        reason="Share of completed revenue",
    )
    assert (
        try_compile_narrow_selection(
            "What share of completed revenue is from the United States?",
            sel_h1_3,
            contracts_by_id,
        )
        is None
    )

    # 4. H1-4: "Total unique customers with completed orders?" -> None (metric counts orders, not distinct customers)
    sel_h1_4 = SemanticSelection(
        selected_contexts=[
            SemanticConceptSelection(
                context_id=orders_contract.id,
                context_version=orders_contract.version,
                metric_ids=["completed_order_count"],
                dimension_ids=[],
            )
        ],
        reason="Unique customers count",
    )
    assert (
        try_compile_narrow_selection(
            "Total unique customers with completed orders?",
            sel_h1_4,
            contracts_by_id,
        )
        is None
    )

    # 5. H1-5: "How many orders are there?" -> None (metric requires Complete qualifier)
    sel_h1_5 = SemanticSelection(
        selected_contexts=[
            SemanticConceptSelection(
                context_id=orders_contract.id,
                context_version=orders_contract.version,
                metric_ids=["completed_order_count"],
                dimension_ids=[],
            )
        ],
        reason="Orders count",
    )
    assert (
        try_compile_narrow_selection(
            "How many orders are there?",
            sel_h1_5,
            contracts_by_id,
        )
        is None
    )

    # 6. M4: "How many completed orders were placed in USA or Brazil?" -> None (multi-value IN filter)
    sel_m4 = SemanticSelection(
        selected_contexts=[
            SemanticConceptSelection(
                context_id=orders_contract.id,
                context_version=orders_contract.version,
                metric_ids=["completed_order_count"],
                dimension_ids=["country"],
                filters=[
                    SemanticFilterSelection(
                        dimension_id="country",
                        op="IN",
                        values=["USA", "Brazil"],
                    )
                ],
            )
        ],
        reason="Multi-value country filter",
    )
    assert (
        try_compile_narrow_selection(
            "How many completed orders were placed in USA or Brazil?",
            sel_m4,
            contracts_by_id,
        )
        is None
    )

    # Canonical Tier 1 positives:
    # Pos 1: "How many completed orders were placed?"
    sel_p1 = SemanticSelection(
        selected_contexts=[
            SemanticConceptSelection(
                context_id=orders_contract.id,
                context_version=orders_contract.version,
                metric_ids=["completed_order_count"],
                dimension_ids=[],
            )
        ],
        reason="Canonical completed orders",
    )
    res_p1 = try_compile_narrow_selection(
        "How many completed orders were placed?",
        sel_p1,
        contracts_by_id,
    )
    assert res_p1 is not None
    assert "completed_order_count" in res_p1["sql"]

    # Pos 2: "How many completed orders were placed in the United States?"
    sel_p2 = SemanticSelection(
        selected_contexts=[
            SemanticConceptSelection(
                context_id=orders_contract.id,
                context_version=orders_contract.version,
                metric_ids=["completed_order_count"],
                dimension_ids=["country"],
                filters=[
                    SemanticFilterSelection(
                        dimension_id="country",
                        op="=",
                        values=["United States"],
                    )
                ],
            )
        ],
        reason="Canonical completed orders with country filter",
    )
    res_p2 = try_compile_narrow_selection(
        "How many completed orders were placed in the United States?",
        sel_p2,
        contracts_by_id,
    )
    assert res_p2 is not None
    assert "completed_order_count" in res_p2["sql"]

    # Pos 3: "What is the total completed revenue?"
    sel_p3 = SemanticSelection(
        selected_contexts=[
            SemanticConceptSelection(
                context_id=orders_contract.id,
                context_version=orders_contract.version,
                metric_ids=["completed_revenue"],
                dimension_ids=[],
            )
        ],
        reason="Canonical completed revenue",
    )
    res_p3 = try_compile_narrow_selection(
        "What is the total completed revenue?",
        sel_p3,
        contracts_by_id,
    )
    assert res_p3 is not None
    assert "completed_revenue" in res_p3["sql"]

    # Pos 4: "What is the average completed order value by country?"
    sel_p4 = SemanticSelection(
        selected_contexts=[
            SemanticConceptSelection(
                context_id=orders_contract.id,
                context_version=orders_contract.version,
                metric_ids=["average_order_value"],
                dimension_ids=["country"],
            )
        ],
        reason="Canonical average completed order value by country",
    )
    res_p4 = try_compile_narrow_selection(
        "What is the average completed order value by country?",
        sel_p4,
        contracts_by_id,
    )
    assert res_p4 is not None
    assert "average_order_value" in res_p4["sql"]

    # Pos 5: "How many inventory items are currently available?"
    sel_p5 = SemanticSelection(
        selected_contexts=[
            SemanticConceptSelection(
                context_id=inv_contract.id,
                context_version=inv_contract.version,
                metric_ids=["available_inventory_item_count"],
                dimension_ids=[],
            )
        ],
        reason="Canonical available inventory items",
    )
    res_p5 = try_compile_narrow_selection(
        "How many inventory items are currently available?",
        sel_p5,
        contracts_by_id,
    )
    assert res_p5 is not None
    assert "available_inventory_item_count" in res_p5["sql"]

    # Pos 6: "How many distinct products are in the catalog?"
    sel_p6 = SemanticSelection(
        selected_contexts=[
            SemanticConceptSelection(
                context_id=inv_contract.id,
                context_version=inv_contract.version,
                metric_ids=["product_count"],
                dimension_ids=[],
            )
        ],
        reason="Canonical product count",
    )
    res_p6 = try_compile_narrow_selection(
        "How many distinct products are in the catalog?",
        sel_p6,
        contracts_by_id,
    )
    assert res_p6 is not None
    assert "product_count" in res_p6["sql"]


def test_tier1_negative_qualifier_and_stopword_checks() -> None:
    contracts_by_id = {c.id: c for c in load_contracts()}
    orders_contract = contracts_by_id["thelook_orders"]
    inv_contract = contracts_by_id["thelook_inventory"]

    negatives = [
        (
            "How many products were ordered?",
            SemanticSelection(
                selected_contexts=[
                    SemanticConceptSelection(
                        context_id=inv_contract.id,
                        context_version=1,
                        metric_ids=["product_count"],
                        dimension_ids=[],
                    )
                ],
                reason="test1",
            ),
        ),
        (
            "How many products were ordered by each distribution center?",
            SemanticSelection(
                selected_contexts=[
                    SemanticConceptSelection(
                        context_id=inv_contract.id,
                        context_version=1,
                        metric_ids=["product_count"],
                        dimension_ids=["distribution_center"],
                    )
                ],
                reason="test2",
            ),
        ),
        (
            "How many products were placed?",
            SemanticSelection(
                selected_contexts=[
                    SemanticConceptSelection(
                        context_id=inv_contract.id,
                        context_version=1,
                        metric_ids=["product_count"],
                        dimension_ids=[],
                    )
                ],
                reason="test3",
            ),
        ),
        (
            "How many products were generated?",
            SemanticSelection(
                selected_contexts=[
                    SemanticConceptSelection(
                        context_id=inv_contract.id,
                        context_version=1,
                        metric_ids=["product_count"],
                        dimension_ids=[],
                    )
                ],
                reason="test4",
            ),
        ),
        (
            "How many products are held by each distribution center?",
            SemanticSelection(
                selected_contexts=[
                    SemanticConceptSelection(
                        context_id=inv_contract.id,
                        context_version=1,
                        metric_ids=["product_count"],
                        dimension_ids=["distribution_center"],
                    )
                ],
                reason="test5",
            ),
        ),
        (
            "How many orders were placed?",
            SemanticSelection(
                selected_contexts=[
                    SemanticConceptSelection(
                        context_id=orders_contract.id,
                        context_version=1,
                        metric_ids=["completed_order_count"],
                        dimension_ids=[],
                    )
                ],
                reason="test6",
            ),
        ),
        (
            "What is the total revenue?",
            SemanticSelection(
                selected_contexts=[
                    SemanticConceptSelection(
                        context_id=orders_contract.id,
                        context_version=1,
                        metric_ids=["completed_revenue"],
                        dimension_ids=[],
                    )
                ],
                reason="test7",
            ),
        ),
        (
            "How many inventory items are there on each distribution center?",
            SemanticSelection(
                selected_contexts=[
                    SemanticConceptSelection(
                        context_id=inv_contract.id,
                        context_version=1,
                        metric_ids=["available_inventory_item_count"],
                        dimension_ids=["distribution_center"],
                    )
                ],
                reason="test8",
            ),
        ),
        (
            "How many inventory items are held by each distribution center?",
            SemanticSelection(
                selected_contexts=[
                    SemanticConceptSelection(
                        context_id=inv_contract.id,
                        context_version=1,
                        metric_ids=["available_inventory_item_count"],
                        dimension_ids=["distribution_center"],
                    )
                ],
                reason="test9",
            ),
        ),
        (
            "How many users are in the United States?",
            SemanticSelection(
                selected_contexts=[
                    SemanticConceptSelection(
                        context_id=orders_contract.id,
                        context_version=1,
                        metric_ids=["active_buyer_rate"],
                        dimension_ids=["country"],
                        filters=[
                            SemanticFilterSelection(
                                dimension_id="country",
                                op="=",
                                values=["United States"],
                            )
                        ],
                    )
                ],
                reason="test10",
            ),
        ),
    ]

    for q, sel in negatives:
        assert try_compile_narrow_selection(q, sel, contracts_by_id) is None

    # M-1: Compound conjunctions and misgrouped dimension phrases must route to Tier 2
    m1_negatives = [
        (
            "How many completed orders and users are there by country?",
            SemanticSelection(
                selected_contexts=[
                    SemanticConceptSelection(
                        context_id="thelook_orders",
                        context_version=1,
                        metric_ids=["completed_order_count"],
                        dimension_ids=["country"],
                    )
                ],
                reason="compound metric",
            ),
        ),
        (
            "What is the completed revenue by country and user?",
            SemanticSelection(
                selected_contexts=[
                    SemanticConceptSelection(
                        context_id="thelook_orders",
                        context_version=1,
                        metric_ids=["completed_revenue"],
                        dimension_ids=["country"],
                    )
                ],
                reason="compound group by",
            ),
        ),
        (
            "What is the average order value and completed revenue?",
            SemanticSelection(
                selected_contexts=[
                    SemanticConceptSelection(
                        context_id="thelook_orders",
                        context_version=1,
                        metric_ids=["average_order_value"],
                        dimension_ids=[],
                    )
                ],
                reason="compound metric 2",
            ),
        ),
        (
            "How many completed orders per user?",
            SemanticSelection(
                selected_contexts=[
                    SemanticConceptSelection(
                        context_id="thelook_orders",
                        context_version=1,
                        metric_ids=["completed_order_count"],
                        dimension_ids=["country"],
                    )
                ],
                reason="misselected group-by dimension",
            ),
        ),
    ]
    for q, sel in m1_negatives:
        assert try_compile_narrow_selection(q, sel, contracts_by_id) is None


def test_gold_cases_compile_tier1() -> None:
    import yaml

    contracts_by_id = {c.id: c for c in load_contracts()}
    gold_path = PROJECT_ROOT / "advanced/app/semantic_analytics/evals/gold_cases.yaml"
    with gold_path.open() as f:
        gold_data = yaml.safe_load(f)

    for case in gold_data["cases"]:
        q = case["question"]
        c_sel = case["selection"]
        filters = []
        if "United States" in q:
            filters.append(
                SemanticFilterSelection(
                    dimension_id="country",
                    op="=",
                    values=["United States"],
                )
            )
        elif "Accessories" in q:
            filters.append(
                SemanticFilterSelection(
                    dimension_id="product_category",
                    op="=",
                    values=["Accessories"],
                )
            )

        limit = 10 if "Which 10" in q else None

        sel = SemanticSelection(
            selected_contexts=[
                SemanticConceptSelection(
                    context_id=c_sel["context_id"],
                    context_version=c_sel["context_version"],
                    metric_ids=c_sel["metric_ids"],
                    dimension_ids=c_sel["dimension_ids"],
                    filters=filters,
                    limit=limit,
                )
            ],
            reason=f"Gold case {case['id']}",
        )
        res = try_compile_narrow_selection(q, sel, contracts_by_id)
        assert res is not None, f"Gold case {case['id']} ({q}) failed Tier-1 compilation"


@pytest.mark.anyio
async def test_end_to_end_tier1_bypasses_sql_generator_and_eval_generator_sees_event(
    monkeypatch,
) -> None:
    from google.adk.evaluation.evaluation_generator import EvaluationGenerator
    from semantic.catalog import CatalogField, TableMetadata
    from semantic.execution import ExecResult

    contract = load_contract()
    selection = SemanticSelection(
        selected_contexts=[
            SemanticConceptSelection(
                context_id=contract.id,
                context_version=contract.version,
                metric_ids=["completed_order_count"],
                dimension_ids=[],
            )
        ],
        reason="Matches completed order count.",
    )
    selector_model = _scripted_model(selection.model_dump_json())
    generator_model = _scripted_model("SELECT 1; -- must not be called")
    summarizer_model = _scripted_model("There were 42 completed orders.")

    class FakeAdapter:
        def fetch_table_metadata(self, sources):
            return [
                TableMetadata(
                    source=f"{s.project}.{s.dataset}.{s.table}",
                    fields=(
                        CatalogField(name="order_id", type="INT64"),
                        CatalogField(name="status", type="STRING"),
                    ),
                )
                for s in sources
            ]

        def fetch_knowledge_context(self, sources, question=""):
            return []

    monkeypatch.setattr("semantic.catalog_runtime.build_catalog_adapter", lambda: FakeAdapter())

    class FakeExecutor:
        def execute(self, sql):
            return ExecResult(
                status="SUCCESS",
                rows=({"completed_order_count": 42},),
                row_count=1,
            )

    monkeypatch.setattr("semantic.sql_runtime.build_sql_executor", lambda **kwargs: FakeExecutor())

    agent_workflow = agent.build_root_agent(
        selector_model=selector_model,
        generator_model=generator_model,
        summarizer_model=summarizer_model,
    )

    session_service = InMemorySessionService()
    await session_service.create_session(app_name="sem_test", user_id="u", session_id="s")
    runner = Runner(agent=agent_workflow, app_name="sem_test", session_service=session_service)

    outputs = []
    events = []
    async for event in runner.run_async(
        user_id="u",
        session_id="s",
        new_message=types.Content(
            role="user",
            parts=[types.Part(text="How many completed orders were placed?")],
        ),
    ):
        events.append(event)
        if event.output is not None:
            outputs.append(event.output)

    final = outputs[-1]
    assert final["status"] == "answered"
    assert final["authoring_mode"] == "tier1_compiled"
    assert final["trust_tier"] == "TIER_1_VERIFIED_OR_COMPILED"
    assert final["trust_sub_mode"] == "STRICT_CONTRACT_COMPILED"
    assert final["trust_reasons"] == []
    # Assert sql_generator was NOT called
    assert len(generator_model.requests) == 0

    # Assert EvaluationGenerator conversion logic sees route_sql_authoring in invocation_events
    invocations = EvaluationGenerator.convert_events_to_eval_invocations(events)
    assert len(invocations) == 1
    inv_events = invocations[0].intermediate_data.invocation_events
    compiled_events = [
        ie for ie in inv_events
        if ie.author and ie.author.endswith("route_sql_authoring")
    ]
    assert len(compiled_events) == 1
    assert compiled_events[0].content.parts[0].text == final["sql"]


@pytest.mark.anyio
async def test_tier1_zero_filtered_count_downgrades_to_tier3(monkeypatch) -> None:
    from semantic.catalog import CatalogField, TableMetadata
    from semantic.execution import ExecResult

    contract = load_contract()
    selection = SemanticSelection(
        selected_contexts=[
            SemanticConceptSelection(
                context_id=contract.id,
                context_version=contract.version,
                metric_ids=["completed_order_count"],
                dimension_ids=["country"],
                filters=[
                    SemanticFilterSelection(
                        dimension_id="country",
                        op="=",
                        values=["USA"],
                    )
                ],
            )
        ],
        reason="Filter on country USA",
    )
    selector_model = _scripted_model(selection.model_dump_json())
    generator_model = _scripted_model("SELECT 1; -- must not be called")
    summarizer_model = _scripted_model("There are 0 completed orders in the USA.")

    class FakeAdapter:
        def fetch_table_metadata(self, sources):
            return [
                TableMetadata(
                    source=f"{s.project}.{s.dataset}.{s.table}",
                    fields=(
                        CatalogField(name="order_id", type="INT64"),
                        CatalogField(name="status", type="STRING"),
                        CatalogField(name="country", type="STRING"),
                        CatalogField(name="id", type="INT64"),
                        CatalogField(name="user_id", type="INT64"),
                    ),
                )
                for s in sources
            ]

        def fetch_knowledge_context(self, sources, question=""):
            return []

    monkeypatch.setattr("semantic.catalog_runtime.build_catalog_adapter", lambda: FakeAdapter())

    class FakeExecutor:
        def execute(self, sql):
            return ExecResult(
                status="SUCCESS",
                rows=({"completed_order_count": 0},),
                row_count=1,
            )

    monkeypatch.setattr("semantic.sql_runtime.build_sql_executor", lambda **kwargs: FakeExecutor())

    agent_workflow = agent.build_root_agent(
        selector_model=selector_model,
        generator_model=generator_model,
        summarizer_model=summarizer_model,
    )
    session_service = InMemorySessionService()
    await session_service.create_session(app_name="sem_test", user_id="u", session_id="s")
    runner = Runner(agent=agent_workflow, app_name="sem_test", session_service=session_service)

    outputs = []
    async for event in runner.run_async(
        user_id="u",
        session_id="s",
        new_message=types.Content(
            role="user",
            parts=[types.Part(text="How many completed orders were placed in the USA?")],
        ),
    ):
        if event.output is not None:
            outputs.append(event.output)

    final = outputs[-1]
    assert final["status"] == "answered"
    assert final["authoring_mode"] == "tier1_compiled"
    assert final["trust_tier"] == "TIER_3_REVIEW_REQUIRED"
    assert final["trust_sub_mode"] == "REVIEW_REQUIRED"
    assert "zero-filtered" in final["trust_reasons"][0]


@pytest.mark.anyio
async def test_multi_turn_session_tier1_then_broad_state_isolation(monkeypatch) -> None:
    from semantic.catalog import CatalogField, TableMetadata
    from semantic.execution import ExecResult

    contract = load_contract()

    # Turn 1: Tier-1 compiled selection
    sel1 = SemanticSelection(
        selected_contexts=[
            SemanticConceptSelection(
                context_id=contract.id,
                context_version=contract.version,
                metric_ids=["completed_order_count"],
                dimension_ids=[],
            )
        ],
        reason="Matches completed order count.",
    )
    # Turn 2: Broad catalog path (requires_broad_catalog = True)
    sel2 = SemanticSelection(
        selected_contexts=[],
        requires_broad_catalog=True,
        reason="Needs broad catalog search.",
    )

    selector_model = _MultiResponseLlm(
        responses=[
            LlmResponse(
                content=types.Content(
                    role="model",
                    parts=[types.Part(text=sel1.model_dump_json())],
                )
            ),
            LlmResponse(
                content=types.Content(
                    role="model",
                    parts=[types.Part(text=sel2.model_dump_json())],
                )
            ),
        ]
    )
    # Generator model is called ONLY on Turn 2
    generator_model = _scripted_model("SELECT count(*) FROM `proj.ds.broad_table`")
    summarizer_model = _MultiResponseLlm(
        responses=[
            LlmResponse(
                content=types.Content(
                    role="model",
                    parts=[types.Part(text="There were 42 completed orders.")],
                )
            ),
            LlmResponse(
                content=types.Content(
                    role="model",
                    parts=[types.Part(text="Broad query returned 99 items.")],
                )
            ),
        ]
    )

    class FakeAdapter:
        def fetch_table_metadata(self, sources):
            return [
                TableMetadata(
                    source=f"{s.project}.{s.dataset}.{s.table}",
                    fields=(
                        CatalogField(name="order_id", type="INT64"),
                        CatalogField(name="status", type="STRING"),
                    ),
                )
                for s in sources
            ]

        def search_tables(self, question, allowed_projects, allowed_datasets):
            return [
                TableMetadata(
                    source="test-project.test_dataset.broad_table",
                    fields=(CatalogField(name="id", type="INT64"),),
                )
            ]

        def fetch_knowledge_context(self, sources, question=""):
            return []

    monkeypatch.setattr("semantic.catalog_runtime.build_catalog_adapter", lambda: FakeAdapter())
    monkeypatch.setenv("CATALOG_ALLOWED_PROJECTS", "test-project")
    monkeypatch.setenv("CATALOG_ALLOWED_DATASETS", "test-project.test_dataset")

    class FakeExecutor:
        def execute(self, sql):
            if "broad_table" in sql:
                return ExecResult(
                    status="SUCCESS",
                    rows=({"total": 99},),
                    row_count=1,
                )
            return ExecResult(
                status="SUCCESS",
                rows=({"completed_order_count": 42},),
                row_count=1,
            )

    monkeypatch.setattr("semantic.sql_runtime.build_sql_executor", lambda **kwargs: FakeExecutor())

    agent_workflow = agent.build_root_agent(
        selector_model=selector_model,
        generator_model=generator_model,
        summarizer_model=summarizer_model,
    )
    session_service = InMemorySessionService()
    await session_service.create_session(app_name="sem_test", user_id="u", session_id="multi")
    runner = Runner(agent=agent_workflow, app_name="sem_test", session_service=session_service)

    # Turn 1: Tier-1
    turn1_outputs = []
    async for event in runner.run_async(
        user_id="u",
        session_id="multi",
        new_message=types.Content(
            role="user",
            parts=[types.Part(text="How many completed orders were placed?")],
        ),
    ):
        if event.output is not None:
            turn1_outputs.append(event.output)

    final1 = turn1_outputs[-1]
    assert final1["status"] == "answered"
    assert final1["authoring_mode"] == "tier1_compiled"
    assert final1["trust_tier"] == "TIER_1_VERIFIED_OR_COMPILED"
    assert len(generator_model.requests) == 0

    # Turn 2: Broad
    turn2_outputs = []
    async for event in runner.run_async(
        user_id="u",
        session_id="multi",
        new_message=types.Content(
            role="user",
            parts=[types.Part(text="Find uncataloged inventory")],
        ),
    ):
        if event.output is not None:
            turn2_outputs.append(event.output)

    final2 = turn2_outputs[-1]
    assert final2["status"] == "answered"
    assert final2["authoring_mode"] == "tier2_guarded_llm"
    assert final2["trust_tier"] == "TIER_2_GROUNDED"
    assert final2["trust_sub_mode"] == "DYNAMIC_SQL_GROUNDED"
    assert final2["trust_reasons"] == []
    # Assert generator was called exactly once in Turn 2
    assert len(generator_model.requests) == 1
    assert "compiled_metric_id" not in final2

