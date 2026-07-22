"""Loads and validates semantic contracts."""

from __future__ import annotations

import os
from pathlib import Path
import re
from typing import Any

import yaml
from yaml.constructor import ConstructorError
from yaml.resolver import BaseResolver

from semantic.types import (
    SUPPORTED_METRIC_TYPES,
    SUPPORTED_OPERATORS,
    SUPPORTED_RELATIONSHIPS,
    ContractError,
    Dimension,
    Join,
    Metric,
    SemanticContract,
    Table,
    TableSource,
)


DEFAULT_CONTRACT_DIRECTORY = (
    Path(__file__).resolve().parents[1] / "config" / "semantic_contracts"
)
DEFAULT_CONTRACT_PATH = DEFAULT_CONTRACT_DIRECTORY / "thelook_orders.yaml"
_CONTRACT_PATH_ENV = "SEMANTIC_CONTRACT_PATH"
_MAX_CONTRACT_FILES = 50
_MAX_CONTRACT_FILE_BYTES = 1_000_000
_MAX_LIST_ITEMS = 100
_MAX_TEXT_LENGTH = 4_000
_MAX_IDENTIFIER_LENGTH = 128
_MAX_VERSION = 2_147_483_647
_SEMANTIC_IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_PROJECT_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9:-]{0,127}$")
_BIGQUERY_IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,1023}$")

_ROOT_KEYS = {
    "id",
    "version",
    "owner",
    "description",
    "routing_terms",
    "examples",
    "tables",
    "joins",
    "dimensions",
    "metrics",
}
_TABLE_KEYS = {"source", "primary_key", "grain", "foreign_keys"}
_SOURCE_KEYS = {"project", "dataset", "table"}
_JOIN_KEYS = {"left", "right", "on", "relationship"}
_DIMENSION_KEYS = {"label", "description", "table", "sql", "synonyms"}
_METRIC_KEYS = {
    "label",
    "description",
    "type",
    "base_table",
    "sql",
    "numerator_sql",
    "denominator_sql",
    "synonyms",
    "required_filters",
    "required_dimensions",
    "allowed_dimensions",
    "join_path",
    "allowed_filters",
    "default_order_by",
    "default_limit",
}


class _UniqueKeyLoader(yaml.SafeLoader):
    """Safe YAML loader that rejects duplicate mapping keys."""


def _construct_unique_mapping(
    loader: _UniqueKeyLoader,
    node: yaml.MappingNode,
    deep: bool = False,
) -> dict[Any, Any]:
    mapping = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        try:
            duplicate = key in mapping
        except TypeError as error:
            raise ConstructorError(
                "while constructing a mapping",
                node.start_mark,
                "found an unhashable mapping key",
                key_node.start_mark,
            ) from error
        if duplicate:
            raise ConstructorError(
                "while constructing a mapping",
                node.start_mark,
                f"found duplicate key: {key}",
                key_node.start_mark,
            )
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


_UniqueKeyLoader.add_constructor(
    BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_unique_mapping,
)


def load_contract(path: Path | str | None = None) -> SemanticContract:
    """Loads and validates a semantic contract file.

    Args:
        path: Path to a YAML semantic contract.

    Returns:
        Parsed and validated semantic contract.

    Raises:
        ContractError: If the contract is malformed or inconsistent.
    """
    contract_path = Path(path) if path is not None else DEFAULT_CONTRACT_PATH
    _validate_yaml_path(contract_path)
    if not contract_path.is_file():
        raise ContractError(f"contract path must be a YAML file: {contract_path}")
    return _load_contract_file(contract_path)


