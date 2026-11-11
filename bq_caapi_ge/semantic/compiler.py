"""Tier-1 Deterministic Intent-to-SQL Compiler for Semantic Contracts.

Translates high-level metric selections, groupings, and filters into standard GoogleSQL
queries with join fan-out protection and strict literal escaping.
Zero external dependencies (stdlib + semantic.types and semantic.sql_lex only).
"""

from __future__ import annotations

from collections import deque
from collections.abc import Sequence
from dataclasses import dataclass
import math
import re

from semantic.sql_lex import (
    extract_qualified_columns,
    format_googlesql_string_literal,
    parse_single_aggregate,
)
from semantic.types import Join, SemanticContract


class CoverageError(ValueError):
    """Raised when an analytical intent cannot be safely compiled under the contract."""


@dataclass(frozen=True)
class FilterClause:
    """Declared filter predicate on a semantic dimension."""

    dimension_id: str
    op: str = "="
    values: tuple[str | int | float, ...] = ()


@dataclass(frozen=True)
class CompiledMetricQuery:
    """Result of deterministic contract compilation."""

    sql: str
    contract_id: str
    metric_id: str
    metric_type: str
    group_by_dimensions: tuple[str, ...]
    filter_dimensions: tuple[str, ...]
    referenced_sources: tuple[str, ...]
    effective_limit: int | None


_ALLOWED_OPERATORS = frozenset({"=", "!=", "IN", ">", ">=", "<", "<="})
_REQ_FILTER_EQ_RE = re.compile(
    r"^\s*([A-Za-z_][A-Za-z0-9_]*\.[A-Za-z_][A-Za-z0-9_]*)\s*=\s*'([^']*)'\s*$"
)


def _format_literal(val: str | int | float) -> str:
    if isinstance(val, bool):
        raise CoverageError("Boolean literals are not supported in filter clauses")
    if val is None:
        raise CoverageError("None literal is not supported in filter clauses")
    if isinstance(val, float):
        if math.isnan(val) or math.isinf(val):
            raise CoverageError("NaN or Infinity floats are not supported in filter clauses")
        return repr(val)
    if isinstance(val, int):
        if not (-2**63 <= val <= 2**63 - 1):
            raise CoverageError("Integer literal outside 64-bit signed integer range")
        return str(val)
    if isinstance(val, str):
        return format_googlesql_string_literal(val)
    raise CoverageError(f"Unsupported filter literal type: {type(val).__name__}")


def _normalize_operator(op: str) -> str:
    cleaned = op.strip()
    return {"==": "=", "<>": "!="}.get(cleaned, cleaned)


