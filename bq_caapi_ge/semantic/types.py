"""Typed semantic contract models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


SUPPORTED_METRIC_TYPES = {"count_distinct", "sum", "ratio"}
SUPPORTED_OPERATORS = {"=", "IN"}
SUPPORTED_RELATIONSHIPS = {
    "one_to_one",
    "one_to_many",
    "many_to_one",
    "many_to_many",
}


class ContractError(ValueError):
    """Raised when a semantic contract is invalid."""


class CompileError(ValueError):
    """Raised when an intent cannot compile against the semantic contract."""


@dataclass(frozen=True)
class Table:
    """Describes a physical table and its grain."""

    name: str
    primary_key: str
    grain: str
    foreign_keys: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class Join:
    """Describes a declared relationship between two tables."""

    name: str
    left: str
    right: str
    on: str
    relationship: str


@dataclass(frozen=True)
class Dimension:
    """Describes a dimension available to certified intents."""

    name: str
    label: str
    description: str
    table: str
    sql: str
    synonyms: tuple[str, ...] = ()


@dataclass(frozen=True)
class Metric:
    """Describes a certified metric formula and coverage limits."""

    name: str
    label: str
    description: str
    type: str
    base_table: str
    allowed_dimensions: tuple[str, ...]
    join_path: tuple[str, ...]
    allowed_filters: dict[str, tuple[str, ...]]
    synonyms: tuple[str, ...] = ()
    sql: str | None = None
    numerator_sql: str | None = None
    denominator_sql: str | None = None
    required_filters: tuple[str, ...] = ()
    required_dimensions: tuple[str, ...] = ()
    default_order_by: str | None = None
    default_limit: int | None = None


@dataclass(frozen=True)
class SemanticContract:
    """Complete semantic contract used by the compiler."""

    version: int
    dataset: str
    owner: str
    certified: bool
    tables: dict[str, Table]
    joins: dict[str, Join]
    dimensions: dict[str, Dimension]
    metrics: dict[str, Metric]

    @property
    def contract_version(self) -> str:
        """Returns a stable external contract version string."""
        return f"{self.dataset}:v{self.version}"


@dataclass(frozen=True)
class IntentFilter:
    """A user-requested filter after intent selection."""

    dimension: str
    operator: str
    value: str | int | float | bool | list[str | int | float | bool]


@dataclass(frozen=True)
class QueryIntent:
    """Structured intent passed into the deterministic compiler."""

    metric: str
    dimensions: tuple[str, ...] = ()
    filters: tuple[IntentFilter, ...] = ()
    limit: int | None = None


@dataclass(frozen=True)
class QueryParameter:
    """A BigQuery query parameter emitted by the compiler."""

    name: str
    value: Any


@dataclass(frozen=True)
class CompiledQuery:
    """Compiled contract-validated SQL with metadata."""

    sql: str
    parameters: tuple[QueryParameter, ...]
    metric: str
    dimensions: tuple[str, ...]
    contract_version: str
    contract_certified: bool
