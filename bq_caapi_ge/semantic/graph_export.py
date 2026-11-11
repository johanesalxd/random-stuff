"""Semantic Layer Exporter for BigQuery Property Graphs, Constraints, and Verified Queries.

Generates GA BigQuery Property Graph DDL with semantic MEASURE() definitions,
non-enforced PK/FK constraints with pre-flight orphan validation queries,
authored verified query specifications, and v1beta Data Agent datasource references.
Zero external dependencies (stdlib + semantic core modules only).
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
import re
from typing import Any

from semantic.compiler import compile_metric_query
from semantic.sql_lex import (
    format_googlesql_string_literal,
    parse_single_aggregate,
    rewrite_base_table_qualifiers,
)
from semantic.types import SemanticContract, VerifiedQuerySpec


class GraphExportError(ValueError):
    """Raised when a semantic contract cannot be safely exported to a Property Graph."""


@dataclass(frozen=True)
class SkippedGraphMetric:
    """Explains why a semantic metric was omitted from the Property Graph DDL."""

    metric_id: str
    reason: str


@dataclass(frozen=True)
class GraphExportResult:
    """Full result of Property Graph DDL generation."""

    ddl: str
    graph_name: str
    exported_metrics: tuple[str, ...]
    skipped_metrics: tuple[SkippedGraphMetric, ...]


_IDENT_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")


def _to_pascal_case(name: str) -> str:
    """Converts snake_case to PascalCase (e.g. order_items -> OrderItems)."""
    return "".join(part.capitalize() for part in name.split("_") if part)


def export_property_graph_ddl(
    contract: SemanticContract,
    *,
    graph_project: str,
    graph_dataset: str,
    graph_name: str | None = None,
) -> GraphExportResult:
    """Generates BigQuery Property Graph DDL with MEASURE() declarations.

    Enforces directed N:1 DAG with in-degree <= 1, assigns unique PascalCase node
    and edge aliases, exports single-table measures, and classifies pre-grouped
    or cross-table metrics into skipped_metrics.
    """
    if not _IDENT_PATTERN.match(graph_project.strip()):
        raise GraphExportError(f"Invalid graph_project identifier: '{graph_project}'")
    if not _IDENT_PATTERN.match(graph_dataset.strip()):
        raise GraphExportError(f"Invalid graph_dataset identifier: '{graph_dataset}'")

    target_graph_name = graph_name.strip() if graph_name else f"{contract.id}_graph"
    if not _IDENT_PATTERN.match(target_graph_name):
        raise GraphExportError(f"Invalid graph_name identifier: '{target_graph_name}'")

    # Map tables to PascalCase node aliases
    node_aliases: dict[str, str] = {}
    for t_name in contract.tables:
        node_aliases[t_name] = _to_pascal_case(t_name)

    # Build directed N:1 edges strictly from contract.joins
    # Edge is directed child -> parent
    edges: list[tuple[str, str, str, str]] = []  # (child_tbl, parent_tbl, child_fk_col, parent_pk_col)

    for j in contract.joins.values():
        if j.relationship == "many_to_many":
            raise GraphExportError(
                f"Join '{j.name}' has relationship many_to_many. "
                "Junction-table node promotion is required for property graph export."
            )
        elif j.relationship == "one_to_many":
            child, parent = j.right, j.left
        elif j.relationship == "many_to_one":
            child, parent = j.left, j.right
        elif j.relationship == "one_to_one":
            left_t = contract.tables[j.left]
            right_t = contract.tables[j.right]
            if any(target.startswith(f"{j.right}.") for target in left_t.foreign_keys.values()):
                child, parent = j.left, j.right
            elif any(target.startswith(f"{j.left}.") for target in right_t.foreign_keys.values()):
                child, parent = j.right, j.left
            else:
                raise GraphExportError(
                    f"Join '{j.name}' is one_to_one but foreign_keys orientation cannot be determined."
                )
        else:
            raise GraphExportError(f"Unsupported join relationship '{j.relationship}' in join '{j.name}'")

        child_t = contract.tables[child]
        parent_t = contract.tables[parent]

        # Verify child foreign key matches parent primary key
        fk_col: str | None = None
        target_ref = f"{parent}.{parent_t.primary_key}"
        for col, target in child_t.foreign_keys.items():
            if target == target_ref:
                fk_col = col
                break

        if fk_col is None:
            raise GraphExportError(
                f"Child table '{child}' does not declare foreign key to parent '{parent}' "
                f"({target_ref}) matching join '{j.name}'"
            )

        edges.append((child, parent, fk_col, parent_t.primary_key))

    # Cycle and in-degree verification:
    # In child -> parent directed edges, each node can have at most one incoming edge
    in_degree: dict[str, int] = {t: 0 for t in contract.tables}
    adj: dict[str, list[str]] = {t: [] for t in contract.tables}

    for child, parent, _, _ in edges:
        in_degree[parent] += 1
        adj[child].append(parent)

    for node, deg in in_degree.items():
        if deg > 1:
            raise GraphExportError(f"Directed graph violates in-degree <= 1: node '{node}' has in-degree {deg}")

    # Cycle detection via topological sort
    q: deque[str] = deque([t for t in contract.tables if in_degree[t] == 0])
    visited_count = 0
    in_deg_copy = dict(in_degree)
    while q:
        curr = q.popleft()
        visited_count += 1
        for nxt in adj[curr]:
            in_deg_copy[nxt] -= 1
            if in_deg_copy[nxt] == 0:
                q.append(nxt)

    if visited_count != len(contract.tables):
        raise GraphExportError("Property graph relationships contain a cycle")

    # Classify metrics
    exported_metrics: list[str] = []
    skipped_metrics: list[SkippedGraphMetric] = []
    table_measures: dict[str, list[str]] = {t: [] for t in contract.tables}
    table_referenced_columns: dict[str, set[str]] = {t: set() for t in contract.tables}

    for m in contract.metrics.values():
        if m.required_dimensions or m.default_limit is not None:
            skipped_metrics.append(
                SkippedGraphMetric(
                    m.name,
                    "Pre-grouped or ranked metric requires GROUP BY / LIMIT; use Tier-1 Compiler or Verified Queries",
                )
            )
            continue

        # Inspect external table qualifiers
        all_formula_text = " ".join(
            filter(None, [m.sql, m.numerator_sql, m.denominator_sql] + list(m.required_filters))
        )
        _, _, ext_tables = rewrite_base_table_qualifiers(all_formula_text, m.base_table)
        if ext_tables:
            skipped_metrics.append(
                SkippedGraphMetric(
                    m.name,
                    f"Cross-table metric references {', '.join(ext_tables)}; use Tier-1 Compiler or Verified Queries",
                )
            )
            continue

        # Single-expression metric
        if m.type in ("sum", "count", "count_distinct", "avg", "min", "max"):
            raw_sql = m.sql or ""
            rw_sql, base_cols, _ = rewrite_base_table_qualifiers(raw_sql, m.base_table)
            table_referenced_columns[m.base_table].update(base_cols)

            rw_filters: list[str] = []
            for rf in m.required_filters:
                rf_clean, rf_cols, _ = rewrite_base_table_qualifiers(rf, m.base_table)
                table_referenced_columns[m.base_table].update(rf_cols)
                rw_filters.append(f"({rf_clean})")

            cond = " AND ".join(rw_filters)
            mtype = m.type.lower()
            if cond:
                if mtype == "count" and rw_sql.strip() == "*":
                    agg_expr = f"COUNTIF({cond})"
                elif mtype == "count_distinct":
                    agg_expr = f"COUNT(DISTINCT CASE WHEN {cond} THEN {rw_sql} END)"
                else:
                    agg_expr = f"{mtype.upper()}(CASE WHEN {cond} THEN {rw_sql} END)"
            else:
                if mtype == "count_distinct":
                    agg_expr = f"COUNT(DISTINCT {rw_sql})"
                elif mtype == "count" and rw_sql.strip() == "*":
                    agg_expr = "COUNT(*)"
                else:
                    agg_expr = f"{mtype.upper()}({rw_sql})"

            desc = format_googlesql_string_literal(m.description)
            measure_def = f"MEASURE({agg_expr}) AS {m.name} OPTIONS (description = {desc})"
            table_measures[m.base_table].append(measure_def)
            exported_metrics.append(m.name)

        elif m.type == "ratio":
            # Same-table ratio
            num_sql = (m.numerator_sql or "").strip()
            den_sql = (m.denominator_sql or "").strip()

            num_res = parse_single_aggregate(num_sql)
            den_res = parse_single_aggregate(den_sql)
            valid_aggs = {"SUM", "COUNT", "AVG", "MIN", "MAX"}
            if (
                not num_res
                or not den_res
                or num_res[0] not in valid_aggs
                or den_res[0] not in valid_aggs
            ):
                skipped_metrics.append(
                    SkippedGraphMetric(
                        m.name,
                        "Ratio numerator/denominator are not simple single aggregates; use Tier-1 Compiler or Verified Queries",
                    )
                )
                continue

            num_agg, num_dist, num_col = num_res
            den_agg, den_dist, den_col = den_res

            rw_num_col, num_cols, _ = rewrite_base_table_qualifiers(num_col, m.base_table)
            rw_den_col, den_cols, _ = rewrite_base_table_qualifiers(den_col, m.base_table)
            table_referenced_columns[m.base_table].update(num_cols)
            table_referenced_columns[m.base_table].update(den_cols)

            rw_filters = []
            for rf in m.required_filters:
                rf_clean, rf_cols, _ = rewrite_base_table_qualifiers(rf, m.base_table)
                table_referenced_columns[m.base_table].update(rf_cols)
                rw_filters.append(f"({rf_clean})")
            cond = " AND ".join(rw_filters)

            if cond:
                num_expr = f"{num_agg.upper()}({'DISTINCT ' if num_dist else ''}CASE WHEN {cond} THEN {rw_num_col} END)"
                den_expr = f"{den_agg.upper()}({'DISTINCT ' if den_dist else ''}CASE WHEN {cond} THEN {rw_den_col} END)"
            else:
                num_expr = f"{num_agg.upper()}({'DISTINCT ' if num_dist else ''}{rw_num_col})"
                den_expr = f"{den_agg.upper()}({'DISTINCT ' if den_dist else ''}{rw_den_col})"

            num_helper = f"{m.name}_numerator"
            den_helper = f"{m.name}_denominator"
            desc_num = format_googlesql_string_literal(f"Numerator helper for {m.label}")
            desc_den = format_googlesql_string_literal(f"Denominator helper for {m.label}")
            desc_ratio = format_googlesql_string_literal(m.description)

            table_measures[m.base_table].append(
                f"MEASURE({num_expr}) AS {num_helper} OPTIONS (description = {desc_num})"
            )
            table_measures[m.base_table].append(
                f"MEASURE({den_expr}) AS {den_helper} OPTIONS (description = {desc_den})"
            )
            table_measures[m.base_table].append(
                f"MEASURE(SAFE_DIVIDE(AGG({num_helper}), NULLIF(AGG({den_helper}), 0))) AS {m.name} OPTIONS (description = {desc_ratio})"
            )
            exported_metrics.append(m.name)
        else:
            skipped_metrics.append(
                SkippedGraphMetric(m.name, f"Unsupported metric type '{m.type}' for property graph export")
            )

    # Add dimensions to referenced columns
    for d in contract.dimensions.values():
        _, cols, _ = rewrite_base_table_qualifiers(d.sql, d.table)
        table_referenced_columns[d.table].update(cols)

    # Add PK and FKs to referenced columns
    for t_name, t in contract.tables.items():
        table_referenced_columns[t_name].add(t.primary_key)
        for fk_c in t.foreign_keys:
            table_referenced_columns[t_name].add(fk_c)

    # Format NODE TABLES
    node_blocks: list[str] = []
    for t_name, t in contract.tables.items():
        alias = node_aliases[t_name]
        raw_cols = sorted(table_referenced_columns[t_name])
        measures = table_measures[t_name]

        prop_elements = list(raw_cols) + measures
        if prop_elements:
            inner_props = ",\n        ".join(prop_elements)
            prop_clause = f"PROPERTIES (\n        {inner_props}\n      )"
        else:
            prop_clause = "NO PROPERTIES"

        desc = format_googlesql_string_literal(f"{t.grain} grain")
        node_blocks.append(
            f"    `{t.source.project}.{t.source.dataset}.{t.source.table}` AS {alias}\n"
            f"      KEY ({t.primary_key})\n"
            f"      DEFAULT LABEL OPTIONS (description = {desc})\n"
            f"      {prop_clause}"
        )

    # Format EDGE TABLES
    edge_blocks: list[str] = []
    used_edge_aliases: set[str] = set()

    for child, parent, fk_col, parent_pk in edges:
        child_t = contract.tables[child]
        parent_t = contract.tables[parent]
        child_alias = node_aliases[child]
        parent_alias = node_aliases[parent]

        base_edge_alias = f"{child_alias}To{parent_alias}"
        edge_alias = base_edge_alias
        counter = 2
        while edge_alias in used_edge_aliases:
            edge_alias = f"{base_edge_alias}_{counter}"
            counter += 1
        used_edge_aliases.add(edge_alias)

        edge_blocks.append(
            f"    `{child_t.source.project}.{child_t.source.dataset}.{child_t.source.table}` AS {edge_alias}\n"
            f"      KEY ({child_t.primary_key})\n"
            f"      SOURCE KEY ({child_t.primary_key}) REFERENCES {child_alias} ({child_t.primary_key})\n"
            f"      DESTINATION KEY ({fk_col}) REFERENCES {parent_alias} ({parent_pk})\n"
            f"      NO PROPERTIES"
        )

    # Construct header comments
    header_lines = [
        f"-- Property Graph DDL generated from semantic contract: {contract.id}",
        f"-- Exported metrics ({len(exported_metrics)}): {', '.join(exported_metrics)}",
    ]
    if skipped_metrics:
        header_lines.append(f"-- Skipped metrics ({len(skipped_metrics)}):")
        for sm in skipped_metrics:
            header_lines.append(f"--   - {sm.metric_id}: {sm.reason}")

    ddl_body_parts = [
        "\n".join(header_lines),
        f"CREATE OR REPLACE PROPERTY GRAPH `{graph_project}.{graph_dataset}.{target_graph_name}`",
        "  NODE TABLES (",
        ",\n".join(node_blocks),
        "  )",
    ]
    if edge_blocks:
        ddl_body_parts.extend([
            "  EDGE TABLES (",
            ",\n".join(edge_blocks),
            "  );",
        ])
    else:
        ddl_body_parts[-1] = "  );"

    full_ddl = "\n".join(ddl_body_parts)

    return GraphExportResult(
        ddl=full_ddl,
        graph_name=target_graph_name,
        exported_metrics=tuple(exported_metrics),
        skipped_metrics=tuple(skipped_metrics),
    )


def export_fk_constraints_ddl(
    contract: SemanticContract,
    *,
    target_project: str,
    target_dataset: str,
) -> str:
    """Generates non-enforced PK and FK ALTER TABLE statements and validation queries.

    Raises:
        ValueError: If target_project is 'bigquery-public-data'.
    """
    clean_proj = target_project.strip()
    clean_ds = target_dataset.strip()

    if not _IDENT_PATTERN.match(clean_proj):
        raise GraphExportError(f"Invalid target_project identifier: '{target_project}'")
    if not _IDENT_PATTERN.match(clean_ds):
        raise GraphExportError(f"Invalid target_dataset identifier: '{target_dataset}'")

    if clean_proj.lower() == "bigquery-public-data":
        raise ValueError("Cannot generate ALTER TABLE constraints for read-only 'bigquery-public-data'")

    lines: list[str] = [
        f"-- Non-enforced PK/FK constraints generated from contract: {contract.id}",
        f"-- Target: `{clean_proj}.{clean_ds}`",
        "",
        "-- ============================================================================",
        "-- 1. Pre-flight Validation Queries (Run to confirm zero duplicates and orphans)",
        "-- ============================================================================",
        "",
    ]

    for t_name, t in contract.tables.items():
        lines.append(f"-- Pre-flight: Check primary key uniqueness on `{clean_proj}.{clean_ds}.{t.source.table}`")
        lines.append(f"SELECT {t.primary_key}, COUNT(1) AS dup_count")
        lines.append(f"FROM `{clean_proj}.{clean_ds}.{t.source.table}`")
        lines.append(f"GROUP BY {t.primary_key}")
        lines.append("HAVING dup_count > 1;\n")

    for child_name, child_t in contract.tables.items():
        for fk_col, parent_ref in child_t.foreign_keys.items():
            parent_name, parent_pk = parent_ref.split(".", 1)
            parent_t = contract.tables[parent_name]
            lines.append(
                f"-- Pre-flight: Check orphans for `{clean_proj}.{clean_ds}.{child_t.source.table}.{fk_col}` -> `{parent_t.source.table}.{parent_pk}`"
            )
            lines.append(f"SELECT child.{fk_col}")
            lines.append(f"FROM `{clean_proj}.{clean_ds}.{child_t.source.table}` AS child")
            lines.append(f"LEFT JOIN `{clean_proj}.{clean_ds}.{parent_t.source.table}` AS parent")
            lines.append(f"  ON child.{fk_col} = parent.{parent_pk}")
            lines.append(f"WHERE child.{fk_col} IS NOT NULL AND parent.{parent_pk} IS NULL;\n")

    lines.extend([
        "-- ============================================================================",
        "-- 2. Primary Key Declarations (Run once per table)",
        "-- ============================================================================",
        "",
    ])

    for t_name, t in contract.tables.items():
        lines.append(
            f"ALTER TABLE `{clean_proj}.{clean_ds}.{t.source.table}`\n"
            f"  ADD PRIMARY KEY ({t.primary_key}) NOT ENFORCED;\n"
        )

    lines.extend([
        "-- ============================================================================",
        "-- 3. Foreign Key Declarations",
        "-- ============================================================================",
        "",
    ])

    for child_name, child_t in contract.tables.items():
        for fk_col, parent_ref in child_t.foreign_keys.items():
            parent_name, parent_pk = parent_ref.split(".", 1)
            parent_t = contract.tables[parent_name]
            constraint_name = f"fk_{child_t.source.table}_{fk_col}_{parent_t.source.table}"
            lines.append(
                f"ALTER TABLE `{clean_proj}.{clean_ds}.{child_t.source.table}`\n"
                f"  ADD CONSTRAINT IF NOT EXISTS {constraint_name}\n"
                f"  FOREIGN KEY ({fk_col}) REFERENCES `{clean_proj}.{clean_ds}.{parent_t.source.table}`({parent_pk}) NOT ENFORCED;\n"
            )

    return "\n".join(lines)


def export_verified_queries(contract: SemanticContract) -> tuple[VerifiedQuerySpec, ...]:
    """Compiles canonical verified queries for all declared contract metrics.

    Note that the generated question strings are starter templates. Callers
    registering exact prompt+SQL allowlists in ca_trust should align question
    phrasings with their expected user prompts.
    """
    specs: list[VerifiedQuerySpec] = []
    for m in contract.metrics.values():
        compiled = compile_metric_query(
            contract,
            metric_id=m.name,
            group_by_dimension_ids=(),
        )
        if m.required_dimensions:
            question = f"Show {m.label.lower()}"
        elif m.type.lower() in {"count", "count_distinct"}:
            question = f"How many {m.label.lower()} are there?"
        else:
            question = f"What is the {m.label.lower()}?"
        specs.append(
            VerifiedQuerySpec(
                question=question,
                sql=compiled.sql,
                query_id=m.name,
            )
        )
    return tuple(specs)


def build_data_agent_datasource_references(
    contract: SemanticContract,
    *,
    graph_project: str | None = None,
    graph_dataset: str | None = None,
    graph_name: str | None = None,
) -> dict[str, Any]:
    """Builds v1beta Data Agent datasource references structure."""
    table_refs: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()

    for t in contract.tables.values():
        key = (t.source.project, t.source.dataset, t.source.table)
        if key not in seen:
            seen.add(key)
            table_refs.append({
                "projectId": t.source.project,
                "datasetId": t.source.dataset,
                "tableId": t.source.table,
            })

    out: dict[str, Any] = {"tableReferences": table_refs}

    if graph_project and graph_dataset:
        g_name = graph_name.strip() if graph_name else f"{contract.id}_graph"
        out["propertyGraphReferences"] = [
            {
                "projectId": graph_project.strip(),
                "datasetId": graph_dataset.strip(),
                "propertyGraphId": g_name,
            }
        ]

    return out
