"""Builds compact, prompt-safe context from semantic contracts."""

from __future__ import annotations

from collections import deque
from typing import Any

from semantic.types import Dimension, Join, Metric, SemanticContract, Table


class SemanticContextError(ValueError):
    """Raised when selected concepts cannot form connected semantic context."""


def build_semantic_context(contract: SemanticContract) -> dict[str, Any]:
    """Builds deterministic model context for one semantic domain.

    Args:
        contract: Validated semantic contract to serialize.

    Returns:
        JSON-safe context containing business semantics and physical sources.
    """
    return {
        "id": contract.id,
        "version": contract.version,
        "owner": contract.owner,
        "description": contract.description,
        "routing_terms": list(contract.routing_terms),
        "examples": list(contract.examples),
        "tables": [_table_context(table) for table in _sorted(contract.tables)],
        "relationships": [
            _relationship_context(join) for join in _sorted(contract.joins)
        ],
        "dimensions": [
            _dimension_context(dimension) for dimension in _sorted(contract.dimensions)
        ],
        "metrics": [_metric_context(metric) for metric in _sorted(contract.metrics)],
    }


def build_selected_semantic_context(
    contract: SemanticContract,
    *,
    metric_names: tuple[str, ...],
    dimension_names: tuple[str, ...],
    relationship_names: tuple[str, ...],
) -> dict[str, Any]:
    """Builds context and physical sources for selected semantic concepts.

    Args:
        contract: Validated semantic contract.
        metric_names: Selected metric IDs from the contract.
        dimension_names: Selected dimension IDs from the contract.
        relationship_names: Selected relationship IDs from the contract.

    Returns:
        Filtered semantic context with the required physical source closure.
    """
    metrics = [contract.metrics[name] for name in metric_names]
    selected_dimension_names = set(dimension_names)
    for metric in metrics:
        selected_dimension_names.update(metric.required_dimensions)

    dimensions = [
        contract.dimensions[name] for name in sorted(selected_dimension_names)
    ]
    table_names = {metric.base_table for metric in metrics}
    table_names.update(dimension.table for dimension in dimensions)
    declared_metric_relationships = set()
    for metric in metrics:
        declared_metric_relationships.update(metric.join_path)
    if metrics:
        unsupported_relationships = sorted(
            set(relationship_names) - declared_metric_relationships
        )
        if unsupported_relationships:
            raise SemanticContextError(
                "selected relationships are outside the selected metric paths: "
                f"{unsupported_relationships}"
            )
        available_relationship_names = declared_metric_relationships
    else:
        available_relationship_names = set(contract.joins)
    selected_relationship_names = _resolve_relationship_closure(
        contract,
        table_names,
        set(relationship_names),
        available_relationship_names=(
            available_relationship_names if metrics else set(contract.joins)
        ),
    )
    relationships = [contract.joins[name] for name in selected_relationship_names]
    for relationship in relationships:
        table_names.update((relationship.left, relationship.right))

    injected_dimensions = sorted(selected_dimension_names - set(dimension_names))
    injected_relationships = sorted(
        set(selected_relationship_names) - set(relationship_names)
    )

    return {
        "id": contract.id,
        "version": contract.version,
        "owner": contract.owner,
        "description": contract.description,
        "tables": [
            _table_context(contract.tables[name]) for name in sorted(table_names)
        ],
        "relationships": [
            _relationship_context(relationship) for relationship in relationships
        ],
        "dimensions": [_dimension_context(dimension) for dimension in dimensions],
        "metrics": [
            _metric_context(
                metric,
                relationship_names=set(selected_relationship_names),
            )
            for metric in metrics
        ],
        "selection": {
            "metric_ids": list(metric_names),
            "dimension_ids": list(dimension_names),
            "relationship_ids": list(relationship_names),
        },
        "resolution": {
            "injected_dimension_ids": injected_dimensions,
            "injected_relationship_ids": injected_relationships,
        },
    }


def build_semantic_index_entry(contract: SemanticContract) -> dict[str, Any]:
    """Builds compact routing context without physical source expressions.

    Args:
        contract: Validated semantic contract to summarize.

    Returns:
        JSON-safe context used only to select relevant semantic domains.
    """
    return {
        "id": contract.id,
        "version": contract.version,
        "description": contract.description,
        "routing_terms": list(contract.routing_terms),
        "examples": list(contract.examples),
        "relationships": [
            {
                "name": join.name,
                "left": join.left,
                "right": join.right,
                "relationship": join.relationship,
            }
            for join in sorted(contract.joins.values(), key=lambda item: item.name)
        ],
        "dimensions": [
            {
                "name": dimension.name,
                "label": dimension.label,
                "description": dimension.description,
                "synonyms": list(dimension.synonyms),
            }
            for dimension in sorted(
                contract.dimensions.values(), key=lambda item: item.name
            )
        ],
        "metrics": [
            {
                "name": metric.name,
                "label": metric.label,
                "description": metric.description,
                "synonyms": list(metric.synonyms),
            }
            for metric in sorted(contract.metrics.values(), key=lambda item: item.name)
        ],
    }


