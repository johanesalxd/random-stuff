"""Domain-neutral ADK nodes for Knowledge Catalog grounding (Phase 7).

These nodes consume the Phase 6 semantic handoff, ground it against current
catalog metadata through an injectable adapter, assess context sufficiency with
deterministic rules, and hand off to guarded SQL generation or to clarification.
No node in this module generates or executes SQL.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from google.adk.agents.context import Context
from google.adk.events.event import Event
from google.adk.workflow import node

from semantic.catalog import (
    CatalogAccessError,
    CatalogAdapter,
    TableMetadata,
    bound_table_results,
    build_catalog_adapter,
    is_source_in_scope,
    parse_allowed_datasets,
    parse_allowed_projects,
    parse_catalog_source,
    resolve_narrow_sources,
)

_MAX_ERROR_CHARS = 500


def load_narrow_catalog_context(node_input: dict[str, Any]) -> Event:
    """Grounds the narrow path against exactly the selected semantic sources.

    Args:
        node_input: The Phase 6 ``semantic_narrow`` handoff payload.

    Returns:
        Event carrying the handoff plus bounded narrow catalog context.
    """
    return Event(output=ground_narrow(node_input, build_catalog_adapter()))


@node
async def assess_context(ctx: Context, node_input: dict[str, Any]) -> Event:
    """Assesses narrow-context sufficiency and routes narrow or broad.

    Args:
        ctx: Current ADK workflow context.
        node_input: Narrow grounding payload.

    Returns:
        Routed event: ``sufficient`` for handoff, ``insufficient`` for broadening.
    """
    output, route = assess_narrow(node_input)
    return Event(output=output, route=route)


def load_broad_catalog_context(node_input: dict[str, Any]) -> Event:
    """Grounds the broad path within configured project and dataset allowlists.

    Args:
        node_input: The semantic handoff or an insufficient narrow payload.

    Returns:
        Event carrying the handoff plus bounded broad catalog context.
    """
    return Event(
        output=ground_broad(
            node_input,
            build_catalog_adapter(),
            allowed_projects=parse_allowed_projects(),
            allowed_datasets=parse_allowed_datasets(),
        )
    )


@node
async def assess_broad_context(ctx: Context, node_input: dict[str, Any]) -> Event:
    """Assesses broad-context sufficiency and routes to handoff or clarification.

    Args:
        ctx: Current ADK workflow context.
        node_input: Broad grounding payload.

    Returns:
        Routed event: ``grounded`` for handoff, ``clarify`` otherwise.
    """
    output, route = assess_broad(node_input)
    return Event(output=output, route=route)


def finish_catalog_grounding(node_input: dict[str, Any]) -> dict[str, Any]:
    """Returns grounded context at the guarded SQL-generation boundary."""
    payload = dict(node_input)
    payload["status"] = "catalog_context_grounded"
    payload["next_step"] = "guarded_sql_generation"
    return payload


def finish_clarification(node_input: dict[str, Any]) -> dict[str, Any]:
    """Returns a clarification handoff when no grounded context is available."""
    payload = dict(node_input)
    payload["status"] = "catalog_context_insufficient"
    payload["next_step"] = "clarify_or_refuse"
    return payload


def ground_narrow(
    handoff: dict[str, Any],
    adapter: CatalogAdapter,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Fetches bounded metadata for exactly the selected narrow sources.

    Args:
        handoff: Phase 6 narrow handoff payload.
        adapter: Injected catalog adapter.
        now: Injected timestamp for deterministic tests.

    Returns:
        The handoff augmented with narrow catalog context and any access error.
    """
    payload = dict(handoff)
    requested = list(handoff.get("semantic_source_names", []))
    payload["catalog_route"] = "narrow"
    try:
        sources = resolve_narrow_sources(requested)
        metadata = adapter.fetch_table_metadata(sources)
    except CatalogAccessError as error:
        payload["catalog_context"] = []
        payload["catalog_permitted_sources"] = requested
        payload["catalog_missing_sources"] = requested
        payload["catalog_error"] = str(error)[:_MAX_ERROR_CHARS]
        return payload

    # Defense in depth: never surface metadata outside the exact requested set.
    permitted = {source.qualified_name for source in sources}
    in_scope = [item for item in metadata if item.source in permitted]
    resolved = {item.source for item in in_scope if item.fields}
    payload["catalog_context"] = [item.to_context() for item in in_scope]
    payload["catalog_permitted_sources"] = sorted(permitted)
    payload["catalog_missing_sources"] = sorted(permitted - resolved)
    return payload


