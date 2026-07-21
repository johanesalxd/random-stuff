"""Loads and validates semantic contracts."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from semantic.types import (
    SUPPORTED_METRIC_TYPES,
    SUPPORTED_OPERATORS,
    ContractError,
    Dimension,
    Join,
    Metric,
    SemanticContract,
    Table,
)


DEFAULT_CONTRACT_PATH = (
    Path(__file__).resolve().parents[1]
    / "config"
    / "semantic_contracts"
    / "thelook_orders.yaml"
)


def load_contract(path: Path | str = DEFAULT_CONTRACT_PATH) -> SemanticContract:
    """Loads and validates a semantic contract file.

    Args:
        path: Path to a YAML semantic contract.

    Returns:
        Parsed and validated semantic contract.

    Raises:
        ContractError: If the contract is malformed or inconsistent.
    """
    contract_path = Path(path)
    with contract_path.open(encoding="utf-8") as file:
        raw = yaml.safe_load(file)
    if not isinstance(raw, dict):
        raise ContractError("contract root must be a mapping")

    contract = _parse_contract(raw)
    validate_contract(contract)
    return contract


def validate_contract(contract: SemanticContract) -> None:
    """Validates references and compile-time constraints in a contract.

    Args:
        contract: Contract to validate.

    Raises:
        ContractError: If a reference or metric definition is invalid.
    """
    if not contract.certified:
        raise ContractError("contract must be certified")

    for table in contract.tables.values():
        for reference in table.foreign_keys.values():
            target_table, _, target_column = reference.partition(".")
            if not target_table or not target_column:
                raise ContractError(f"invalid foreign key target: {reference}")
            if target_table not in contract.tables:
                raise ContractError(f"unknown foreign key table: {target_table}")

    for join in contract.joins.values():
        if join.left not in contract.tables:
            raise ContractError(
                f"join {join.name} references unknown table {join.left}"
            )
        if join.right not in contract.tables:
            raise ContractError(
                f"join {join.name} references unknown table {join.right}"
            )

    for dimension in contract.dimensions.values():
        if dimension.table not in contract.tables:
            raise ContractError(
                f"dimension {dimension.name} references unknown table {dimension.table}"
            )

    for metric in contract.metrics.values():
        _validate_metric(contract, metric)


def _parse_contract(raw: dict[str, Any]) -> SemanticContract:
    return SemanticContract(
        version=_required_int(raw, "version"),
        dataset=_required_str(raw, "dataset"),
        owner=_required_str(raw, "owner"),
        certified=_required_bool(raw, "certified"),
        tables=_parse_tables(_required_mapping(raw, "tables")),
        joins=_parse_joins(_required_mapping(raw, "joins")),
        dimensions=_parse_dimensions(_required_mapping(raw, "dimensions")),
        metrics=_parse_metrics(_required_mapping(raw, "metrics")),
    )


def _parse_tables(raw_tables: dict[str, Any]) -> dict[str, Table]:
    tables = {}
    for name, raw_table in raw_tables.items():
        table = _ensure_mapping(raw_table, f"tables.{name}")
        tables[name] = Table(
            name=name,
            primary_key=_required_str(table, "primary_key"),
            grain=_required_str(table, "grain"),
            foreign_keys=dict(table.get("foreign_keys", {})),
        )
    return tables


def _parse_joins(raw_joins: dict[str, Any]) -> dict[str, Join]:
    joins = {}
    for name, raw_join in raw_joins.items():
        join = _ensure_mapping(raw_join, f"joins.{name}")
        joins[name] = Join(
            name=name,
            left=_required_str(join, "left"),
            right=_required_str(join, "right"),
            on=_required_str(join, "on"),
            relationship=_required_str(join, "relationship"),
        )
    return joins


def _parse_dimensions(raw_dimensions: dict[str, Any]) -> dict[str, Dimension]:
    dimensions = {}
    for name, raw_dimension in raw_dimensions.items():
        dimension = _ensure_mapping(raw_dimension, f"dimensions.{name}")
        dimensions[name] = Dimension(
            name=name,
            label=_required_str(dimension, "label"),
            description=_required_str(dimension, "description"),
            table=_required_str(dimension, "table"),
            sql=_required_str(dimension, "sql"),
            synonyms=tuple(dimension.get("synonyms", [])),
        )
    return dimensions


def _parse_metrics(raw_metrics: dict[str, Any]) -> dict[str, Metric]:
    metrics = {}
    for name, raw_metric in raw_metrics.items():
        metric = _ensure_mapping(raw_metric, f"metrics.{name}")
        metrics[name] = Metric(
            name=name,
            label=_required_str(metric, "label"),
            description=_required_str(metric, "description"),
            type=_required_str(metric, "type"),
            base_table=_required_str(metric, "base_table"),
            sql=metric.get("sql"),
            numerator_sql=metric.get("numerator_sql"),
            denominator_sql=metric.get("denominator_sql"),
            synonyms=tuple(metric.get("synonyms", [])),
            required_filters=tuple(metric.get("required_filters", [])),
            required_dimensions=tuple(metric.get("required_dimensions", [])),
            allowed_dimensions=tuple(metric.get("allowed_dimensions", [])),
            join_path=tuple(metric.get("join_path", [])),
            allowed_filters={
                dimension: tuple(operators)
                for dimension, operators in metric.get("allowed_filters", {}).items()
            },
            default_order_by=metric.get("default_order_by"),
            default_limit=metric.get("default_limit"),
        )
    return metrics


def _validate_metric(contract: SemanticContract, metric: Metric) -> None:
    if metric.type not in SUPPORTED_METRIC_TYPES:
        raise ContractError(f"metric {metric.name} has unsupported type {metric.type}")
    if metric.base_table not in contract.tables:
        raise ContractError(
            f"metric {metric.name} references unknown table {metric.base_table}"
        )
    if metric.type in {"count_distinct", "sum"} and not metric.sql:
        raise ContractError(f"metric {metric.name} requires sql")
    if metric.type == "ratio" and (
        not metric.numerator_sql or not metric.denominator_sql
    ):
        raise ContractError(f"metric {metric.name} requires numerator and denominator")

    for join_name in metric.join_path:
        if join_name not in contract.joins:
            raise ContractError(
                f"metric {metric.name} references unknown join {join_name}"
            )

    for dimension_name in metric.allowed_dimensions + metric.required_dimensions:
        if dimension_name not in contract.dimensions:
            raise ContractError(
                f"metric {metric.name} references unknown dimension {dimension_name}"
            )
        if not _is_table_reachable(
            contract, metric, contract.dimensions[dimension_name].table
        ):
            raise ContractError(
                f"dimension {dimension_name} is not reachable from metric {metric.name}"
            )

    for dimension_name, operators in metric.allowed_filters.items():
        if dimension_name not in metric.allowed_dimensions:
            raise ContractError(
                f"filter {dimension_name} is not an allowed dimension for {metric.name}"
            )
        unsupported_operators = set(operators) - SUPPORTED_OPERATORS
        if unsupported_operators:
            raise ContractError(
                f"filter {dimension_name} has unsupported operators: "
                f"{sorted(unsupported_operators)}"
            )


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


def _required_mapping(raw: dict[str, Any], key: str) -> dict[str, Any]:
    return _ensure_mapping(raw.get(key), key)


def _ensure_mapping(value: Any, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ContractError(f"{name} must be a mapping")
    return value


def _required_str(raw: dict[str, Any], key: str) -> str:
    value = raw.get(key)
    if not isinstance(value, str) or not value:
        raise ContractError(f"{key} must be a non-empty string")
    return value


def _required_int(raw: dict[str, Any], key: str) -> int:
    value = raw.get(key)
    if not isinstance(value, int):
        raise ContractError(f"{key} must be an integer")
    return value


def _required_bool(raw: dict[str, Any], key: str) -> bool:
    value = raw.get(key)
    if not isinstance(value, bool):
        raise ContractError(f"{key} must be a boolean")
    return value