def load_contracts(path: Path | str | None = None) -> tuple[SemanticContract, ...]:
    """Loads one semantic contract file or all contracts in a directory.

    Args:
        path: Optional YAML file or directory. When omitted,
            SEMANTIC_CONTRACT_PATH is used before the default contract directory.

    Returns:
        Validated contracts in deterministic path order.

    Raises:
        ContractError: If the path is invalid, empty, or contains duplicate IDs.
    """
    contract_path = _configured_path(path, default=DEFAULT_CONTRACT_DIRECTORY)
    if contract_path.is_file():
        _validate_yaml_path(contract_path)
        paths = (contract_path,)
    elif contract_path.is_dir():
        paths = tuple(
            sorted(
                candidate
                for candidate in contract_path.iterdir()
                if candidate.is_file() and candidate.suffix in {".yaml", ".yml"}
            )
        )
    else:
        raise ContractError(f"semantic contract path does not exist: {contract_path}")
    if not paths:
        raise ContractError(f"no semantic contract files found: {contract_path}")
    if len(paths) > _MAX_CONTRACT_FILES:
        raise ContractError(
            f"semantic contract directory exceeds {_MAX_CONTRACT_FILES} files: "
            f"{contract_path}"
        )

    contracts = tuple(_load_contract_file(contract_file) for contract_file in paths)
    contract_ids = [contract.id for contract in contracts]
    duplicate_ids = sorted(
        contract_id
        for contract_id in set(contract_ids)
        if contract_ids.count(contract_id) > 1
    )
    if duplicate_ids:
        raise ContractError(f"duplicate semantic contract IDs: {duplicate_ids}")
    return contracts


def _configured_path(path: Path | str | None, *, default: Path) -> Path:
    if path is not None:
        return Path(path)
    configured_path = os.getenv(_CONTRACT_PATH_ENV, "").strip()
    return Path(configured_path) if configured_path else default


def _load_contract_file(contract_path: Path) -> SemanticContract:
    try:
        if contract_path.stat().st_size > _MAX_CONTRACT_FILE_BYTES:
            raise ContractError(
                f"semantic contract exceeds maximum file size: {contract_path}"
            )
        with contract_path.open(encoding="utf-8") as file:
            raw = yaml.load(file, Loader=_UniqueKeyLoader)
    except ContractError:
        raise
    except (OSError, UnicodeError, yaml.YAMLError) as error:
        raise ContractError(
            f"failed to read semantic contract {contract_path}: {error}"
        ) from error
    if not isinstance(raw, dict):
        raise ContractError(f"contract root must be a mapping: {contract_path}")

    try:
        contract = _parse_contract(raw)
        validate_contract(contract)
        return contract
    except ContractError as error:
        raise ContractError(
            f"invalid semantic contract {contract_path}: {error}"
        ) from error


def validate_contract(contract: SemanticContract) -> None:
    """Validates portable semantic references without compiler restrictions.

    Args:
        contract: Contract to validate.

    Raises:
        ContractError: If a semantic reference is invalid.
    """
    for table in contract.tables.values():
        for reference in table.foreign_keys.values():
            target_table, _, target_column = reference.partition(".")
            if not target_table or not target_column:
                raise ContractError(f"invalid foreign key target: {reference}")
            if target_table not in contract.tables:
                raise ContractError(f"unknown foreign key table: {target_table}")
            if target_column != contract.tables[target_table].primary_key:
                raise ContractError(
                    f"foreign key target must reference the primary key: {reference}"
                )

    for join in contract.joins.values():
        if join.left not in contract.tables:
            raise ContractError(
                f"join {join.name} references unknown table {join.left}"
            )
        if join.right not in contract.tables:
            raise ContractError(
                f"join {join.name} references unknown table {join.right}"
            )
        if join.relationship not in SUPPORTED_RELATIONSHIPS:
            raise ContractError(
                f"join {join.name} has unsupported relationship {join.relationship}"
            )

    for dimension in contract.dimensions.values():
        if dimension.table not in contract.tables:
            raise ContractError(
                f"dimension {dimension.name} references unknown table {dimension.table}"
            )

    for metric in contract.metrics.values():
        _validate_metric_references(contract, metric)


def validate_compiler_contract(contract: SemanticContract) -> None:
    """Validates restrictions required by the historical SQL compiler.

    Args:
        contract: Contract to validate for deterministic compilation.

    Raises:
        ContractError: If the compiler cannot safely consume the contract.
    """
    validate_contract(contract)
    for metric in contract.metrics.values():
        _validate_compiler_metric(contract, metric)


