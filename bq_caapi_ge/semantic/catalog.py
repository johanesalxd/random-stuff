"""Knowledge Catalog grounding boundary for Phase 7.

This module defines the deterministic, testable core of catalog grounding:
physical-source parsing, default-deny broad-search allowlists, bounded and
redacted metadata payloads, and the injectable catalog adapter boundary.

It never generates or executes SQL. Live catalog access is confined to adapter
implementations behind :class:`CatalogAdapter`; unit tests inject fakes and must
not perform live catalog calls.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
import os
import re
from typing import Any, Protocol, runtime_checkable

_ALLOWED_PROJECTS_ENV = "CATALOG_ALLOWED_PROJECTS"
_ALLOWED_DATASETS_ENV = "CATALOG_ALLOWED_DATASETS"
_COMPUTE_PROJECT_ENV = "GOOGLE_CLOUD_PROJECT"
_DATAPLEX_ENABLED_ENV = "CATALOG_DATAPLEX_ENABLED"

# Bounds keep catalog payloads small enough for prompt-safe grounding context.
_MAX_TABLES = 25
_MAX_FIELDS_PER_TABLE = 300
_MAX_TEXT_CHARS = 1_000
# Bounds keep broad discovery from scanning an unbounded catalog surface.
_MAX_SEARCH_DATASETS = 50
_MAX_SEARCH_TABLES_PER_DATASET = 200
_MIN_SEARCH_TOKEN_LENGTH = 3
# Bounds keep Dataplex-backed discovery from issuing an unbounded fan-out of
# per-project search calls.
_MAX_SEARCH_SCOPES = 10
# Structural profile signals are rounded and value-free; a candidate key needs a
# near-unique, non-null column.
_RATIO_PRECISION = 3
_CANDIDATE_KEY_DISTINCT_MIN = 0.999
_CANDIDATE_KEY_NULL_MAX = 1e-9
_TTRUE = frozenset({"1", "true", "yes", "on"})
# Component patterns follow BigQuery identifier rules; project IDs allow hyphens.
_PROJECT_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9-]{4,28}[A-Za-z0-9]$")
_DATASET_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,1023}$")
_TABLE_PATTERN = re.compile(r"^[A-Za-z_0-9][A-Za-z0-9_$]{0,1023}$")


class CatalogAccessError(ValueError):
    """Raised when catalog access is unconfigured, out of scope, or unavailable."""


@dataclass(frozen=True)
class CatalogSource:
    """A fully qualified, validated BigQuery source reference."""

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
    """One typed column with optional, bounded description text.

    Profile-derived signals are strictly structural and value-free: ratios and a
    candidate-key flag only. Actual data values (samples, min, max, top-N,
    averages, quantiles) are never stored here.
    """

    name: str
    type: str
    mode: str = "NULLABLE"
    description: str = ""
    null_ratio: float | None = None
    distinct_ratio: float | None = None
    is_candidate_key: bool = False


@dataclass(frozen=True)
class TableMetadata:
    """Bounded, redacted, timestamped metadata for one physical source."""

    source: str
    fields: tuple[CatalogField, ...]
    description: str = ""
    retrieved_at: str = ""
    redacted_profile: bool = False
    has_insight: bool = False

    def to_context(self) -> dict[str, Any]:
        """Returns a JSON-safe, prompt-safe representation of the metadata."""
        return {
            "source": self.source,
            "description": self.description,
            "retrieved_at": self.retrieved_at,
            "redacted_profile": self.redacted_profile,
            "has_insight": self.has_insight,
            "fields": [self._field_context(field_) for field_ in self.fields],
        }

    @staticmethod
    def _field_context(field_: CatalogField) -> dict[str, Any]:
        context: dict[str, Any] = {
            "name": field_.name,
            "type": field_.type,
            "mode": field_.mode,
            "description": field_.description,
        }
        # Structural signals are emitted only when present, and never carry values.
        if field_.null_ratio is not None:
            context["null_ratio"] = field_.null_ratio
        if field_.distinct_ratio is not None:
            context["distinct_ratio"] = field_.distinct_ratio
        if field_.is_candidate_key:
            context["is_candidate_key"] = True
        return context


def parse_catalog_source(value: str) -> CatalogSource:
    """Parses and validates a ``project.dataset.table`` source string.

    Args:
        value: Candidate fully qualified source reference.

    Returns:
        The validated :class:`CatalogSource`.

    Raises:
        CatalogAccessError: If the value is not exactly a valid three-part name.
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
    """Validates curated narrow-path sources into an exact allowlist.

    Narrow retrieval may access only the exact fully qualified sources that a
    validated semantic contract selected. This forms the narrow-path allowlist;
    it never widens to a dataset or project.

    Args:
        source_names: ``project.dataset.table`` names from the Phase 6 handoff.

    Returns:
        A deduplicated, ordered tuple of validated sources.

    Raises:
        CatalogAccessError: If no sources are provided or any is invalid.
    """
    if not source_names:
        raise CatalogAccessError("narrow grounding requires at least one source")
    resolved: dict[str, CatalogSource] = {}
    for name in source_names:
        source = parse_catalog_source(name)
        resolved[source.qualified_name] = source
    return tuple(resolved[key] for key in sorted(resolved))


