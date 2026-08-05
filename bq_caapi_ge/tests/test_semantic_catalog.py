"""Tests for V2 Knowledge Catalog and BigQuery schema grounding."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

import pytest

pytest.importorskip("google.adk")

from google.adk.runners import Runner  # noqa: E402
from google.adk.sessions import InMemorySessionService  # noqa: E402
from google.adk.workflow import Workflow  # noqa: E402
from google.api_core import exceptions as gcp_exceptions  # noqa: E402
from google.genai import types  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from semantic import catalog_runtime  # noqa: E402
from semantic.catalog import (  # noqa: E402
    BigQueryCatalogAdapter,
    CatalogAccessError,
    KnowledgeCatalogAdapter,
    build_catalog_adapter,
    build_table_metadata,
    bound_table_results,
    is_source_in_scope,
    parse_allowed_datasets,
    parse_allowed_projects,
    parse_catalog_source,
    resolve_narrow_sources,
    sanitize_knowledge_context,
)
from semantic.catalog_runtime import (  # noqa: E402
    assess_broad,
    assess_broad_context,
    assess_context,
    assess_narrow,
    finish_catalog_grounding,
    finish_clarification,
    ground_broad,
    ground_narrow,
    load_broad_catalog_context,
    load_narrow_catalog_context,
)
from semantic.runtime import (  # noqa: E402
    load_semantic_registry,
    resolve_semantic_selection,
)

_FIXED_NOW = datetime(2026, 7, 22, 12, 0, 0, tzinfo=timezone.utc)
_READINGS = "example-project.climate.readings"
_ENTRY_NAME = (
    "projects/example-project/locations/us/entryGroups/@bigquery/entries/"
    "bigquery.googleapis.com/projects/example-project/datasets/climate/tables/readings"
)


class _FakeCatalogAdapter:
    def __init__(self, *, narrow=None, broad=(), context=()):
        self._narrow = dict(narrow or {})
        self._broad = tuple(broad)
        self._context = tuple(context)
        self.narrow_calls: list[tuple[str, ...]] = []
        self.broad_calls: list[str] = []
        self.context_calls: list[tuple[str, ...]] = []

    def fetch_table_metadata(self, sources):
        self.narrow_calls.append(tuple(source.qualified_name for source in sources))
        return tuple(
            self._narrow[source.qualified_name]
            for source in sources
            if source.qualified_name in self._narrow
        )

    def search_tables(self, *, question, allowed_projects, allowed_datasets):
        self.broad_calls.append(question)
        return self._broad

    def fetch_knowledge_context(self, sources, *, question):
        self.context_calls.append(tuple(source.qualified_name for source in sources))
        return self._context


def _readings_metadata(source: str = _READINGS):
    return build_table_metadata(
        source=source,
        fields=[
            {"name": "reading_id", "type": "STRING", "mode": "REQUIRED"},
            {"name": "station_id", "type": "STRING"},
        ],
        description="Weather station readings.",
        now=_FIXED_NOW,
    )


def test_parse_catalog_source_accepts_three_parts():
    source = parse_catalog_source("proj-1.dataset_a.table$1")
    assert source.qualified_name == "proj-1.dataset_a.table$1"
    assert source.dataset_id == "proj-1.dataset_a"


@pytest.mark.parametrize(
    "value",
    ["only.two", "a.b.c.d", "proj.dataset.", "proj..table", "bad proj.d.t", ""],
)
def test_parse_catalog_source_rejects_malformed(value):
    with pytest.raises(CatalogAccessError):
        parse_catalog_source(value)


def test_resolve_narrow_sources_dedupes_and_sorts():
    sources = resolve_narrow_sources([_READINGS, _READINGS, "p-project.d.a"])
    assert [source.qualified_name for source in sources] == [
        _READINGS,
        "p-project.d.a",
    ]


def test_allowlists_default_deny_and_drop_invalid(monkeypatch):
    monkeypatch.delenv("CATALOG_ALLOWED_PROJECTS", raising=False)
    monkeypatch.delenv("CATALOG_ALLOWED_DATASETS", raising=False)
    assert parse_allowed_projects() == frozenset()
    assert parse_allowed_datasets() == frozenset()
    assert parse_allowed_projects("good-project, bad proj") == frozenset(
        {"good-project"}
    )
    assert parse_allowed_datasets("good-project.sales, missing, a.b.c") == (
        frozenset({"good-project.sales"})
    )


def test_is_source_in_scope_requires_explicit_allow():
    source = parse_catalog_source(_READINGS)
    assert not is_source_in_scope(
        source, allowed_projects=frozenset(), allowed_datasets=frozenset()
    )
    assert is_source_in_scope(
        source,
        allowed_projects=frozenset({"example-project"}),
        allowed_datasets=frozenset(),
    )
    assert is_source_in_scope(
        source,
        allowed_projects=frozenset(),
        allowed_datasets=frozenset({"example-project.climate"}),
    )


def test_build_table_metadata_bounds_fields_and_text():
    fields = [{"name": f"c{index}", "type": "STRING"} for index in range(500)]
    metadata = build_table_metadata(
        source=_READINGS,
        fields=fields,
        description="x" * 2_000,
        now=_FIXED_NOW,
    )
    assert len(metadata.fields) == 300
    assert len(metadata.description) == 1_000
    assert metadata.retrieved_at == "2026-07-22T12:00:00+00:00"


def test_bound_table_results_caps_tables():
    many = [_readings_metadata(f"p-project.d.t{index}") for index in range(40)]
    assert len(bound_table_results(many)) == 25


def test_sanitize_knowledge_context_keeps_metadata_and_removes_values():
    raw = json.dumps(
        {
            "resources": [
                {
                    "name": _READINGS,
                    "description": "Weather readings",
                    "schema": {
                        "fields": [
                            {
                                "name": "station_id",
                                "type": "STRING",
                                "description": "Station identifier",
                                "sample_values": ["secret-station"],
                                "min": "aaa",
                                "max": "zzz",
                            }
                        ]
                    },
                    "relationships": [
                        {"name": "station_join", "join_condition": "a.id = b.id"}
                    ],
                    "data_profile": {"top_values": ["secret"]},
                }
            ]
        }
    )

    context = sanitize_knowledge_context(raw)

    assert context is not None
    serialized = json.dumps(context)
    assert "Weather readings" in serialized
    assert "station_join" in serialized
    for excluded in ("secret-station", "aaa", "zzz", "secret", "data_profile"):
        assert excluded not in serialized


def test_sanitize_knowledge_context_fails_closed():
    assert sanitize_knowledge_context("not-json") is None
    assert sanitize_knowledge_context('{"sample_values":["secret"]}') is None


def test_ground_narrow_returns_schema_and_knowledge_context():
    knowledge = ({"resources": [{"name": _READINGS}]},)
    adapter = _FakeCatalogAdapter(
        narrow={_READINGS: _readings_metadata()},
        context=knowledge,
    )

    payload = ground_narrow(
        {"question": "q", "semantic_source_names": [_READINGS]},
        adapter,
    )

    assert adapter.narrow_calls == [(_READINGS,)]
    assert adapter.context_calls == [(_READINGS,)]
    assert payload["catalog_route"] == "narrow"
    assert payload["catalog_missing_sources"] == []
    assert payload["knowledge_catalog_context"] == list(knowledge)


def test_ground_narrow_marks_missing_and_routes_broad():
    adapter = _FakeCatalogAdapter(narrow={})
    grounding = ground_narrow(
        {"question": "q", "semantic_source_names": [_READINGS]},
        adapter,
    )

    payload, route = assess_narrow(grounding)

    assert route == "insufficient"
    assert payload["catalog_missing_sources"] == [_READINGS]


def test_ground_broad_fails_closed_without_allowlists():
    adapter = _FakeCatalogAdapter(broad=(_readings_metadata(),))
    payload = ground_broad(
        {"question": "q"},
        adapter,
        allowed_projects=frozenset(),
        allowed_datasets=frozenset(),
    )
    assert payload["catalog_context"] == []
    assert adapter.broad_calls == []


def test_ground_broad_clamps_results_and_retrieves_context():
    knowledge = ({"resources": [{"name": _READINGS}]},)
    adapter = _FakeCatalogAdapter(
        broad=(
            _readings_metadata(),
            _readings_metadata("other-project.secret.table"),
        ),
        context=knowledge,
    )
    payload = ground_broad(
        {"question": "q"},
        adapter,
        allowed_projects=frozenset({"example-project"}),
        allowed_datasets=frozenset(),
    )
    assert payload["catalog_discovered_sources"] == [_READINGS]
    assert payload["knowledge_catalog_context"] == list(knowledge)
    assert adapter.context_calls == [(_READINGS,)]


def test_assess_broad_routes_grounded_and_clarify():
    grounded, route = assess_broad(
        {
            "catalog_context": [{"source": _READINGS}],
            "catalog_discovered_sources": [_READINGS],
        }
    )
    assert route == "grounded"
    assert grounded["context_sufficiency"]["sufficient"] is True
    _, empty_route = assess_broad(
        {"catalog_context": [], "catalog_discovered_sources": []}
    )
    assert empty_route == "clarify"


class _FakeSchemaField:
    def __init__(self, name, field_type, mode="NULLABLE", description=""):
        self.name = name
        self.field_type = field_type
        self.mode = mode
        self.description = description


class _FakeTable:
    def __init__(self, schema, description=""):
        self.schema = schema
        self.description = description


class _FakeBigQueryClient:
    def __init__(self, tables=None):
        self._tables = dict(tables or {})

    def get_table(self, qualified_name):
        if qualified_name not in self._tables:
            raise gcp_exceptions.NotFound(qualified_name)
        return self._tables[qualified_name]


def _schema_adapter(client):
    return BigQueryCatalogAdapter(
        project="compute-project",
        client=client,
        now=_FIXED_NOW,
    )


def test_bigquery_adapter_fetch_maps_current_schema():
    client = _FakeBigQueryClient(
        {
            _READINGS: _FakeTable(
                schema=[
                    _FakeSchemaField("reading_id", "STRING", "REQUIRED", "PK"),
                    _FakeSchemaField("station_id", "STRING"),
                ],
                description="Weather readings.",
            )
        }
    )
    metadata = _schema_adapter(client).fetch_table_metadata(
        (parse_catalog_source(_READINGS),)
    )
    assert [field_.name for field_ in metadata[0].fields] == [
        "reading_id",
        "station_id",
    ]
    assert metadata[0].description == "Weather readings."


class _FakeDataplexEntry:
    def __init__(self, *, name, fully_qualified_name):
        self.name = name
        self.fully_qualified_name = fully_qualified_name


class _FakeSearchResult:
    def __init__(self, *, source=_READINGS, entry_name=_ENTRY_NAME):
        self.dataplex_entry = _FakeDataplexEntry(
            name=entry_name,
            fully_qualified_name=f"bigquery:{source}",
        )
        self.linked_resource = ""


class _FakeLookupResponse:
    def __init__(self, context):
        self.context = context


class _FakeKnowledgeClient:
    def __init__(self, *, results=(), context="{}"):
        self._results = list(results)
        self._context = context
        self.search_requests = []
        self.lookup_requests = []

    def search_entries(self, request=None, **_kwargs):
        self.search_requests.append(request)
        return list(self._results)

    def lookup_context(self, request=None, **_kwargs):
        self.lookup_requests.append(request)
        return _FakeLookupResponse(self._context)


def _knowledge_adapter(bq_client, knowledge_client):
    return KnowledgeCatalogAdapter(
        project="compute-project",
        schema_adapter=_schema_adapter(bq_client),
        client=knowledge_client,
    )


def test_knowledge_catalog_broad_search_is_semantic_and_allowlisted():
    bq_client = _FakeBigQueryClient(
        {_READINGS: _FakeTable([_FakeSchemaField("station_id", "STRING")])}
    )
    knowledge_client = _FakeKnowledgeClient(results=[_FakeSearchResult()])
    adapter = _knowledge_adapter(bq_client, knowledge_client)

    results = adapter.search_tables(
        question="weather observations by station",
        allowed_projects=frozenset(),
        allowed_datasets=frozenset({"example-project.climate"}),
    )

    assert [item.source for item in results] == [_READINGS]
    request = knowledge_client.search_requests[0]
    assert request.semantic_search is True
    assert request.scope == "projects/example-project"


def test_knowledge_catalog_lookup_uses_entry_location_and_sanitizes():
    bq_client = _FakeBigQueryClient(
        {_READINGS: _FakeTable([_FakeSchemaField("station_id", "STRING")])}
    )
    raw_context = json.dumps(
        {
            "resources": [
                {
                    "name": _READINGS,
                    "description": "Weather",
                    "sample_values": ["secret"],
                }
            ]
        }
    )
    knowledge_client = _FakeKnowledgeClient(
        results=[_FakeSearchResult()],
        context=raw_context,
    )
    adapter = _knowledge_adapter(bq_client, knowledge_client)

    context = adapter.fetch_knowledge_context(
        (parse_catalog_source(_READINGS),),
        question="weather",
    )

    request = knowledge_client.lookup_requests[0]
    assert request.name == "projects/compute-project/locations/us"
    assert request.options["format"] == "json"
    assert request.options["context_budget"] == "10000"
    assert "Weather" in json.dumps(context)
    assert "secret" not in json.dumps(context)


def test_build_catalog_adapter_requires_project_and_returns_knowledge(monkeypatch):
    monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)
    with pytest.raises(CatalogAccessError):
        build_catalog_adapter()
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "compute-project")
    assert isinstance(build_catalog_adapter(), KnowledgeCatalogAdapter)


def test_finish_terminals_set_next_step():
    grounded = finish_catalog_grounding({"question": "q"})
    assert grounded["status"] == "catalog_context_grounded"
    clarified = finish_clarification({"question": "q"})
    assert clarified["status"] == "catalog_context_insufficient"


def _weather_selection(node_input):
    assert node_input["semantic_candidates"][0]["id"] == "weather_observations"
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


async def _run(selector, question):
    workflow = Workflow(
        name="catalog_grounding_test",
        edges=[
            ("START", load_semantic_registry, selector),
            (selector, resolve_semantic_selection),
            (
                resolve_semantic_selection,
                {
                    "semantic_narrow": load_narrow_catalog_context,
                    "catalog_broad": load_broad_catalog_context,
                },
            ),
            (load_narrow_catalog_context, assess_context),
            (
                assess_context,
                {
                    "sufficient": finish_catalog_grounding,
                    "insufficient": load_broad_catalog_context,
                },
            ),
            (load_broad_catalog_context, assess_broad_context),
            (
                assess_broad_context,
                {
                    "grounded": finish_catalog_grounding,
                    "clarify": finish_clarification,
                },
            ),
        ],
    )
    service = InMemorySessionService()
    await service.create_session(app_name="catalog_test", user_id="u", session_id="s")
    runner = Runner(agent=workflow, app_name="catalog_test", session_service=service)
    outputs = []
    async for event in runner.run_async(
        user_id="u",
        session_id="s",
        new_message=types.Content(role="user", parts=[types.Part(text=question)]),
    ):
        if event.output is not None:
            outputs.append(event.output)
    return outputs


def test_workflow_narrow_sufficient_reaches_sql_handoff(monkeypatch, tmp_path):
    _write_weather_contract(tmp_path, monkeypatch)
    adapter = _FakeCatalogAdapter(narrow={_READINGS: _readings_metadata()})
    monkeypatch.setattr(catalog_runtime, "build_catalog_adapter", lambda: adapter)

    final = asyncio.run(_run(_weather_selection, "Count by station"))[-1]

    assert final["catalog_route"] == "narrow"
    assert [item["source"] for item in final["catalog_context"]] == [_READINGS]


def _write_weather_contract(tmp_path: Path, monkeypatch) -> None:
    contract_path = tmp_path / "weather.yaml"
    contract_path.write_text(
        """id: weather_observations
version: 3
owner: climate-team
description: Weather station observations.
routing_terms: [weather, stations]
examples: [Count observations by station]
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
    description: Reporting station.
    table: readings
    sql: readings.station_id
    synonyms: [station]
metrics:
  observation_total:
    label: Reading Count
    description: Number of observations.
    type: count_distinct
    base_table: readings
    sql: readings.reading_id
    allowed_dimensions: [sensor_location]
    join_path: []
    allowed_filters: {}
""",
        encoding="utf-8",
    )
    monkeypatch.setenv("SEMANTIC_CONTRACT_PATH", str(contract_path))