def _parse_contract(raw: dict[str, Any]) -> SemanticContract:
    _reject_unknown_keys(raw, _ROOT_KEYS, "contract")
    return SemanticContract(
        id=_required_identifier(raw, "id"),
        version=_required_int(raw, "version"),
        owner=_required_str(raw, "owner"),
        description=_required_str(raw, "description"),
        routing_terms=_required_str_tuple(raw, "routing_terms"),
        examples=_optional_str_tuple(raw, "examples"),
        tables=_parse_tables(_required_mapping(raw, "tables")),
        joins=_parse_joins(_required_mapping(raw, "joins")),
        dimensions=_parse_dimensions(_required_mapping(raw, "dimensions")),
        metrics=_parse_metrics(_required_mapping(raw, "metrics")),
    )


def _parse_tables(raw_tables: dict[str, Any]) -> dict[str, Table]:
    tables = {}
    for name, raw_table in raw_tables.items():
        _validate_identifier(name, "tables")
        table = _ensure_mapping(raw_table, f"tables.{name}")
        _reject_unknown_keys(table, _TABLE_KEYS, f"tables.{name}")
        source = _required_mapping(table, "source")
        _reject_unknown_keys(source, _SOURCE_KEYS, f"tables.{name}.source")
        tables[name] = Table(
            name=name,
            source=TableSource(
                project=_required_source_component(source, "project"),
                dataset=_required_source_component(source, "dataset"),
                table=_required_source_component(source, "table"),
            ),
            primary_key=_required_identifier(table, "primary_key"),
            grain=_required_str(table, "grain"),
            foreign_keys=_optional_str_mapping(
                table,
                "foreign_keys",
                f"tables.{name}.foreign_keys",
            ),
        )
    return tables


def _parse_joins(raw_joins: dict[str, Any]) -> dict[str, Join]:
    joins = {}
    for name, raw_join in raw_joins.items():
        _validate_identifier(name, "joins")
        join = _ensure_mapping(raw_join, f"joins.{name}")
        _reject_unknown_keys(join, _JOIN_KEYS, f"joins.{name}")
        joins[name] = Join(
            name=name,
            left=_required_identifier(join, "left"),
            right=_required_identifier(join, "right"),
            on=_required_str(join, "on"),
            relationship=_required_str(join, "relationship"),
        )
    return joins


def _parse_dimensions(raw_dimensions: dict[str, Any]) -> dict[str, Dimension]:
    dimensions = {}
    for name, raw_dimension in raw_dimensions.items():
        _validate_identifier(name, "dimensions")
        dimension = _ensure_mapping(raw_dimension, f"dimensions.{name}")
        _reject_unknown_keys(
            dimension,
            _DIMENSION_KEYS,
            f"dimensions.{name}",
        )
        dimensions[name] = Dimension(
            name=name,
            label=_required_str(dimension, "label"),
            description=_required_str(dimension, "description"),
            table=_required_identifier(dimension, "table"),
            sql=_required_str(dimension, "sql"),
            synonyms=_optional_str_tuple(
                dimension,
                "synonyms",
                name=f"dimensions.{name}.synonyms",
            ),
        )
    return dimensions


def _parse_metrics(raw_metrics: dict[str, Any]) -> dict[str, Metric]:
    metrics = {}
    for name, raw_metric in raw_metrics.items():
        _validate_identifier(name, "metrics")
        metric = _ensure_mapping(raw_metric, f"metrics.{name}")
        _reject_unknown_keys(metric, _METRIC_KEYS, f"metrics.{name}")
        metrics[name] = Metric(
            name=name,
            label=_required_str(metric, "label"),
            description=_required_str(metric, "description"),
            type=_required_identifier(metric, "type"),
            base_table=_required_identifier(metric, "base_table"),
            sql=_optional_str(metric, "sql"),
            numerator_sql=_optional_str(metric, "numerator_sql"),
            denominator_sql=_optional_str(metric, "denominator_sql"),
            synonyms=_optional_str_tuple(
                metric,
                "synonyms",
                name=f"metrics.{name}.synonyms",
            ),
            required_filters=_optional_str_tuple(
                metric,
                "required_filters",
                name=f"metrics.{name}.required_filters",
            ),
            required_dimensions=_optional_identifier_tuple(
                metric,
                "required_dimensions",
                name=f"metrics.{name}.required_dimensions",
            ),
            allowed_dimensions=_optional_identifier_tuple(
                metric,
                "allowed_dimensions",
                name=f"metrics.{name}.allowed_dimensions",
            ),
            join_path=_optional_identifier_tuple(
                metric,
                "join_path",
                name=f"metrics.{name}.join_path",
            ),
            allowed_filters={
                dimension: _ensure_str_list(
                    operators,
                    f"metrics.{name}.allowed_filters.{dimension}",
                )
                for dimension, operators in _validated_mapping_items(
                    metric,
                    "allowed_filters",
                    f"metrics.{name}.allowed_filters",
                )
            },
            default_order_by=_optional_str(metric, "default_order_by"),
            default_limit=_optional_int(metric, "default_limit"),
        )
    return metrics


