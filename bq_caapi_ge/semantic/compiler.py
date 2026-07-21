"""Deterministic SQL compiler for certified semantic intents."""

from __future__ import annotations

import re

from semantic.types import (
    CompileError,
    CompiledQuery,
    Dimension,
    IntentFilter,
    Metric,
    QueryIntent,
    QueryParameter,
    SemanticContract,
)


_IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def compile_query(contract: SemanticContract, intent: QueryIntent) -> CompiledQuery:
    """Compiles a validated intent to deterministic BigQuery SQL.

    Args:
        contract: Semantic contract that owns metrics and joins.
        intent: Structured intent selected upstream.

    Returns:
        Compiled SQL and BigQuery query parameters.

    Raises:
        CompileError: If the intent is outside the contract coverage.
    """
    metric = _get_metric(contract, intent.metric)
    filters = _validate_filters(metric, intent.filters)
    filter_dimensions = tuple(intent_filter.dimension for intent_filter in filters)
    dimensions = _validate_dimensions(
        contract,
        metric,
        tuple(dict.fromkeys(intent.dimensions + filter_dimensions)),
    )

    selected_dimensions = tuple(
        dict.fromkeys(metric.required_dimensions + intent.dimensions)
    )
    dimension_selects = [
        f"  {contract.dimensions[name].sql} AS {name}," for name in selected_dimensions
    ]
    metric_expression = _metric_expression(metric)
    select_lines = [*dimension_selects, f"  {metric_expression} AS {metric.name}"]
    from_lines = _from_and_join_lines(contract, metric, dimensions)
    where_lines, parameters = _where_lines(metric, filters, contract)
    group_by_lines = _group_by_lines(selected_dimensions)
    order_by_lines = _order_by_lines(metric, selected_dimensions)
    limit_lines = _limit_lines(metric, intent.limit)

    sql = "\n".join(
        [
            "SELECT",
            *select_lines,
            *from_lines,
            *where_lines,
            *group_by_lines,
            *order_by_lines,
            *limit_lines,
        ]
    )
    return CompiledQuery(
        sql=sql,
        parameters=tuple(parameters),
        metric=metric.name,
        dimensions=selected_dimensions,
        contract_version=contract.contract_version,
        certified=contract.certified,
    )


def _get_metric(contract: SemanticContract, metric_name: str) -> Metric:
    metric = contract.metrics.get(metric_name)
    if metric is None:
        raise CompileError(f"unsupported metric: {metric_name}")
    return metric


def _validate_dimensions(
    contract: SemanticContract,
    metric: Metric,
    dimension_names: tuple[str, ...],
) -> dict[str, Dimension]:
    allowed_dimensions = set(metric.allowed_dimensions)
    requested_dimensions = tuple(
        dict.fromkeys(metric.required_dimensions + dimension_names)
    )
    dimensions = {}
    for dimension_name in requested_dimensions:
        if dimension_name not in allowed_dimensions:
            raise CompileError(
                f"dimension {dimension_name} is not allowed for metric {metric.name}"
            )
        dimension = contract.dimensions.get(dimension_name)
        if dimension is None:
            raise CompileError(f"unknown dimension: {dimension_name}")
        if not _is_table_reachable(contract, metric, dimension.table):
            raise CompileError(
                f"dimension {dimension_name} is not reachable from metric {metric.name}"
            )
        dimensions[dimension_name] = dimension
    return dimensions


def _validate_filters(
    metric: Metric,
    filters: tuple[IntentFilter, ...],
) -> tuple[IntentFilter, ...]:
    for intent_filter in filters:
        allowed_operators = metric.allowed_filters.get(intent_filter.dimension)
        if allowed_operators is None:
            raise CompileError(
                f"filter {intent_filter.dimension} is not allowed for metric {metric.name}"
            )
        if intent_filter.operator not in allowed_operators:
            raise CompileError(
                f"operator {intent_filter.operator} is not allowed for filter "
                f"{intent_filter.dimension}"
            )
        if intent_filter.operator == "IN" and not isinstance(intent_filter.value, list):
            raise CompileError(
                f"filter {intent_filter.dimension} requires a list value"
            )
        if intent_filter.operator == "=" and isinstance(intent_filter.value, list):
            raise CompileError(
                f"filter {intent_filter.dimension} requires a scalar value"
            )
    return filters