def parse_allowed_projects(raw: str | None = None) -> frozenset[str]:
    """Parses the broad-search project allowlist with fail-closed defaults.

    Args:
        raw: Comma-separated project IDs. Reads ``CATALOG_ALLOWED_PROJECTS`` when
            ``None``.

    Returns:
        The set of permitted project IDs; empty when unconfigured or invalid.
    """
    values = _split_csv(raw if raw is not None else os.getenv(_ALLOWED_PROJECTS_ENV))
    return frozenset(value for value in values if _PROJECT_PATTERN.match(value))


def parse_allowed_datasets(raw: str | None = None) -> frozenset[str]:
    """Parses the broad-search dataset allowlist with fail-closed defaults.

    Args:
        raw: Comma-separated ``project.dataset`` IDs. Reads
            ``CATALOG_ALLOWED_DATASETS`` when ``None``.

    Returns:
        The set of permitted ``project.dataset`` IDs; empty when unconfigured or
        invalid.
    """
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
    """Returns whether a source is within a configured broad-search allowlist.

    Args:
        source: Candidate source.
        allowed_projects: Permitted project IDs.
        allowed_datasets: Permitted ``project.dataset`` IDs.

    Returns:
        ``True`` only when the source's project or dataset is explicitly allowed.
    """
    if not allowed_projects and not allowed_datasets:
        return False
    return source.project in allowed_projects or source.dataset_id in allowed_datasets


