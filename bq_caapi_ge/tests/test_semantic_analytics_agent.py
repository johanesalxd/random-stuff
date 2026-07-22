"""Tests for the domain-neutral semantic analytics workflow."""

from __future__ import annotations

import asyncio
from dataclasses import replace
import json
from pathlib import Path
import sys

import pytest
from pydantic import Field

pytest.importorskip("google.adk")

from google.adk.runners import Runner  # noqa: E402
from google.adk.models import BaseLlm, LlmRequest, LlmResponse  # noqa: E402
from google.adk.sessions import InMemorySessionService  # noqa: E402
from google.adk.workflow import Workflow  # noqa: E402
from google.genai import types  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from advanced.app.semantic_analytics import agent  # noqa: E402
from semantic.registry import load_contract, load_contracts  # noqa: E402
from semantic.runtime import (  # noqa: E402
    SemanticConceptSelection,
    SemanticSelection,
    finish_catalog_broad_resolution,
    finish_semantic_narrow_resolution,
    load_semantic_registry,
    recover_invalid_semantic_selection,
    resolve_selection,
    resolve_semantic_selection,
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
                    "semantic_narrow": finish_semantic_narrow_resolution,
                    "catalog_broad": finish_catalog_broad_resolution,
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
