"""Tests for Phase 7 Knowledge Catalog grounding."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path
import sys

import pytest

pytest.importorskip("google.adk")

from google.adk.runners import Runner  # noqa: E402
from google.adk.sessions import InMemorySessionService  # noqa: E402
from google.adk.workflow import Workflow  # noqa: E402
from google.genai import types  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from semantic import catalog_runtime  # noqa: E402
from google.api_core import exceptions as gcp_exceptions  # noqa: E402

from semantic.catalog import (  # noqa: E402
    BigQueryCatalogAdapter,
    CatalogAccessError,
    DataplexCatalogAdapter,
    build_catalog_adapter,
    build_table_metadata,
    bound_table_results,
    is_source_in_scope,
    parse_allowed_datasets,
    parse_allowed_projects,
    parse_catalog_source,
    resolve_narrow_sources,
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


class _FakeCatalogAdapter:
    """Deterministic in-memory catalog adapter for tests."""

    def __init__(self, *, narrow=None, broad=()):
        self._narrow = dict(narrow or {})
        self._broad = tuple(broad)
        self.narrow_calls: list[tuple[str, ...]] = []
        self.broad_calls: list[str] = []

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


def _readings_metadata(source: str = _READINGS) -> object:
    return build_table_metadata(
        source=source,
        fields=[
            {"name": "reading_id", "type": "STRING", "mode": "REQUIRED"},
            {"name": "station_id", "type": "STRING"},
        ],
        description="Weather station readings.",
        had_profile=True,
        now=_FIXED_NOW,
    )


# --- source and allowlist parsing ------------------------------------------


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


def test_resolve_narrow_sources_requires_sources():
    with pytest.raises(CatalogAccessError):
        resolve_narrow_sources([])


def test_allowlists_default_deny_when_unset(monkeypatch):
    monkeypatch.delenv("CATALOG_ALLOWED_PROJECTS", raising=False)
    monkeypatch.delenv("CATALOG_ALLOWED_DATASETS", raising=False)
    assert parse_allowed_projects() == frozenset()
    assert parse_allowed_datasets() == frozenset()


def test_allowlists_drop_invalid_entries():
    assert parse_allowed_projects("good-project, bad proj, ") == frozenset(
        {"good-project"}
    )
    assert parse_allowed_datasets("good-project.sales, missingdataset, a.b.c") == (
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


# --- metadata bounding and redaction ---------------------------------------


def test_build_table_metadata_redacts_profile_and_timestamps():
    metadata = _readings_metadata()
    context = metadata.to_context()
    assert context["retrieved_at"] == "2026-07-22T12:00:00+00:00"
    assert context["redacted_profile"] is True
    assert [field_["name"] for field_ in context["fields"]] == [
        "reading_id",
        "station_id",
    ]
    # No sample values or profile payloads are ever surfaced.
    assert "sample_values" not in context
    assert all("value" not in field_ for field_ in context["fields"])


def test_build_table_metadata_bounds_field_count():
    fields = [{"name": f"c{index}", "type": "STRING"} for index in range(500)]
    metadata = build_table_metadata(source=_READINGS, fields=fields, now=_FIXED_NOW)
    assert len(metadata.fields) == 300


def test_bound_table_results_caps_tables():
    many = [_readings_metadata(f"p-project.d.t{index}") for index in range(40)]
    assert len(bound_table_results(many)) == 25


# --- narrow grounding ------------------------------------------------------


def test_ground_narrow_returns_context_for_requested_sources():
    adapter = _FakeCatalogAdapter(narrow={_READINGS: _readings_metadata()})
    handoff = {"question": "q", "semantic_source_names": [_READINGS]}

    payload = ground_narrow(handoff, adapter, now=_FIXED_NOW)

    assert adapter.narrow_calls == [(_READINGS,)]
    assert payload["catalog_route"] == "narrow"
    assert payload["catalog_missing_sources"] == []
    assert [item["source"] for item in payload["catalog_context"]] == [_READINGS]


def test_ground_narrow_marks_unresolved_sources_missing():
    adapter = _FakeCatalogAdapter(narrow={})
    handoff = {"question": "q", "semantic_source_names": [_READINGS]}

    payload = ground_narrow(handoff, adapter, now=_FIXED_NOW)

    assert payload["catalog_context"] == []
    assert payload["catalog_missing_sources"] == [_READINGS]


def test_ground_narrow_never_surfaces_out_of_scope_metadata():
    stray = _readings_metadata("other-project.secret.table")
    adapter = _FakeCatalogAdapter(
        narrow={_READINGS: _readings_metadata(), "other-project.secret.table": stray}
    )
    handoff = {"question": "q", "semantic_source_names": [_READINGS]}

    payload = ground_narrow(handoff, adapter, now=_FIXED_NOW)

    sources = [item["source"] for item in payload["catalog_context"]]
    assert sources == [_READINGS]


def test_ground_narrow_handles_access_error_as_missing():
    adapter = _FakeCatalogAdapter(narrow={})
    payload = ground_narrow({"question": "q", "semantic_source_names": []}, adapter)
    assert payload["catalog_context"] == []
    assert "catalog_error" in payload


def test_assess_narrow_routes_sufficient_context():
    adapter = _FakeCatalogAdapter(narrow={_READINGS: _readings_metadata()})
    grounding = ground_narrow(
        {"question": "q", "semantic_source_names": [_READINGS]},
        adapter,
        now=_FIXED_NOW,
    )

    payload, route = assess_narrow(grounding)

    assert route == "sufficient"
    assert payload["context_sufficiency"]["sufficient"] is True
    assert payload["context_sufficiency"]["missing_metadata"] == []


def test_assess_narrow_routes_missing_context_broad():
    adapter = _FakeCatalogAdapter(narrow={})
    grounding = ground_narrow(
        {"question": "q", "semantic_source_names": [_READINGS]},
        adapter,
        now=_FIXED_NOW,
    )

    _, route = assess_narrow(grounding)

    assert route == "insufficient"


# --- broad grounding -------------------------------------------------------


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
    assert "failing closed" in payload["catalog_error"]


def test_ground_broad_filters_results_to_allowlist():
    in_scope = _readings_metadata()
    out_of_scope = _readings_metadata("other-project.secret.table")
    adapter = _FakeCatalogAdapter(broad=(in_scope, out_of_scope))

    payload = ground_broad(
        {"question": "q"},
        adapter,
        allowed_projects=frozenset({"example-project"}),
        allowed_datasets=frozenset(),
    )

    assert payload["catalog_discovered_sources"] == [_READINGS]


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


# --- factory and terminals -------------------------------------------------


def test_build_catalog_adapter_requires_compute_project(monkeypatch):
    monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)
    with pytest.raises(CatalogAccessError):
        build_catalog_adapter()


def test_build_catalog_adapter_returns_bigquery_adapter(monkeypatch):
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "compute-project")
    monkeypatch.delenv("CATALOG_DATAPLEX_ENABLED", raising=False)
    adapter = build_catalog_adapter()
    assert isinstance(adapter, BigQueryCatalogAdapter)


def test_build_catalog_adapter_wraps_dataplex_when_enabled(monkeypatch):
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "compute-project")
    monkeypatch.setenv("CATALOG_DATAPLEX_ENABLED", "true")
    adapter = build_catalog_adapter()
    assert isinstance(adapter, DataplexCatalogAdapter)


# --- BigQueryCatalogAdapter (fake client, no live calls) -------------------


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


class _FakeTableItem:
    def __init__(self, project, dataset_id, table_id):
        self.project = project
        self.dataset_id = dataset_id
        self.table_id = table_id


class _FakeDatasetItem:
    def __init__(self, project, dataset_id):
        self.project = project
        self.dataset_id = dataset_id


class _FakeBigQueryClient:
    def __init__(self, *, tables=None, dataset_tables=None, project_datasets=None):
        self._tables = dict(tables or {})
        self._dataset_tables = dict(dataset_tables or {})
        self._project_datasets = dict(project_datasets or {})

    def get_table(self, qualified_name):
        if qualified_name not in self._tables:
            raise gcp_exceptions.NotFound(qualified_name)
        return self._tables[qualified_name]

    def list_tables(self, dataset_id):
        return list(self._dataset_tables.get(dataset_id, []))

    def list_datasets(self, project):
        return list(self._project_datasets.get(project, []))


def _adapter_with(client):
    return BigQueryCatalogAdapter(
        project="compute-project", client=client, now=_FIXED_NOW
    )


def test_bigquery_adapter_fetch_maps_schema():
    client = _FakeBigQueryClient(
        tables={
            _READINGS: _FakeTable(
                schema=[
                    _FakeSchemaField("reading_id", "STRING", "REQUIRED", "PK"),
                    _FakeSchemaField("station_id", "STRING"),
                ],
                description="Weather readings.",
            )
        }
    )
    adapter = _adapter_with(client)

    metadata = adapter.fetch_table_metadata((parse_catalog_source(_READINGS),))

    assert len(metadata) == 1
    context = metadata[0].to_context()
    assert context["source"] == _READINGS
    assert context["description"] == "Weather readings."
    assert [field_["name"] for field_ in context["fields"]] == [
        "reading_id",
        "station_id",
    ]
    assert context["fields"][0]["mode"] == "REQUIRED"


def test_bigquery_adapter_fetch_omits_missing_tables():
    client = _FakeBigQueryClient(tables={})
    adapter = _adapter_with(client)

    metadata = adapter.fetch_table_metadata((parse_catalog_source(_READINGS),))

    assert metadata == ()


def test_bigquery_adapter_search_stays_in_allowlist_and_ranks_by_name():
    readings = _FakeTable(schema=[_FakeSchemaField("station_id", "STRING")])
    other = _FakeTable(schema=[_FakeSchemaField("id", "STRING")])
    client = _FakeBigQueryClient(
        tables={
            _READINGS: readings,
            "example-project.climate.stations": other,
        },
        dataset_tables={
            "example-project.climate": [
                _FakeTableItem("example-project", "climate", "readings"),
                _FakeTableItem("example-project", "climate", "stations"),
            ],
            # Out-of-scope dataset must never be listed because it is not resolved.
            "other-project.secret": [
                _FakeTableItem("other-project", "secret", "readings")
            ],
        },
    )
    adapter = _adapter_with(client)

    results = adapter.search_tables(
        question="show me readings by station",
        allowed_projects=frozenset(),
        allowed_datasets=frozenset({"example-project.climate"}),
    )

    sources = [item.source for item in results]
    assert _READINGS in sources
    assert all(source.startswith("example-project.climate.") for source in sources)
    assert "other-project.secret.readings" not in sources


def test_bigquery_adapter_search_empty_without_allowlist():
    client = _FakeBigQueryClient()
    adapter = _adapter_with(client)

    results = adapter.search_tables(
        question="anything",
        allowed_projects=frozenset(),
        allowed_datasets=frozenset(),
    )

    assert results == ()


def test_bigquery_adapter_search_expands_allowed_projects():
    client = _FakeBigQueryClient(
        tables={
            _READINGS: _FakeTable(schema=[_FakeSchemaField("station_id", "STRING")])
        },
        project_datasets={
            "example-project": [_FakeDatasetItem("example-project", "climate")]
        },
        dataset_tables={
            "example-project.climate": [
                _FakeTableItem("example-project", "climate", "readings")
            ]
        },
    )
    adapter = _adapter_with(client)

    results = adapter.search_tables(
        question="readings",
        allowed_projects=frozenset({"example-project"}),
        allowed_datasets=frozenset(),
    )

    assert [item.source for item in results] == [_READINGS]


# --- DataplexCatalogAdapter (fake clients, no live calls) ------------------


class _FakeAspect:
    def __init__(self, aspect_type, data=None):
        self.aspect_type = aspect_type
        self.data = data


class _FakeEntry:
    def __init__(self, aspects=None):
        self.aspects = dict(aspects or {})


class _FakeDataplexEntry:
    def __init__(self, fully_qualified_name):
        self.fully_qualified_name = fully_qualified_name


class _FakeSearchResult:
    def __init__(self, fqn="", linked_resource=""):
        self.dataplex_entry = _FakeDataplexEntry(fqn) if fqn else None
        self.linked_resource = linked_resource


class _FakeDataplexClient:
    def __init__(self, *, search_results=(), entry=None, search_error=None):
        self._search_results = list(search_results)
        self._entry = entry
        self._search_error = search_error
        self.search_calls = []

    def search_entries(self, request=None, **_kwargs):
        self.search_calls.append(request)
        if self._search_error is not None:
            raise self._search_error
        return list(self._search_results)

    def lookup_entry(self, request=None, **_kwargs):
        if self._entry is None:
            raise gcp_exceptions.NotFound("entry")
        return self._entry


def _dataplex_over_bq(bq_client, dpx_client):
    inner = BigQueryCatalogAdapter(
        project="compute-project", client=bq_client, now=_FIXED_NOW
    )
    return DataplexCatalogAdapter(
        project="compute-project", inner=inner, client=dpx_client, now=_FIXED_NOW
    )


def test_dataplex_search_clamps_to_allowlist_and_loads_schema():
    bq_client = _FakeBigQueryClient(
        tables={
            _READINGS: _FakeTable(schema=[_FakeSchemaField("station_id", "STRING")])
        }
    )
    dpx_client = _FakeDataplexClient(
        search_results=[
            _FakeSearchResult(fqn=f"bigquery:{_READINGS}"),
            _FakeSearchResult(fqn="bigquery:other-project.secret.table"),
        ]
    )
    adapter = _dataplex_over_bq(bq_client, dpx_client)

    results = adapter.search_tables(
        question="show me readings by station",
        allowed_projects=frozenset(),
        allowed_datasets=frozenset({"example-project.climate"}),
    )

    assert [item.source for item in results] == [_READINGS]
    assert adapter.last_search_backend == "dataplex"
    assert dpx_client.search_calls  # Dataplex was actually consulted


def test_dataplex_search_out_of_scope_falls_back_to_name_match():
    bq_client = _FakeBigQueryClient(
        tables={
            _READINGS: _FakeTable(schema=[_FakeSchemaField("station_id", "STRING")])
        },
        dataset_tables={
            "example-project.climate": [
                _FakeTableItem("example-project", "climate", "readings")
            ]
        },
    )
    dpx_client = _FakeDataplexClient(
        search_results=[_FakeSearchResult(fqn="bigquery:other-project.secret.table")]
    )
    adapter = _dataplex_over_bq(bq_client, dpx_client)

    results = adapter.search_tables(
        question="readings",
        allowed_projects=frozenset(),
        allowed_datasets=frozenset({"example-project.climate"}),
    )

    assert [item.source for item in results] == [_READINGS]
    assert adapter.last_search_backend == "name_match_fallback"


def test_dataplex_search_error_falls_back_to_name_match():
    bq_client = _FakeBigQueryClient(
        tables={
            _READINGS: _FakeTable(schema=[_FakeSchemaField("station_id", "STRING")])
        },
        dataset_tables={
            "example-project.climate": [
                _FakeTableItem("example-project", "climate", "readings")
            ]
        },
    )
    dpx_client = _FakeDataplexClient(
        search_error=gcp_exceptions.ServiceUnavailable("dataplex down")
    )
    adapter = _dataplex_over_bq(bq_client, dpx_client)

    results = adapter.search_tables(
        question="readings",
        allowed_projects=frozenset(),
        allowed_datasets=frozenset({"example-project.climate"}),
    )

    assert [item.source for item in results] == [_READINGS]
    assert adapter.last_search_backend == "name_match_fallback"


def test_dataplex_enrich_surfaces_structural_signals_only():
    bq_client = _FakeBigQueryClient(
        tables={
            _READINGS: _FakeTable(
                schema=[
                    _FakeSchemaField("reading_id", "STRING", "REQUIRED"),
                    _FakeSchemaField("station_id", "STRING"),
                ]
            )
        }
    )
    profile_aspect = _FakeAspect(
        "projects/dataplex-types/global/aspectTypes/data-profile-scan",
        data={
            "fields": [
                {
                    "name": "reading_id",
                    "profile": {
                        "nullRatio": 0.0,
                        "distinctRatio": 1.0,
                        # Value-bearing keys that must never be surfaced:
                        "min": "aaa",
                        "max": "zzz",
                        "average": 42,
                        "topNValues": [{"value": "secret", "count": 9}],
                        "quartiles": [1, 2, 3],
                    },
                },
                {
                    "name": "station_id",
                    "profile": {"nullRatio": 0.2, "distinctRatio": 0.5},
                },
            ]
        },
    )
    insight_aspect = _FakeAspect(
        "projects/dataplex-types/global/aspectTypes/data-insight",
        data={"summary": "generated prose that could echo values"},
    )
    entry = _FakeEntry(aspects={"profile": profile_aspect, "insight": insight_aspect})
    dpx_client = _FakeDataplexClient(entry=entry)
    adapter = _dataplex_over_bq(bq_client, dpx_client)

    metadata = adapter.fetch_table_metadata((parse_catalog_source(_READINGS),))

    context = metadata[0].to_context()
    assert context["redacted_profile"] is True
    assert context["has_insight"] is True
    by_name = {field_["name"]: field_ for field_ in context["fields"]}
    assert by_name["reading_id"]["null_ratio"] == 0.0
    assert by_name["reading_id"]["distinct_ratio"] == 1.0
    assert by_name["reading_id"]["is_candidate_key"] is True
    assert by_name["station_id"]["null_ratio"] == 0.2
    assert by_name["station_id"]["distinct_ratio"] == 0.5
    assert "is_candidate_key" not in by_name["station_id"]
    # Redaction: no data values leak anywhere in the serialized context.
    serialized = repr(context)
    for leaked in ("aaa", "zzz", "secret", "topNValues", "average", "quartiles"):
        assert leaked not in serialized


def test_dataplex_enrich_noop_without_aspects():
    bq_client = _FakeBigQueryClient(
        tables={
            _READINGS: _FakeTable(schema=[_FakeSchemaField("station_id", "STRING")])
        }
    )
    dpx_client = _FakeDataplexClient(entry=_FakeEntry(aspects={}))
    adapter = _dataplex_over_bq(bq_client, dpx_client)

    metadata = adapter.fetch_table_metadata((parse_catalog_source(_READINGS),))

    context = metadata[0].to_context()
    assert context["redacted_profile"] is False
    assert context["has_insight"] is False
    assert "null_ratio" not in context["fields"][0]


def test_finish_terminals_set_next_step():
    grounded = finish_catalog_grounding({"question": "q"})
    assert grounded["status"] == "catalog_context_grounded"
    assert grounded["next_step"] == "guarded_sql_generation"

    clarified = finish_clarification({"question": "q"})
    assert clarified["status"] == "catalog_context_insufficient"
    assert clarified["next_step"] == "clarify_or_refuse"


# --- workflow integration --------------------------------------------------


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


def _broad_selection(node_input):
    assert node_input["semantic_candidates"]
    return {
        "selected_contexts": [],
        "requires_broad_catalog": True,
        "reason": "No configured context applies.",
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
    session_service = InMemorySessionService()
    await session_service.create_session(
        app_name="catalog_test", user_id="user", session_id="session"
    )
    runner = Runner(
        agent=workflow,
        app_name="catalog_test",
        session_service=session_service,
    )
    outputs = []
    async for event in runner.run_async(
        user_id="user",
        session_id="session",
        new_message=types.Content(role="user", parts=[types.Part(text=question)]),
    ):
        if event.output is not None:
            outputs.append(event.output)
    return outputs


def test_workflow_narrow_sufficient_reaches_sql_handoff(monkeypatch, tmp_path):
    _write_weather_contract(tmp_path, monkeypatch)
    adapter = _FakeCatalogAdapter(narrow={_READINGS: _readings_metadata()})
    monkeypatch.setattr(catalog_runtime, "build_catalog_adapter", lambda: adapter)

    outputs = asyncio.run(_run(_weather_selection, "Count observations by station"))

    final = outputs[-1]
    assert final["status"] == "catalog_context_grounded"
    assert final["next_step"] == "guarded_sql_generation"
    assert final["catalog_route"] == "narrow"
    assert [item["source"] for item in final["catalog_context"]] == [_READINGS]


def test_workflow_broad_without_allowlist_clarifies(monkeypatch, tmp_path):
    _write_weather_contract(tmp_path, monkeypatch)
    monkeypatch.delenv("CATALOG_ALLOWED_PROJECTS", raising=False)
    monkeypatch.delenv("CATALOG_ALLOWED_DATASETS", raising=False)
    adapter = _FakeCatalogAdapter(broad=(_readings_metadata(),))
    monkeypatch.setattr(catalog_runtime, "build_catalog_adapter", lambda: adapter)

    outputs = asyncio.run(_run(_broad_selection, "Something unconfigured"))

    final = outputs[-1]
    assert final["status"] == "catalog_context_insufficient"
    assert final["next_step"] == "clarify_or_refuse"
    assert final["catalog_context"] == []


def test_workflow_narrow_insufficient_falls_through_to_broad(monkeypatch, tmp_path):
    _write_weather_contract(tmp_path, monkeypatch)
    monkeypatch.setenv("CATALOG_ALLOWED_DATASETS", "example-project.climate")
    adapter = _FakeCatalogAdapter(narrow={}, broad=(_readings_metadata(),))
    monkeypatch.setattr(catalog_runtime, "build_catalog_adapter", lambda: adapter)

    outputs = asyncio.run(_run(_weather_selection, "Count observations by station"))

    final = outputs[-1]
    assert final["status"] == "catalog_context_grounded"
    assert final["catalog_route"] == "broad"
    assert final["catalog_discovered_sources"] == [_READINGS]


def _write_weather_contract(tmp_path: Path, monkeypatch) -> None:
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
    monkeypatch.setenv("SEMANTIC_CONTRACT_PATH", str(contract_path))