def build_table_metadata(
    *,
    source: str,
    fields: list[dict[str, Any]] | tuple[CatalogField, ...],
    description: str = "",
    had_profile: bool = False,
    now: datetime | None = None,
) -> TableMetadata:
    """Builds a bounded, redacted, timestamped :class:`TableMetadata`.

    Sensitive profile sample values are never copied into the payload; only the
    presence of a profile is recorded. Field counts and free text are bounded.

    Args:
        source: Fully qualified source name.
        fields: Column definitions as dicts or :class:`CatalogField` values.
        description: Optional table description.
        had_profile: Whether an underlying profile aspect existed.
        now: Injected timestamp for deterministic tests.

    Returns:
        A prompt-safe metadata payload.
    """
    normalized: list[CatalogField] = []
    for field_ in list(fields)[:_MAX_FIELDS_PER_TABLE]:
        if isinstance(field_, CatalogField):
            normalized.append(
                CatalogField(
                    name=field_.name,
                    type=field_.type,
                    mode=field_.mode or "NULLABLE",
                    description=_bound_text(field_.description),
                    null_ratio=field_.null_ratio,
                    distinct_ratio=field_.distinct_ratio,
                    is_candidate_key=field_.is_candidate_key,
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
        redacted_profile=bool(had_profile),
    )


def bound_table_results(results: list[TableMetadata]) -> tuple[TableMetadata, ...]:
    """Caps the number of returned tables to the configured maximum.

    Args:
        results: Retrieved table metadata.

    Returns:
        A tuple bounded to ``_MAX_TABLES`` entries.
    """
    return tuple(results[:_MAX_TABLES])


@runtime_checkable
class CatalogAdapter(Protocol):
    """Injectable boundary for Knowledge Catalog access.

    Implementations must not generate or execute SQL. Narrow retrieval must use
    only the exact provided sources; broad retrieval must stay within the given
    allowlists.
    """

    def fetch_table_metadata(
        self,
        sources: tuple[CatalogSource, ...],
    ) -> tuple[TableMetadata, ...]:
        """Returns bounded, redacted metadata for exactly the given sources."""
        ...

    def search_tables(
        self,
        *,
        question: str,
        allowed_projects: frozenset[str],
        allowed_datasets: frozenset[str],
    ) -> tuple[TableMetadata, ...]:
        """Returns bounded metadata for sources within the given allowlists."""
        ...


class BigQueryCatalogAdapter:
    """Live catalog adapter backed by the BigQuery metadata API.

    Narrow retrieval reads current schema for exactly the requested sources. Broad
    retrieval enumerates only the configured project and dataset allowlists. The
    adapter issues metadata calls only; it never runs SQL. The BigQuery client is
    created lazily so construction performs no network access, and it can be
    injected for deterministic tests.
    """

    discovery_backend = "name_match"

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
                    "google-cloud-bigquery is required for the live catalog adapter"
                ) from error
            self._client = bigquery.Client(project=self._project)
        return self._client

    def fetch_table_metadata(
        self,
        sources: tuple[CatalogSource, ...],
    ) -> tuple[TableMetadata, ...]:
        """Returns current schema metadata for exactly the requested sources.

        Sources that are absent or unauthorized are omitted so the caller can
        surface them as missing context; systemic access failures raise.
        """
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
        """Returns metadata for allowlisted tables whose names match the question.

        Discovery never leaves the configured allowlists: it enumerates only the
        explicit datasets and the datasets of allowlisted projects, ranks tables
        by question-token overlap on their names, and bounds the result set.
        """
        if not allowed_projects and not allowed_datasets:
            return ()
        client = self._get_client()
        tokens = _tokenize(question)
        if not tokens:
            return ()
        scored: list[tuple[int, str]] = []
        for dataset_id in self._resolve_search_datasets(
            client, allowed_projects, allowed_datasets
        ):
            for qualified_name in self._list_dataset_tables(client, dataset_id):
                score = _name_match_score(qualified_name, tokens)
                if score > 0:
                    scored.append((score, qualified_name))
        scored.sort(key=lambda item: (-item[0], item[1]))
        results: list[TableMetadata] = []
        for _, qualified_name in scored[:_MAX_TABLES]:
            table = self._get_table(client, qualified_name)
            if table is not None:
                results.append(self._table_to_metadata(qualified_name, table))
        return bound_table_results(results)

    def _resolve_search_datasets(
        self,
        client: Any,
        allowed_projects: frozenset[str],
        allowed_datasets: frozenset[str],
    ) -> list[str]:
        datasets: list[str] = sorted(allowed_datasets)
        for project in sorted(allowed_projects):
            for dataset in self._list_project_datasets(client, project):
                if dataset not in datasets:
                    datasets.append(dataset)
        return datasets[:_MAX_SEARCH_DATASETS]

    def _list_project_datasets(self, client: Any, project: str) -> list[str]:
        try:
            listed = client.list_datasets(project)
        except _api_errors() as error:
            raise CatalogAccessError(
                f"catalog dataset listing failed for {project}: {error}"
            ) from error
        datasets = []
        for item in listed:
            dataset_id = getattr(item, "dataset_id", None)
            item_project = getattr(item, "project", project)
            if dataset_id:
                datasets.append(f"{item_project}.{dataset_id}")
        return datasets

    def _list_dataset_tables(self, client: Any, dataset_id: str) -> list[str]:
        try:
            listed = client.list_tables(dataset_id)
        except _api_errors() as error:
            raise CatalogAccessError(
                f"catalog table listing failed for {dataset_id}: {error}"
            ) from error
        names = []
        for index, item in enumerate(listed):
            if index >= _MAX_SEARCH_TABLES_PER_DATASET:
                break
            project = getattr(item, "project", "")
            dataset = getattr(item, "dataset_id", "")
            table = getattr(item, "table_id", "")
            if project and dataset and table:
                names.append(f"{project}.{dataset}.{table}")
        return names

    def _get_table(self, client: Any, qualified_name: str) -> Any:
        not_found, forbidden, api_error = _lookup_errors()
        try:
            return client.get_table(qualified_name)
        except (not_found, forbidden):
            return None
        except api_error as error:
            raise CatalogAccessError(
                f"catalog schema retrieval failed for {qualified_name}: {error}"
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
            had_profile=False,
            now=self._now,
        )