def _metric_expression(metric: Metric) -> str:
    if metric.type == "count_distinct":
        return f"COUNT(DISTINCT {metric.sql})"
    if metric.type == "sum":
        return f"SUM({metric.sql})"
    if metric.type == "ratio":
        return f"SAFE_DIVIDE({metric.numerator_sql}, {metric.denominator_sql})"
    raise CompileError(f"unsupported metric type: {metric.type}")


def _from_and_join_lines(
    contract: SemanticContract,
    metric: Metric,
    dimensions: dict[str, Dimension],
) -> list[str]:
    required_tables = {metric.base_table}
    required_tables.update(dimension.table for dimension in dimensions.values())

    lines = [f"FROM `{contract.dataset}.{metric.base_table}` AS {metric.base_table}"]
    joined_tables = {metric.base_table}
    for join_name in metric.join_path:
        join = contract.joins[join_name]
        if join.left in joined_tables and join.right not in joined_tables:
            lines.append(f"LEFT JOIN `{contract.dataset}.{join.right}` AS {join.right}")
            lines.append(f"  ON {join.on}")
            joined_tables.add(join.right)
        elif join.right in joined_tables and join.left not in joined_tables:
            lines.append(f"LEFT JOIN `{contract.dataset}.{join.left}` AS {join.left}")
            lines.append(f"  ON {join.on}")
            joined_tables.add(join.left)
        if required_tables.issubset(joined_tables):
            break

    missing_tables = required_tables - joined_tables
    if missing_tables:
        raise CompileError(f"missing join path for tables: {sorted(missing_tables)}")
    return lines


def _where_lines(
    metric: Metric,
    filters: tuple[IntentFilter, ...],
    contract: SemanticContract,
) -> tuple[list[str], list[QueryParameter]]:
    predicates = list(metric.required_filters)
    parameters = []
    for index, intent_filter in enumerate(filters, start=1):
        dimension = contract.dimensions[intent_filter.dimension]
        parameter_name = f"p{index}_{intent_filter.dimension}"
        _validate_parameter_name(parameter_name)
        if intent_filter.operator == "IN":
            predicates.append(f"{dimension.sql} IN UNNEST(@{parameter_name})")
        else:
            predicates.append(
                f"{dimension.sql} {intent_filter.operator} @{parameter_name}"
            )
        parameters.append(
            QueryParameter(name=parameter_name, value=intent_filter.value)
        )

    if not predicates:
        return [], parameters

    return [
        "WHERE",
        *[f"  {predicate}" for predicate in _and_join(predicates)],
    ], parameters


def _and_join(predicates: list[str]) -> list[str]:
    lines = []
    for index, predicate in enumerate(predicates):
        prefix = "" if index == 0 else "AND "
        lines.append(f"{prefix}{predicate}")
    return lines


def _group_by_lines(dimensions: tuple[str, ...]) -> list[str]:
    if not dimensions:
        return []
    ordinals = ", ".join(str(index) for index in range(1, len(dimensions) + 1))
    return [f"GROUP BY {ordinals}"]


def _order_by_lines(metric: Metric, dimensions: tuple[str, ...]) -> list[str]:
    if metric.default_order_by == "metric_desc":
        return [f"ORDER BY {metric.name} DESC"]
    if dimensions:
        return ["ORDER BY " + ", ".join(dimensions)]
    return []


def _limit_lines(metric: Metric, intent_limit: int | None) -> list[str]:
    limit = intent_limit if intent_limit is not None else metric.default_limit
    if limit is None:
        return []
    if limit <= 0:
        raise CompileError("limit must be positive")
    return [f"LIMIT {limit}"]


def _is_table_reachable(
    contract: SemanticContract,
    metric: Metric,
    table_name: str,
) -> bool:
    if table_name == metric.base_table:
        return True

    reachable_tables = {metric.base_table}
    changed = True
    while changed:
        changed = False
        for join_name in metric.join_path:
            join = contract.joins[join_name]
            if join.left in reachable_tables and join.right not in reachable_tables:
                reachable_tables.add(join.right)
                changed = True
            if join.right in reachable_tables and join.left not in reachable_tables:
                reachable_tables.add(join.left)
                changed = True
    return table_name in reachable_tables


def _validate_parameter_name(name: str) -> None:
    if not _IDENTIFIER_PATTERN.match(name):
        raise CompileError(f"invalid parameter name: {name}")