def _table_context(table: Table) -> dict[str, Any]:
    return {
        "name": table.name,
        "source": table.source.qualified_name,
        "grain": table.grain,
        "primary_key": table.primary_key,
        "foreign_keys": dict(sorted(table.foreign_keys.items())),
    }


def _relationship_context(join: Join) -> dict[str, str]:
    return {
        "name": join.name,
        "left": join.left,
        "right": join.right,
        "condition": join.on,
        "relationship": join.relationship,
    }


def _dimension_context(dimension: Dimension) -> dict[str, Any]:
    return {
        "name": dimension.name,
        "label": dimension.label,
        "description": dimension.description,
        "table": dimension.table,
        "expression": dimension.sql,
        "synonyms": list(dimension.synonyms),
    }


def _metric_context(
    metric: Metric,
    *,
    relationship_names: set[str] | None = None,
) -> dict[str, Any]:
    relationship_path = metric.join_path
    if relationship_names is not None:
        relationship_path = tuple(
            name for name in metric.join_path if name in relationship_names
        )
    return {
        "name": metric.name,
        "label": metric.label,
        "description": metric.description,
        "synonyms": list(metric.synonyms),
        "base_table": metric.base_table,
        "aggregation_type": metric.type,
        "expression": metric.sql,
        "numerator_expression": metric.numerator_sql,
        "denominator_expression": metric.denominator_sql,
        "required_filters": list(metric.required_filters),
        "required_dimensions": list(metric.required_dimensions),
        "known_dimensions": list(metric.allowed_dimensions),
        "known_filters": {
            dimension: list(operators)
            for dimension, operators in sorted(metric.allowed_filters.items())
        },
        "relationship_path": list(relationship_path),
        "default_order_by": metric.default_order_by,
        "default_limit": metric.default_limit,
    }


def _sorted(items: dict[str, Any]) -> list[Any]:
    return sorted(items.values(), key=lambda item: item.name)


def _resolve_relationship_closure(
    contract: SemanticContract,
    required_tables: set[str],
    explicit_relationships: set[str],
    available_relationship_names: set[str],
) -> tuple[str, ...]:
    selected_relationships = set(explicit_relationships)
    for relationship_name in explicit_relationships:
        relationship = contract.joins[relationship_name]
        required_tables.update((relationship.left, relationship.right))
    if not required_tables:
        return tuple(sorted(selected_relationships))

    anchor = min(required_tables)
    connected = _connected_tables(contract, anchor, selected_relationships)
    while not required_tables.issubset(connected):
        paths = []
        for target in sorted(required_tables - connected):
            path = _shortest_relationship_path(
                contract,
                connected,
                target,
                available_relationship_names,
            )
            if path is not None:
                paths.append(path)
        if not paths:
            missing = sorted(required_tables - connected)
            raise SemanticContextError(
                f"selected concepts have disconnected tables: {missing}"
            )
        selected_relationships.update(min(paths, key=lambda path: (len(path), path)))
        connected = _connected_tables(contract, anchor, selected_relationships)
    return tuple(sorted(selected_relationships))


def _connected_tables(
    contract: SemanticContract,
    anchor: str,
    relationship_names: set[str],
) -> set[str]:
    connected = {anchor}
    changed = True
    while changed:
        changed = False
        for name in sorted(relationship_names):
            relationship = contract.joins[name]
            if relationship.left in connected and relationship.right not in connected:
                connected.add(relationship.right)
                changed = True
            elif relationship.right in connected and relationship.left not in connected:
                connected.add(relationship.left)
                changed = True
    return connected


def _shortest_relationship_path(
    contract: SemanticContract,
    source_tables: set[str],
    target_table: str,
    available_relationship_names: set[str],
) -> tuple[str, ...] | None:
    queue = deque((table, ()) for table in sorted(source_tables))
    visited = set(source_tables)
    while queue:
        table, path = queue.popleft()
        for relationship in sorted(contract.joins.values(), key=lambda item: item.name):
            if relationship.name not in available_relationship_names:
                continue
            if relationship.left == table:
                neighbor = relationship.right
            elif relationship.right == table:
                neighbor = relationship.left
            else:
                continue
            next_path = (*path, relationship.name)
            if neighbor == target_table:
                return next_path
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append((neighbor, next_path))
    return None