class DataplexCatalogAdapter:
    """Dataplex-backed discovery and structural enrichment over a BigQuery adapter.

    This decorator adds two optional capabilities on top of an inner
    :class:`CatalogAdapter` (BigQuery remains the schema source of truth):

    - broad discovery via Dataplex Catalog search, re-clamped to the configured
      allowlists and falling back to the inner name-match search on error or when
      no in-scope entry is found
    - structural, value-free profile enrichment (null ratio, distinct ratio, and a
      derived candidate-key flag) plus presence of a generated insight aspect

    Sensitive profile values (samples, min, max, top-N, averages, quantiles) are
    never read or surfaced. The Dataplex client is created lazily and is injectable
    for deterministic tests; enrichment and search are best-effort and never raise
    into the workflow.
    """

    discovery_backend = "dataplex"

    def __init__(
        self,
        *,
        project: str,
        inner: CatalogAdapter,
        client: Any = None,
        now: datetime | None = None,
    ):
        self._project = project
        self._inner = inner
        self._client = client
        self._now = now
        self.last_search_backend = "dataplex"

    def _get_client(self) -> Any:
        if self._client is None:
            try:
                from google.cloud import dataplex_v1
            except ImportError as error:  # pragma: no cover - dependency guard
                raise CatalogAccessError(
                    "google-cloud-dataplex is required for the Dataplex adapter"
                ) from error
            self._client = dataplex_v1.CatalogServiceClient()
        return self._client

    def fetch_table_metadata(
        self,
        sources: tuple[CatalogSource, ...],
    ) -> tuple[TableMetadata, ...]:
        """Returns inner schema metadata enriched with structural profile signals."""
        base = self._inner.fetch_table_metadata(sources)
        return tuple(self._enrich(item) for item in base)

    def search_tables(
        self,
        *,
        question: str,
        allowed_projects: frozenset[str],
        allowed_datasets: frozenset[str],
    ) -> tuple[TableMetadata, ...]:
        """Discovers allowlisted sources via Dataplex, then loads authoritative schema.

        Discovery results are always re-clamped to the allowlists. On any Dataplex
        error, or when no in-scope entry is found, this falls back to the inner
        name-match search so broad discovery still works without Dataplex.
        """
        if not allowed_projects and not allowed_datasets:
            self.last_search_backend = "dataplex"
            return ()
        try:
            discovered = self._dataplex_search(
                question, allowed_projects, allowed_datasets
            )
        except _dataplex_errors():
            discovered = []
        in_scope = [
            source
            for source in discovered
            if is_source_in_scope(
                source,
                allowed_projects=allowed_projects,
                allowed_datasets=allowed_datasets,
            )
        ]
        if not in_scope:
            self.last_search_backend = "name_match_fallback"
            return self._inner.search_tables(
                question=question,
                allowed_projects=allowed_projects,
                allowed_datasets=allowed_datasets,
            )
        self.last_search_backend = "dataplex"
        metadata = self.fetch_table_metadata(tuple(in_scope))
        return bound_table_results(list(metadata))

    def _dataplex_search(
        self,
        question: str,
        allowed_projects: frozenset[str],
        allowed_datasets: frozenset[str],
    ) -> list[CatalogSource]:
        tokens = _tokenize(question)
        if not tokens:
            return []
        from google.cloud import dataplex_v1

        client = self._get_client()
        query = self._build_search_query(tokens)
        seen: dict[str, CatalogSource] = {}
        for project in _distinct_allowed_projects(allowed_projects, allowed_datasets):
            request = dataplex_v1.SearchEntriesRequest(
                name=f"projects/{self._project}/locations/global",
                query=query,
                page_size=_MAX_TABLES,
                semantic_search=False,
                scope=f"projects/{project}",
            )
            for index, item in enumerate(client.search_entries(request=request)):
                if index >= _MAX_TABLES:
                    break
                source = self._result_to_source(item)
                if source is not None:
                    seen.setdefault(source.qualified_name, source)
        return list(seen.values())

    @staticmethod
    def _build_search_query(tokens: frozenset[str]) -> str:
        terms = " ".join(sorted(tokens))
        return f"{terms} system=bigquery type=table".strip()

    def _result_to_source(self, item: Any) -> CatalogSource | None:
        entry = getattr(item, "dataplex_entry", None)
        fqn = getattr(entry, "fully_qualified_name", "") if entry is not None else ""
        if fqn and fqn.startswith("bigquery:"):
            return _safe_parse_source(fqn[len("bigquery:") :])
        linked = getattr(item, "linked_resource", "") or ""
        return _parse_linked_resource(linked)

    def _enrich(self, metadata: TableMetadata) -> TableMetadata:
        try:
            entry = self._lookup_entry(metadata.source)
        except _dataplex_errors():
            return metadata
        if entry is None:
            return metadata
        field_signals, had_profile, has_insight = _extract_profile_signals(entry)
        if not had_profile and not has_insight:
            return metadata
        fields = tuple(
            _apply_field_signals(field_, field_signals.get(field_.name))
            for field_ in metadata.fields
        )
        return replace(
            metadata,
            fields=fields,
            redacted_profile=metadata.redacted_profile or had_profile,
            has_insight=metadata.has_insight or has_insight,
        )

    def _lookup_entry(self, source: str) -> Any:
        from google.cloud import dataplex_v1

        client = self._get_client()
        # Best-effort lookup of the auto-generated BigQuery entry. The exact
        # regional entry group may vary; failures degrade gracefully to no
        # enrichment via the caller's error handling.
        project, dataset, table = source.split(".")
        entry_name = (
            f"projects/{project}/locations/global/entryGroups/@bigquery/"
            f"entries/bigquery.googleapis.com/projects/{project}/"
            f"datasets/{dataset}/tables/{table}"
        )
        request = dataplex_v1.LookupEntryRequest(
            name=f"projects/{self._project}/locations/global",
            view=dataplex_v1.EntryView.FULL,
            entry=entry_name,
        )
        return client.lookup_entry(request=request)


