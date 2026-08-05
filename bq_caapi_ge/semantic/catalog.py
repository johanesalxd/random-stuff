"""Bounded Knowledge Catalog and BigQuery schema grounding for V2."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
import re
from typing import Any, Protocol, runtime_checkable

_ALLOWED_PROJECTS_ENV = "CATALOG_ALLOWED_PROJECTS"
_ALLOWED_DATASETS_ENV = "CATALOG_ALLOWED_DATASETS"
_COMPUTE_PROJECT_ENV = "GOOGLE_CLOUD_PROJECT"

_MAX_TABLES = 25
_MAX_FIELDS_PER_TABLE = 300
_MAX_TEXT_CHARS = 1_000
_MAX_SEARCH_SCOPES = 10
_MAX_CONTEXT_RESOURCES = 10
_CONTEXT_BUDGET = "10000"

_PROJECT_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9-]{4,28}[A-Za-z0-9]$")
_DATASET_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,1023}$")
_TABLE_PATTERN = re.compile(r"^[A-Za-z_0-9][A-Za-z0-9_$]{0,1023}$")
_ENTRY_LOCATION_PATTERN = re.compile(r"/locations/([^/]+)/")

_SAFE_CONTEXT_KEYS = frozenset(
    {
        "ancestors",
        "business_description",
        "business_descriptions",
        "business_metadata",
        "clustering",
        "column",
        "column_name",
        "columns",
        "contact",
        "contacts",
        "data_quality",
        "data_quality_status",
        "dataset",
        "description",
        "descriptions",
        "display_name",
        "field",
        "field_name",
        "fields",
        "fully_qualified_name",
        "glossary",
        "glossary_terms",
        "guideline",
        "guidelines",
        "join",
        "join_condition",
        "join_conditions",
        "joins",
        "label",
        "labels",
        "metadata",
        "mode",
        "name",
        "operational_metadata",
        "overview",
        "owner",
        "owners",
        "partitioning",
        "path",
        "primary_key",
        "primary_keys",
        "quality",
        "quality_status",
        "refresh_cadence",
        "related_resource",
        "related_resources",
        "relationship",
        "relationships",
        "resource",
        "resource_name",
        "resources",
        "schema",
        "sql",
        "sql_example",
        "sql_examples",
        "suggested_queries",
        "table",
        "table_name",
        "technical_metadata",
        "term",
        "terms",
        "type",
        "verified_queries",
    }
)


class CatalogAccessError(ValueError):
    """Raised when catalog access is invalid, unconfigured, or unavailable."""


@dataclass(frozen=True)
class CatalogSource:
    """A validated fully qualified BigQuery source."""

    project: str
    dataset: str
    table: str

    @property
    def qualified_name(self) -> str:
        """Returns the ``project.dataset.table`` identifier."""
        return f"{self.project}.{self.dataset}.{self.table}"

    @property
    def dataset_id(self) -> str:
        """Returns the ``project.dataset`` identifier."""
        return f"{self.project}.{self.dataset}"


@dataclass(frozen=True)
class CatalogField:
    """One bounded BigQuery schema field."""

    name: str
    type: str
    mode: str = "NULLABLE"
    description: str = ""


@dataclass(frozen=True)
class TableMetadata:
    """Bounded current schema metadata for one physical table."""

    source: str
    fields: tuple[CatalogField, ...]
    description: str = ""
    retrieved_at: str = ""

    def to_context(self) -> dict[str, Any]:
        """Returns JSON-safe metadata for model context."""
        return {
            "source": self.source,
            "description": self.description,
            "retrieved_at": self.retrieved_at,
            "fields": [
                {
                    "name": field_.name,
                    "type": field_.type,
                    "mode": field_.mode,
                    "description": field_.description,
                }
                for field_ in self.fields
            ],
        }


def parse_catalog_source(value: str) -> CatalogSource:
    """Parses a ``project.dataset.table`` source.

    Args:
        value: Candidate fully qualified source.

    Returns:
        Validated source.

    Raises:
        CatalogAccessError: If the source is malformed.
    """
    if not isinstance(value, str):
        raise CatalogAccessError(f"source must be a string: {value!r}")
    parts = value.split(".")
    if len(parts) != 3:
        raise CatalogAccessError(
            f"source must be exactly project.dataset.table: {value!r}"
        )
    project, dataset, table = (part.strip() for part in parts)
    if not _PROJECT_PATTERN.match(project):
        raise CatalogAccessError(f"invalid project in source: {value!r}")
    if not _DATASET_PATTERN.match(dataset):
        raise CatalogAccessError(f"invalid dataset in source: {value!r}")
    if not _TABLE_PATTERN.match(table):
        raise CatalogAccessError(f"invalid table in source: {value!r}")
    return CatalogSource(project=project, dataset=dataset, table=table)


def resolve_narrow_sources(source_names: list[str]) -> tuple[CatalogSource, ...]:
    """Builds the exact source set selected by semantic contracts."""
    if not source_names:
        raise CatalogAccessError("narrow grounding requires at least one source")
    sources = {
        parse_catalog_source(name).qualified_name: parse_catalog_source(name)
        for name in source_names
    }
    return tuple(sources[name] for name in sorted(sources))


def parse_allowed_projects(raw: str | None = None) -> frozenset[str]:
    """Parses the default-deny broad project allowlist."""
    values = _split_csv(raw if raw is not None else os.getenv(_ALLOWED_PROJECTS_ENV))
    return frozenset(value for value in values if _PROJECT_PATTERN.match(value))


def parse_allowed_datasets(raw: str | None = None) -> frozenset[str]:
    """Parses the default-deny broad dataset allowlist."""
    values = _split_csv(raw if raw is not None else os.getenv(_ALLOWED_DATASETS_ENV))
    allowed: set[str] = set()
    for value in values:
        parts = value.split(".")
        if len(parts) != 2:
            continue
        project, dataset = (part.strip() for part in parts)
        if _PROJECT_PATTERN.match(project) and _DATASET_PATTERN.match(dataset):
            allowed.add(f"{project}.{dataset}")
    return frozenset(allowed)


def is_source_in_scope(
    source: CatalogSource,
    *,
    allowed_projects: frozenset[str],
    allowed_datasets: frozenset[str],
) -> bool:
    """Returns whether a broad-search result is explicitly allowed."""
    if not allowed_projects and not allowed_datasets:
        return False
    return source.project in allowed_projects or source.dataset_id in allowed_datasets


def build_table_metadata(
    *,
    source: str,
    fields: list[dict[str, Any]] | tuple[CatalogField, ...],
    description: str = "",
    now: datetime | None = None,
) -> TableMetadata:
    """Builds bounded table schema metadata."""
    normalized: list[CatalogField] = []
    for field_ in list(fields)[:_MAX_FIELDS_PER_TABLE]:
        if isinstance(field_, CatalogField):
            normalized.append(
                CatalogField(
                    name=field_.name,
                    type=field_.type,
                    mode=field_.mode or "NULLABLE",
                    description=_bound_text(field_.description),
                )
            )
            continue
        normalized.append(
            CatalogField(
                name=str(field_.get("name", "")),
                type=str(field_.get("type", "")),
                mode=str(field_.get("mode", "NULLABLE") or "NULLABLE"),
                description=_bound_text(str(field_.get("description", ""))),
            )
        )
    timestamp = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    return TableMetadata(
        source=source,
        fields=tuple(normalized),
        description=_bound_text(description),
        retrieved_at=timestamp.isoformat(timespec="seconds"),
    )


def bound_table_results(results: list[TableMetadata]) -> tuple[TableMetadata, ...]:
    """Caps table metadata returned to the workflow."""
    return tuple(results[:_MAX_TABLES])


def sanitize_knowledge_context(raw: str) -> dict[str, Any] | list[Any] | None:
    """Parses LookupContext JSON into an allowlisted metadata structure.

    Args:
        raw: Raw JSON context returned by Knowledge Catalog.

    Returns:
        Sanitized metadata, or ``None`` when parsing or sanitization fails closed.
    """
    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError):
        return None
    sanitized = _sanitize_value(parsed, allow_primitive=False)
    if sanitized in ({}, [], None):
        return None
    return sanitized


@runtime_checkable
class CatalogAdapter(Protocol):
    """Injectable Knowledge Catalog and schema boundary."""

    def fetch_table_metadata(
        self,
        sources: tuple[CatalogSource, ...],
    ) -> tuple[TableMetadata, ...]:
        """Returns current schemas for exact sources."""
        ...

    def search_tables(
        self,
        *,
        question: str,
        allowed_projects: frozenset[str],
        allowed_datasets: frozenset[str],
    ) -> tuple[TableMetadata, ...]:
        """Returns current schemas for allowed semantic-search candidates."""
        ...

    def fetch_knowledge_context(
        self,
        sources: tuple[CatalogSource, ...],
        *,
        question: str,
    ) -> tuple[dict[str, Any], ...]:
        """Returns sanitized Knowledge Catalog context for exact sources."""
        ...


class BigQueryCatalogAdapter:
    """Current-schema adapter backed by the BigQuery metadata API."""

    def __init__(
        self, *, project: str, client: Any = None, now: datetime | None = None
    ):
        self._project = project
        self._client = client
        self._now = now

    def _get_client(self) -> Any:
        if self._client is None:
            try:
                from google.cloud import bigquery
            except ImportError as error:  # pragma: no cover - dependency guard
                raise CatalogAccessError(
                    "google-cloud-bigquery is required for schema grounding"
                ) from error
            self._client = bigquery.Client(project=self._project)
        return self._client

    def fetch_table_metadata(
        self,
        sources: tuple[CatalogSource, ...],
    ) -> tuple[TableMetadata, ...]:
        """Fetches current schemas for exact sources."""
        client = self._get_client()
        results: list[TableMetadata] = []
        for source in sources:
            table = self._get_table(client, source.qualified_name)
            if table is not None:
                results.append(self._table_to_metadata(source.qualified_name, table))
        return tuple(results)

    def search_tables(
        self,
        *,
        question: str,
        allowed_projects: frozenset[str],
        allowed_datasets: frozenset[str],
    ) -> tuple[TableMetadata, ...]:
        """Returns no broad results; Knowledge Catalog owns V2 discovery."""
        return ()

    def fetch_knowledge_context(
        self,
        sources: tuple[CatalogSource, ...],
        *,
        question: str,
    ) -> tuple[dict[str, Any], ...]:
        """Returns no business context without Knowledge Catalog."""
        return ()

    def _get_table(self, client: Any, qualified_name: str) -> Any:
        not_found, forbidden, api_error = _lookup_errors()
        try:
            return client.get_table(qualified_name)
        except (not_found, forbidden):
            return None
        except api_error as error:
            raise CatalogAccessError(
                f"BigQuery schema retrieval failed for {qualified_name}: {error}"
            ) from error

    def _table_to_metadata(self, qualified_name: str, table: Any) -> TableMetadata:
        fields = [
            {
                "name": getattr(schema_field, "name", ""),
                "type": getattr(schema_field, "field_type", ""),
                "mode": getattr(schema_field, "mode", "NULLABLE") or "NULLABLE",
                "description": getattr(schema_field, "description", "") or "",
            }
            for schema_field in getattr(table, "schema", []) or []
        ]
        return build_table_metadata(
            source=qualified_name,
            fields=fields,
            description=getattr(table, "description", "") or "",
            now=self._now,
        )


class KnowledgeCatalogAdapter:
    """Knowledge Catalog search and context over current BigQuery schemas."""

    discovery_backend = "knowledge_catalog_semantic"

    def __init__(
        self,
        *,
        project: str,
        schema_adapter: BigQueryCatalogAdapter,
        client: Any = None,
    ):
        self._project = project
        self._schema_adapter = schema_adapter
        self._client = client
        self._entry_names: dict[str, str] = {}

    def _get_client(self) -> Any:
        if self._client is None:
            try:
                from google.cloud import dataplex_v1
            except ImportError as error:  # pragma: no cover - dependency guard
                raise CatalogAccessError(
                    "google-cloud-dataplex is required for Knowledge Catalog"
                ) from error
            self._client = dataplex_v1.CatalogServiceClient()
        return self._client

    def fetch_table_metadata(
        self,
        sources: tuple[CatalogSource, ...],
    ) -> tuple[TableMetadata, ...]:
        """Delegates current physical schema lookup to BigQuery."""
        return self._schema_adapter.fetch_table_metadata(sources)

    def search_tables(
        self,
        *,
        question: str,
        allowed_projects: frozenset[str],
        allowed_datasets: frozenset[str],
    ) -> tuple[TableMetadata, ...]:
        """Discovers allowed BigQuery tables with semantic SearchEntries."""
        if not allowed_projects and not allowed_datasets:
            return ()
        seen: dict[str, CatalogSource] = {}
        for project in _distinct_allowed_projects(
            allowed_projects,
            allowed_datasets,
        ):
            for source, entry_name in self._search_entries(
                question=question,
                scope_project=project,
                semantic_search=True,
            ):
                if not is_source_in_scope(
                    source,
                    allowed_projects=allowed_projects,
                    allowed_datasets=allowed_datasets,
                ):
                    continue
                seen.setdefault(source.qualified_name, source)
                if entry_name:
                    self._entry_names[source.qualified_name] = entry_name
                if len(seen) >= _MAX_TABLES:
                    break
            if len(seen) >= _MAX_TABLES:
                break
        sources = tuple(seen[name] for name in sorted(seen))
        return self.fetch_table_metadata(sources)

    def fetch_knowledge_context(
        self,
        sources: tuple[CatalogSource, ...],
        *,
        question: str,
    ) -> tuple[dict[str, Any], ...]:
        """Returns sanitized LookupContext metadata grouped by entry location."""
        self._resolve_entry_names(sources)
        grouped: dict[str, list[str]] = {}
        for source in sources:
            entry_name = self._entry_names.get(source.qualified_name)
            if not entry_name:
                continue
            location = _entry_location(entry_name)
            if location:
                grouped.setdefault(location, []).append(entry_name)

        contexts: list[dict[str, Any]] = []
        client = self._get_client()
        for location, resource_names in sorted(grouped.items()):
            for offset in range(0, len(resource_names), _MAX_CONTEXT_RESOURCES):
                resources = resource_names[offset : offset + _MAX_CONTEXT_RESOURCES]
                try:
                    from google.cloud import dataplex_v1

                    response = client.lookup_context(
                        request=dataplex_v1.LookupContextRequest(
                            name=f"projects/{self._project}/locations/{location}",
                            resources=resources,
                            context=(
                                "Provide schemas, descriptions, relationships, "
                                "guidelines, quality status, and SQL examples for "
                                f"this question: {_bound_text(question)}. Omit data values."
                            ),
                            options={
                                "format": "json",
                                "context_budget": _CONTEXT_BUDGET,
                            },
                        )
                    )
                except _dataplex_errors():
                    continue
                sanitized = sanitize_knowledge_context(
                    str(getattr(response, "context", "") or "")
                )
                if sanitized is not None:
                    contexts.append(
                        {
                            "location": location,
                            "resources": list(resources),
                            "context": sanitized,
                        }
                    )
        return tuple(contexts)

    def _resolve_entry_names(self, sources: tuple[CatalogSource, ...]) -> None:
        for source in sources:
            if source.qualified_name in self._entry_names:
                continue
            query = f"{source.table} system=bigquery type=table"
            try:
                matches = self._search_entries(
                    question=query,
                    scope_project=source.project,
                    semantic_search=False,
                )
            except _dataplex_errors():
                continue
            for candidate, entry_name in matches:
                if candidate.qualified_name == source.qualified_name and entry_name:
                    self._entry_names[source.qualified_name] = entry_name
                    break

    def _search_entries(
        self,
        *,
        question: str,
        scope_project: str,
        semantic_search: bool,
    ) -> list[tuple[CatalogSource, str]]:
        from google.cloud import dataplex_v1

        request = dataplex_v1.SearchEntriesRequest(
            name=f"projects/{self._project}/locations/global",
            query=f"{_bound_text(question)} system=bigquery type=table".strip(),
            page_size=_MAX_TABLES,
            semantic_search=semantic_search,
            scope=f"projects/{scope_project}",
        )
        matches: list[tuple[CatalogSource, str]] = []
        for index, result in enumerate(
            self._get_client().search_entries(request=request)
        ):
            if index >= _MAX_TABLES:
                break
            source = _result_to_source(result)
            if source is None:
                continue
            entry = getattr(result, "dataplex_entry", None)
            matches.append((source, str(getattr(entry, "name", "") or "")))
        return matches


def build_catalog_adapter() -> CatalogAdapter:
    """Builds the V2 Knowledge Catalog adapter."""
    project = os.getenv(_COMPUTE_PROJECT_ENV, "").strip()
    if not project:
        raise CatalogAccessError(
            f"{_COMPUTE_PROJECT_ENV} must be set to build the catalog adapter"
        )
    schema_adapter = BigQueryCatalogAdapter(project=project)
    return KnowledgeCatalogAdapter(
        project=project,
        schema_adapter=schema_adapter,
    )


def _sanitize_value(value: Any, *, allow_primitive: bool) -> Any:
    if isinstance(value, dict):
        sanitized: dict[str, Any] = {}
        for key, nested in value.items():
            normalized = _normalize_key(str(key))
            if normalized not in _SAFE_CONTEXT_KEYS:
                continue
            cleaned = _sanitize_value(nested, allow_primitive=True)
            if cleaned not in ({}, [], None, ""):
                sanitized[str(key)] = cleaned
        return sanitized
    if isinstance(value, list):
        items = [
            cleaned
            for item in value
            if (cleaned := _sanitize_value(item, allow_primitive=allow_primitive))
            not in ({}, [], None, "")
        ]
        return items
    if allow_primitive and isinstance(value, (str, int, float, bool)):
        return _bound_text(value) if isinstance(value, str) else value
    return None


def _normalize_key(value: str) -> str:
    snake = re.sub(r"(?<!^)(?=[A-Z])", "_", value).lower()
    return re.sub(r"[^a-z0-9]+", "_", snake).strip("_")


def _result_to_source(item: Any) -> CatalogSource | None:
    entry = getattr(item, "dataplex_entry", None)
    fqn = getattr(entry, "fully_qualified_name", "") if entry is not None else ""
    if fqn and fqn.startswith("bigquery:"):
        return _safe_parse_source(fqn[len("bigquery:") :])
    linked = str(getattr(item, "linked_resource", "") or "")
    match = re.search(r"projects/([^/]+)/datasets/([^/]+)/tables/([^/]+)", linked)
    return _safe_parse_source(".".join(match.groups())) if match else None


def _safe_parse_source(candidate: str) -> CatalogSource | None:
    try:
        return parse_catalog_source(candidate.strip())
    except CatalogAccessError:
        return None


def _entry_location(entry_name: str) -> str:
    match = _ENTRY_LOCATION_PATTERN.search(entry_name)
    return match.group(1) if match else ""


def _distinct_allowed_projects(
    allowed_projects: frozenset[str],
    allowed_datasets: frozenset[str],
) -> list[str]:
    projects = set(allowed_projects)
    projects.update(dataset.split(".", 1)[0] for dataset in allowed_datasets)
    return sorted(projects)[:_MAX_SEARCH_SCOPES]


def _split_csv(raw: str | None) -> list[str]:
    return [value.strip() for value in (raw or "").split(",") if value.strip()]


def _bound_text(value: str) -> str:
    return " ".join(str(value).split())[:_MAX_TEXT_CHARS]


def _lookup_errors() -> tuple[type[Exception], type[Exception], type[Exception]]:
    try:
        from google.api_core import exceptions
    except ImportError:  # pragma: no cover - dependency guard
        return (LookupError, PermissionError, Exception)
    return (exceptions.NotFound, exceptions.Forbidden, exceptions.GoogleAPICallError)


def _dataplex_errors() -> tuple[type[Exception], ...]:
    try:
        from google.api_core import exceptions
    except ImportError:  # pragma: no cover - dependency guard
        return (Exception,)
    return (exceptions.GoogleAPICallError, exceptions.RetryError)