def _validate_metric_references(contract: SemanticContract, metric: Metric) -> None:
    if metric.base_table not in contract.tables:
        raise ContractError(
            f"metric {metric.name} references unknown table {metric.base_table}"
        )
    for join_name in metric.join_path:
        if join_name not in contract.joins:
            raise ContractError(
                f"metric {metric.name} references unknown join {join_name}"
            )
    for dimension_name in set(
        metric.allowed_dimensions
        + metric.required_dimensions
        + tuple(metric.allowed_filters)
    ):
        if dimension_name not in contract.dimensions:
            raise ContractError(
                f"metric {metric.name} references unknown dimension {dimension_name}"
            )


def _validate_compiler_metric(contract: SemanticContract, metric: Metric) -> None:
    from semantic.join_planner import JoinPlanError, plan_joins

    if metric.type not in SUPPORTED_METRIC_TYPES:
        raise ContractError(f"metric {metric.name} has unsupported type {metric.type}")
    if metric.type in {"count_distinct", "sum"} and not metric.sql:
        raise ContractError(f"metric {metric.name} requires sql")
    if metric.type == "ratio" and (
        not metric.numerator_sql or not metric.denominator_sql
    ):
        raise ContractError(f"metric {metric.name} requires numerator and denominator")
    if not set(metric.required_dimensions).issubset(metric.allowed_dimensions):
        raise ContractError(
            f"metric {metric.name} required dimensions must also be allowed"
        )
    if metric.default_order_by not in {None, "metric_desc"}:
        raise ContractError(
            f"metric {metric.name} has unsupported default order {metric.default_order_by}"
        )
    if metric.default_limit is not None and (
        isinstance(metric.default_limit, bool)
        or not isinstance(metric.default_limit, int)
        or not 1 <= metric.default_limit <= 1000
    ):
        raise ContractError(
            f"metric {metric.name} default limit must be between 1 and 1000"
        )

    for dimension_name in metric.allowed_dimensions + metric.required_dimensions:
        try:
            planned_joins = plan_joins(
                contract,
                metric,
                {
                    metric.base_table,
                    contract.dimensions[dimension_name].table,
                },
            )
        except JoinPlanError as error:
            raise ContractError(
                f"dimension {dimension_name} is not reachable from metric {metric.name}"
            ) from error
        if metric.type in {"sum", "ratio"} and any(
            planned_join.introduces_fan_out for planned_join in planned_joins
        ):
            raise ContractError(
                f"dimension {dimension_name} introduces fan-out for metric {metric.name}"
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


def _required_mapping(raw: dict[str, Any], key: str) -> dict[str, Any]:
    return _ensure_mapping(raw.get(key), key)


def _ensure_mapping(value: Any, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ContractError(f"{name} must be a mapping")
    if len(value) > _MAX_LIST_ITEMS:
        raise ContractError(f"{name} exceeds {_MAX_LIST_ITEMS} items")
    return value


def _required_str(raw: dict[str, Any], key: str) -> str:
    value = raw.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ContractError(f"{key} must be a non-empty string")
    if len(value) > _MAX_TEXT_LENGTH:
        raise ContractError(f"{key} exceeds {_MAX_TEXT_LENGTH} characters")
    return value


def _required_int(raw: dict[str, Any], key: str) -> int:
    value = raw.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ContractError(f"{key} must be an integer")
    if not 1 <= value <= _MAX_VERSION:
        raise ContractError(f"{key} must be between 1 and {_MAX_VERSION}")
    return value


def _required_str_tuple(raw: dict[str, Any], key: str) -> tuple[str, ...]:
    value = raw.get(key)
    if not value:
        raise ContractError(f"{key} must be a non-empty list")
    return _ensure_str_list(value, key)


def _optional_str_tuple(
    raw: dict[str, Any],
    key: str,
    *,
    name: str | None = None,
) -> tuple[str, ...]:
    value = raw.get(key, [])
    return _ensure_str_list(value, name or key)


def _optional_identifier_tuple(
    raw: dict[str, Any],
    key: str,
    *,
    name: str,
) -> tuple[str, ...]:
    values = _optional_str_tuple(raw, key, name=name)
    for value in values:
        _validate_identifier(value, name)
    return values


def _ensure_str_list(value: Any, name: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise ContractError(f"{name} must be a list")
    if len(value) > _MAX_LIST_ITEMS:
        raise ContractError(f"{name} exceeds {_MAX_LIST_ITEMS} items")
    if any(
        not isinstance(item, str) or not item.strip() or len(item) > _MAX_TEXT_LENGTH
        for item in value
    ):
        raise ContractError(f"{name} must contain bounded non-empty strings")
    return tuple(value)


def _optional_mapping(
    raw: dict[str, Any],
    key: str,
    name: str,
) -> dict[str, Any]:
    value = raw.get(key, {})
    return _ensure_mapping(value, name)


def _validated_mapping_items(
    raw: dict[str, Any],
    key: str,
    name: str,
) -> tuple[tuple[str, Any], ...]:
    value = _optional_mapping(raw, key, name)
    for item_key in value:
        _validate_identifier(item_key, name)
    return tuple(value.items())


def _optional_str_mapping(
    raw: dict[str, Any],
    key: str,
    name: str,
) -> dict[str, str]:
    value = _optional_mapping(raw, key, name)
    if len(value) > _MAX_LIST_ITEMS:
        raise ContractError(f"{name} exceeds {_MAX_LIST_ITEMS} items")
    for item_key, item_value in value.items():
        _validate_identifier(item_key, name)
        if (
            not isinstance(item_value, str)
            or not item_value.strip()
            or len(item_value) > _MAX_TEXT_LENGTH
        ):
            raise ContractError(f"{name} must contain bounded non-empty strings")
    return {key: item.strip() for key, item in value.items()}


def _optional_str(raw: dict[str, Any], key: str) -> str | None:
    value = raw.get(key)
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ContractError(f"{key} must be a non-empty string when set")
    if len(value) > _MAX_TEXT_LENGTH:
        raise ContractError(f"{key} exceeds {_MAX_TEXT_LENGTH} characters")
    return value


def _optional_int(raw: dict[str, Any], key: str) -> int | None:
    value = raw.get(key)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise ContractError(f"{key} must be an integer when set")
    return value


def _reject_unknown_keys(
    raw: dict[str, Any],
    allowed: set[str],
    name: str,
) -> None:
    non_string_keys = [key for key in raw if not isinstance(key, str)]
    if non_string_keys:
        raise ContractError(f"{name} must use string field names")
    unknown = sorted(set(raw) - allowed)
    if unknown:
        raise ContractError(f"{name} has unknown fields: {unknown}")


def _validate_identifier(value: Any, name: str) -> None:
    if (
        not isinstance(value, str)
        or len(value) > _MAX_IDENTIFIER_LENGTH
        or not _SEMANTIC_IDENTIFIER_PATTERN.fullmatch(value)
    ):
        raise ContractError(f"{name} must use valid semantic identifiers")


def _required_identifier(raw: dict[str, Any], key: str) -> str:
    value = _required_str(raw, key)
    _validate_identifier(value, key)
    return value


def _required_source_component(raw: dict[str, Any], key: str) -> str:
    value = _required_str(raw, key)
    pattern = _PROJECT_PATTERN if key == "project" else _BIGQUERY_IDENTIFIER_PATTERN
    if not pattern.fullmatch(value):
        raise ContractError(f"{key} is not a valid BigQuery source component")
    return value


def _validate_yaml_path(path: Path) -> None:
    if path.suffix.lower() not in {".yaml", ".yml"}:
        raise ContractError(f"semantic contract must use .yaml or .yml: {path}")