def build_catalog_adapter() -> CatalogAdapter:
    """Returns the configured live catalog adapter.

    The BigQuery-backed adapter reads current schema for narrow sources and
    enumerates the configured allowlists for broad discovery. When
    ``CATALOG_DATAPLEX_ENABLED`` is truthy, it is wrapped in
    :class:`DataplexCatalogAdapter`, which adds Dataplex Catalog search and
    structural, value-free profile enrichment while keeping BigQuery as the schema
    source of truth. A provider-backed smoke test is exercised under Phase 10
    evaluation.

    Raises:
        CatalogAccessError: If the compute project is not configured.
    """
    project = os.getenv(_COMPUTE_PROJECT_ENV, "").strip()
    if not project:
        raise CatalogAccessError(
            f"{_COMPUTE_PROJECT_ENV} must be set to build the live catalog adapter"
        )
    adapter: CatalogAdapter = BigQueryCatalogAdapter(project=project)
    if _dataplex_enabled():
        adapter = DataplexCatalogAdapter(project=project, inner=adapter)
    return adapter


def _dataplex_enabled() -> bool:
    return os.getenv(_DATAPLEX_ENABLED_ENV, "").strip().lower() in _TTRUE


def _api_errors() -> tuple[type[Exception], ...]:
    try:
        from google.api_core import exceptions
    except ImportError:  # pragma: no cover - dependency guard
        return (Exception,)
    return (exceptions.GoogleAPICallError, exceptions.RetryError)


def _lookup_errors() -> tuple[type[Exception], type[Exception], type[Exception]]:
    try:
        from google.api_core import exceptions
    except ImportError:  # pragma: no cover - dependency guard
        return (LookupError, PermissionError, Exception)
    return (exceptions.NotFound, exceptions.Forbidden, exceptions.GoogleAPICallError)


def _dataplex_errors() -> tuple[type[Exception], ...]:
    # Dataplex discovery and enrichment are best-effort: any Google API failure
    # (including auth or absent entries) degrades gracefully rather than breaking
    # the grounding flow.
    try:
        from google.api_core import exceptions
    except ImportError:  # pragma: no cover - dependency guard
        return (Exception,)
    return (exceptions.GoogleAPICallError, exceptions.RetryError)


def _distinct_allowed_projects(
    allowed_projects: frozenset[str],
    allowed_datasets: frozenset[str],
) -> list[str]:
    projects = set(allowed_projects)
    for dataset_id in allowed_datasets:
        project, _, dataset = dataset_id.partition(".")
        if project and dataset:
            projects.add(project)
    return sorted(projects)[:_MAX_SEARCH_SCOPES]


def _safe_parse_source(candidate: str) -> CatalogSource | None:
    try:
        return parse_catalog_source(candidate.strip())
    except CatalogAccessError:
        return None


def _parse_linked_resource(linked: str) -> CatalogSource | None:
    match = re.search(r"projects/([^/]+)/datasets/([^/]+)/tables/([^/]+)", linked or "")
    if not match:
        return None
    return _safe_parse_source(".".join(match.groups()))