def assess_narrow(grounding: dict[str, Any]) -> tuple[dict[str, Any], str]:
    """Applies deterministic narrow-sufficiency rules and selects a route.

    Args:
        grounding: Narrow grounding payload.

    Returns:
        The payload with a sufficiency report and the ``sufficient`` or
        ``insufficient`` route.
    """
    permitted = list(grounding.get("catalog_permitted_sources", []))
    missing = list(grounding.get("catalog_missing_sources", []))
    has_context = bool(grounding.get("catalog_context"))
    sufficient = has_context and not missing and bool(permitted)
    route = "sufficient" if sufficient else "insufficient"
    payload = dict(grounding)
    payload["context_sufficiency"] = _sufficiency_report(
        route="narrow",
        sufficient=sufficient,
        permitted_sources=permitted,
        missing_metadata=missing,
        resolved_terms=list(grounding.get("semantic_context_ids", [])),
        unresolved_terms=[] if sufficient else ["narrow_metadata_incomplete"],
        preserved_question=grounding.get("question", ""),
    )
    return payload, route


def ground_broad(
    handoff: dict[str, Any],
    adapter: CatalogAdapter,
    *,
    allowed_projects: frozenset[str],
    allowed_datasets: frozenset[str],
    now: datetime | None = None,
) -> dict[str, Any]:
    """Searches configured project and dataset allowlists for candidate sources.

    Args:
        handoff: The semantic handoff or an insufficient narrow payload.
        adapter: Injected catalog adapter.
        allowed_projects: Permitted project IDs.
        allowed_datasets: Permitted ``project.dataset`` IDs.
        now: Injected timestamp for deterministic tests.

    Returns:
        The handoff augmented with in-scope broad catalog context. Absent or
        invalid allowlists fail closed with an empty result.
    """
    payload = dict(handoff)
    payload["catalog_route"] = "broad"
    payload["catalog_allowed_projects"] = sorted(allowed_projects)
    payload["catalog_allowed_datasets"] = sorted(allowed_datasets)
    if not allowed_projects and not allowed_datasets:
        payload["catalog_context"] = []
        payload["catalog_error"] = (
            "broad search allowlists are unconfigured; failing closed"
        )
        return payload
    try:
        results = adapter.search_tables(
            question=str(handoff.get("question", "")),
            allowed_projects=allowed_projects,
            allowed_datasets=allowed_datasets,
        )
    except CatalogAccessError as error:
        payload["catalog_context"] = []
        payload["catalog_error"] = str(error)[:_MAX_ERROR_CHARS]
        return payload

    in_scope: list[TableMetadata] = []
    for item in results:
        try:
            source = parse_catalog_source(item.source)
        except CatalogAccessError:
            continue
        if is_source_in_scope(
            source,
            allowed_projects=allowed_projects,
            allowed_datasets=allowed_datasets,
        ):
            in_scope.append(item)
    bounded = bound_table_results(in_scope)
    payload["catalog_context"] = [item.to_context() for item in bounded]
    payload["catalog_discovered_sources"] = sorted(item.source for item in bounded)
    payload["catalog_discovery_backend"] = getattr(
        adapter, "last_search_backend", None
    ) or getattr(adapter, "discovery_backend", "name_match")
    return payload


def assess_broad(grounding: dict[str, Any]) -> tuple[dict[str, Any], str]:
    """Applies deterministic broad-sufficiency rules and selects a route.

    Args:
        grounding: Broad grounding payload.

    Returns:
        The payload with a sufficiency report and the ``grounded`` or ``clarify``
        route.
    """
    discovered = list(grounding.get("catalog_discovered_sources", []))
    has_context = bool(grounding.get("catalog_context"))
    sufficient = has_context and bool(discovered)
    route = "grounded" if sufficient else "clarify"
    payload = dict(grounding)
    payload["context_sufficiency"] = _sufficiency_report(
        route="broad",
        sufficient=sufficient,
        permitted_sources=discovered,
        missing_metadata=[] if sufficient else ["no_in_scope_sources"],
        resolved_terms=list(grounding.get("semantic_context_ids", [])),
        unresolved_terms=[] if sufficient else ["broad_discovery_empty"],
        preserved_question=grounding.get("question", ""),
    )
    return payload, route


def _sufficiency_report(
    *,
    route: str,
    sufficient: bool,
    permitted_sources: list[str],
    missing_metadata: list[str],
    resolved_terms: list[str],
    unresolved_terms: list[str],
    preserved_question: str,
) -> dict[str, Any]:
    return {
        "route": route,
        "sufficient": sufficient,
        "permitted_sources": permitted_sources,
        "missing_metadata": missing_metadata,
        "resolved_terms": resolved_terms,
        "unresolved_terms": unresolved_terms,
        "preserved_question": preserved_question,
    }