def compile_metric_query(
    contract: SemanticContract,
    *,
    metric_id: str,
    group_by_dimension_ids: Sequence[str] = (),
    filters: Sequence[FilterClause] = (),
    limit: int | None = None,
    max_limit: int = 1000,
) -> CompiledMetricQuery:
    """Compiles a metric query into deterministic GoogleSQL.

    Validates dimensions, allowed filters, value literals, and resolves joins strictly
    along metric.join_path while enforcing fan-out and ratio-denominator protection.
    """
    if metric_id not in contract.metrics:
        raise CoverageError(f"Metric '{metric_id}' not found in contract '{contract.id}'")

    metric = contract.metrics[metric_id]

    # Validate group-by dimensions
    for d in group_by_dimension_ids:
        if d not in contract.dimensions:
            raise CoverageError(f"Dimension '{d}' not found in contract '{contract.id}'")
        if d not in metric.allowed_dimensions:
            raise CoverageError(f"Dimension '{d}' is not in allowed_dimensions for metric '{metric_id}'")

    # Order group-by dimensions: metric.required_dimensions first, then remaining, preserving order
    final_group_by: list[str] = list(metric.required_dimensions)
    for d in group_by_dimension_ids:
        if d not in final_group_by:
            final_group_by.append(d)

    # Validate filter clauses
    required_equalities: dict[str, str] = {}
    for rf in metric.required_filters:
        m = _REQ_FILTER_EQ_RE.match(rf)
        if m:
            required_equalities[m.group(1)] = m.group(2)

    validated_filters: list[FilterClause] = []
    filter_dims: list[str] = []
    for f in filters:
        if f.dimension_id not in contract.dimensions:
            raise CoverageError(f"Filter dimension '{f.dimension_id}' not found in contract '{contract.id}'")
        if f.dimension_id not in metric.allowed_filters:
            raise CoverageError(
                f"Dimension '{f.dimension_id}' is not in allowed_filters for metric '{metric_id}'"
            )

        norm_op = _normalize_operator(f.op)
        if norm_op not in _ALLOWED_OPERATORS:
            raise CoverageError(f"Unsupported filter operator '{f.op}'")

        allowed_ops_for_dim = metric.allowed_filters[f.dimension_id]
        if norm_op not in allowed_ops_for_dim:
            raise CoverageError(
                f"Operator '{norm_op}' is not allowed for dimension '{f.dimension_id}' in metric '{metric_id}'"
            )

        if norm_op == "IN":
            if not (1 <= len(f.values) <= 100):
                raise CoverageError(f"IN filter clause requires between 1 and 100 values, got {len(f.values)}")
        else:
            if len(f.values) != 1:
                raise CoverageError(f"Scalar filter operator '{norm_op}' requires exactly 1 value, got {len(f.values)}")

        # Validate literal values
        for v in f.values:
            _format_literal(v)

        dim_sql = contract.dimensions[f.dimension_id].sql.strip()
        if dim_sql in required_equalities:
            req_val = required_equalities[dim_sql]
            if norm_op == "=" and str(f.values[0]) != req_val:
                raise CoverageError(
                    f"Filter on '{f.dimension_id}' ('{f.values[0]}') contradicts required filter {dim_sql} = '{req_val}'"
                )
            if norm_op == "!=" and str(f.values[0]) == req_val:
                raise CoverageError(
                    f"Filter on '{f.dimension_id}' (!= '{f.values[0]}') contradicts required filter {dim_sql} = '{req_val}'"
                )
            if norm_op == "IN" and req_val not in {str(v) for v in f.values}:
                raise CoverageError(
                    f"Filter on '{f.dimension_id}' IN ({f.values}) excludes required filter value '{req_val}'"
                )

        validated_filters.append(FilterClause(dimension_id=f.dimension_id, op=norm_op, values=tuple(f.values)))
        filter_dims.append(f.dimension_id)

    # Validate limit
    if limit is not None:
        if isinstance(limit, bool) or not isinstance(limit, int):
            raise CoverageError(f"limit must be an integer, got {type(limit).__name__}")
        if not (1 <= limit <= max_limit):
            raise CoverageError(f"limit must be between 1 and {max_limit}, got {limit}")
        effective_limit = limit
    else:
        effective_limit = metric.default_limit

    # Collect required table aliases
    required_tables: set[str] = {metric.base_table}
    for d in final_group_by:
        required_tables.add(contract.dimensions[d].table)
    for f in validated_filters:
        required_tables.add(contract.dimensions[f.dimension_id].table)

    # Extract tables referenced in metric formulas and required_filters
    formula_texts = [
        metric.sql,
        metric.numerator_sql,
        metric.denominator_sql,
    ] + list(metric.required_filters)

    for text in formula_texts:
        if not text:
            continue
        for qual, _ in extract_qualified_columns(text):
            if qual in contract.tables:
                required_tables.add(qual)
            else:
                raise CoverageError(f"Unknown table qualifier '{qual}' in metric definition or filter")

    # Resolve join sequence from base_table along metric.join_path
    allowed_joins: dict[str, Join] = {}
    for j_name in metric.join_path:
        if j_name not in contract.joins:
            raise CoverageError(f"Join '{j_name}' declared in join_path not found in contract '{contract.id}'")
        allowed_joins[j_name] = contract.joins[j_name]

    # Find shortest paths from base_table to each required table using BFS
    # Graph adjacency: table -> list of (neighbor_table, join_name)
    adj: dict[str, list[tuple[str, str]]] = {}
    for j_name, j in allowed_joins.items():
        adj.setdefault(j.left, []).append((j.right, j_name))
        adj.setdefault(j.right, []).append((j.left, j_name))

    needed_join_names: set[str] = set()
    for target in required_tables:
        if target == metric.base_table:
            continue
        # BFS from base_table to target
        queue: deque[tuple[str, list[str]]] = deque([(metric.base_table, [])])
        visited: set[str] = {metric.base_table}
        found_path: list[str] | None = None
        while queue:
            curr, path = queue.popleft()
            if curr == target:
                found_path = path
                break
            for neighbor, j_name in adj.get(curr, []):
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((neighbor, path + [j_name]))

        if found_path is None:
            raise CoverageError(
                f"Cannot reach required table '{target}' from base table '{metric.base_table}' "
                f"using join_path {metric.join_path}"
            )
        needed_join_names.update(found_path)

    # Order the needed joins such that every step connects an already-bound table to a new table
    bound_tables: set[str] = {metric.base_table}
    ordered_bound_tables: list[str] = [metric.base_table]
    ordered_joins: list[tuple[Join, str, str]] = []  # (join, already_bound, next_table)

    remaining_joins = set(needed_join_names)
    while remaining_joins:
        # Pick the first join in metric.join_path order that connects bound to unbound
        candidate: tuple[Join, str, str] | None = None
        for j_name in metric.join_path:
            if j_name not in remaining_joins:
                continue
            j = allowed_joins[j_name]
            if j.left in bound_tables and j.right not in bound_tables:
                candidate = (j, j.left, j.right)
                remaining_joins.remove(j_name)
                break
            if j.right in bound_tables and j.left not in bound_tables:
                candidate = (j, j.right, j.left)
                remaining_joins.remove(j_name)
                break

        if candidate is None:
            raise CoverageError("Disjoint or cyclic join structure in join_path")

        j_cand, already_bound, next_table = candidate
        bound_tables.add(next_table)
        ordered_bound_tables.append(next_table)
        ordered_joins.append((j_cand, already_bound, next_table))

    # Cardinality tracking and fan-out guard
    tables_via_fanout: set[str] = set()
    join_clauses: list[str] = []

    for j, already_bound, next_table in ordered_joins:
        # Determine step cardinality
        if j.relationship == "one_to_one":
            is_fanout = False
        elif (already_bound == j.left and j.relationship == "many_to_one") or (
            already_bound == j.right and j.relationship == "one_to_many"
        ):
            is_fanout = False
        else:
            is_fanout = True

        if already_bound in tables_via_fanout or is_fanout:
            tables_via_fanout.add(next_table)
            join_type = "LEFT JOIN"
        else:
            join_type = "INNER JOIN"

        next_t = contract.tables[next_table]
        join_clauses.append(
            f"{join_type} `{next_t.source.project}.{next_t.source.dataset}.{next_t.source.table}` AS {next_t.name} ON {j.on}"
        )

    # Fan-Out Guard Enforcement
    if tables_via_fanout:
        is_count_distinct = metric.type == "count_distinct"
        is_distinct_ratio = False
        if metric.type == "ratio":
            num_agg = parse_single_aggregate(metric.numerator_sql or "")
            den_agg = parse_single_aggregate(metric.denominator_sql or "")
            if (
                num_agg is not None
                and num_agg[0] == "COUNT"
                and num_agg[1] is True
                and den_agg is not None
                and den_agg[0] == "COUNT"
                and den_agg[1] is True
            ):
                is_distinct_ratio = True

        if not (is_count_distinct or is_distinct_ratio):
            raise CoverageError("Join traversal introduces 1:N/M:N fan-out for non-distinct metric")

        # In ratio metrics with fanout, ensure no filter references a fanout table
        if metric.type == "ratio":
            for f in validated_filters:
                dim_tbl = contract.dimensions[f.dimension_id].table
                if dim_tbl in tables_via_fanout:
                    raise CoverageError(
                        f"Filter on 1:N joined table '{dim_tbl}' would shrink ratio denominator"
                    )
            for rf in metric.required_filters:
                for qual, _ in extract_qualified_columns(rf):
                    if qual in tables_via_fanout:
                        raise CoverageError(
                            f"Filter on 1:N joined table '{qual}' would shrink ratio denominator"
                        )

    # Build metric SQL expression
    m_type = metric.type.lower()
    if m_type == "sum":
        metric_expr = f"SUM({metric.sql})"
    elif m_type == "count":
        metric_expr = f"COUNT({metric.sql})"
    elif m_type == "count_distinct":
        metric_expr = f"COUNT(DISTINCT {metric.sql})"
    elif m_type == "avg":
        metric_expr = f"AVG({metric.sql})"
    elif m_type == "min":
        metric_expr = f"MIN({metric.sql})"
    elif m_type == "max":
        metric_expr = f"MAX({metric.sql})"
    elif m_type == "ratio":
        den = (metric.denominator_sql or "").strip()
        if den.upper().startswith("NULLIF("):
            den_expr = den
        else:
            den_expr = f"NULLIF({den}, 0)"
        metric_expr = f"SAFE_DIVIDE({metric.numerator_sql}, {den_expr})"
    else:
        raise CoverageError(f"Unsupported metric type '{metric.type}'")

    # SELECT items
    select_items = [f"{contract.dimensions[d].sql} AS {d}" for d in final_group_by]
    select_items.append(f"{metric_expr} AS {metric.name}")

    # FROM clause
    base_t = contract.tables[metric.base_table]
    from_clause = f"FROM `{base_t.source.project}.{base_t.source.dataset}.{base_t.source.table}` AS {base_t.name}"

    # WHERE predicates
    where_preds: list[str] = list(metric.required_filters)
    for f in validated_filters:
        dim = contract.dimensions[f.dimension_id]
        if f.op == "IN":
            val_strs = ", ".join(_format_literal(v) for v in f.values)
            where_preds.append(f"{dim.sql} IN ({val_strs})")
        else:
            val_str = _format_literal(f.values[0])
            where_preds.append(f"{dim.sql} {f.op} {val_str}")

    # Assemble query lines
    lines: list[str] = ["SELECT", "  " + ",\n  ".join(select_items), from_clause]
    if join_clauses:
        lines.extend(join_clauses)
    if where_preds:
        lines.append("WHERE " + " AND ".join(where_preds))
    if final_group_by:
        lines.append("GROUP BY " + ", ".join(contract.dimensions[d].sql for d in final_group_by))

    order_by_clause: str | None = None
    if final_group_by or metric.default_order_by == "metric_desc":
        order_items = [f"{metric.name} DESC"] + [f"{d}" for d in final_group_by]
        order_by_clause = "ORDER BY " + ", ".join(order_items)
        lines.append(order_by_clause)

    if effective_limit is not None:
        lines.append(f"LIMIT {effective_limit}")

    final_sql = "\n".join(lines)

    referenced_sources = tuple(contract.tables[t_name].source.qualified_name for t_name in ordered_bound_tables)

    return CompiledMetricQuery(
        sql=final_sql,
        contract_id=contract.id,
        metric_id=metric.name,
        metric_type=metric.type,
        group_by_dimensions=tuple(final_group_by),
        filter_dimensions=tuple(filter_dims),
        referenced_sources=referenced_sources,
        effective_limit=effective_limit,
    )