def _extract_profile_signals(
    entry: Any,
) -> tuple[dict[str, tuple[float | None, float | None]], bool, bool]:
    """Reads only structural, value-free signals from an entry's aspects."""
    field_signals: dict[str, tuple[float | None, float | None]] = {}
    had_profile = False
    has_insight = False
    for key, aspect in _iter_aspects(getattr(entry, "aspects", None)):
        aspect_type = str(getattr(aspect, "aspect_type", "") or key or "").lower()
        if "profile" in aspect_type:
            had_profile = True
            field_signals.update(
                _parse_profile_fields(_struct_to_dict(getattr(aspect, "data", None)))
            )
        if "insight" in aspect_type or "documentation" in aspect_type:
            has_insight = True
    return field_signals, had_profile, has_insight


def _iter_aspects(aspects: Any):
    if not aspects:
        return
    items = getattr(aspects, "items", None)
    if callable(items):
        yield from items()
        return
    if isinstance(aspects, (list, tuple)):
        for aspect in aspects:
            yield "", aspect


def _struct_to_dict(data: Any) -> dict[str, Any]:
    if data is None:
        return {}
    if isinstance(data, dict):
        return data
    try:
        from google.protobuf.json_format import MessageToDict

        return MessageToDict(getattr(data, "_pb", data))
    except Exception:  # pragma: no cover - defensive conversion
        try:
            return dict(data)
        except Exception:
            return {}


def _parse_profile_fields(
    data: dict[str, Any],
) -> dict[str, tuple[float | None, float | None]]:
    signals: dict[str, tuple[float | None, float | None]] = {}
    for item in _find_field_list(data):
        if not isinstance(item, dict):
            continue
        name = item.get("name") or item.get("fieldName") or item.get("column")
        if not name:
            continue
        stats = item.get("profile") if isinstance(item.get("profile"), dict) else item
        null_ratio = _safe_ratio(
            _first(stats, ("nullRatio", "null_ratio", "ratioNull"))
        )
        distinct_ratio = _safe_ratio(
            _first(stats, ("distinctRatio", "distinct_ratio", "uniqueRatio"))
        )
        # Only structural ratios are read; value-bearing keys are never touched.
        if null_ratio is None and distinct_ratio is None:
            continue
        signals[str(name)] = (null_ratio, distinct_ratio)
    return signals


def _find_field_list(data: dict[str, Any]) -> list[Any]:
    if not isinstance(data, dict):
        return []
    for key in ("fields", "columns"):
        value = data.get(key)
        if isinstance(value, list):
            return value
    profile = data.get("profile")
    if isinstance(profile, dict):
        for key in ("fields", "columns"):
            value = profile.get(key)
            if isinstance(value, list):
                return value
    return []


def _first(stats: Any, keys: tuple[str, ...]) -> Any:
    if not isinstance(stats, dict):
        return None
    for key in keys:
        if key in stats:
            return stats[key]
    return None


def _safe_ratio(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number < 0.0:
        number = 0.0
    elif number > 1.0:
        number = 1.0
    return round(number, _RATIO_PRECISION)


def _is_candidate_key(null_ratio: float | None, distinct_ratio: float | None) -> bool:
    return (
        distinct_ratio is not None
        and distinct_ratio >= _CANDIDATE_KEY_DISTINCT_MIN
        and null_ratio is not None
        and null_ratio <= _CANDIDATE_KEY_NULL_MAX
    )


def _apply_field_signals(
    field_: CatalogField,
    signal: tuple[float | None, float | None] | None,
) -> CatalogField:
    if signal is None:
        return field_
    null_ratio, distinct_ratio = signal
    return replace(
        field_,
        null_ratio=null_ratio,
        distinct_ratio=distinct_ratio,
        is_candidate_key=_is_candidate_key(null_ratio, distinct_ratio),
    )


def _tokenize(question: str) -> frozenset[str]:
    tokens = re.split(r"[^a-z0-9]+", question.lower())
    return frozenset(
        token for token in tokens if len(token) >= _MIN_SEARCH_TOKEN_LENGTH
    )


def _name_match_score(qualified_name: str, tokens: frozenset[str]) -> int:
    _, _, table_part = qualified_name.partition(".")
    name_tokens = frozenset(
        part for part in re.split(r"[^a-z0-9]+", table_part.lower()) if part
    )
    return len(name_tokens & tokens)


def _split_csv(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [value.strip() for value in raw.split(",") if value.strip()]


def _bound_text(value: str) -> str:
    text = " ".join(value.split())
    if len(text) > _MAX_TEXT_CHARS:
        return text[:_MAX_TEXT_CHARS]
    return text
