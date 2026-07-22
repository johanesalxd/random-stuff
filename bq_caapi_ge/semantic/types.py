"""Typed semantic contract models."""

from __future__ import annotations

from dataclasses import dataclass, field


SUPPORTED_RELATIONSHIPS = {
    "one_to_one",
    "one_to_many",
    "many_to_one",
    "many_to_many",
}


class ContractError(ValueError):
    """Raised when a semantic contract is invalid."""


@dataclass(frozen=True)
class TableSource:
    """Identifies a physical BigQuery table."""

    project: str
    dataset: str
    table: str

    @property
    def qualified_name(self) -> str:
        """Returns the fully qualified BigQuery table name."""
        return f"{self.project}.{self.dataset}.{self.table}"


@dataclass(frozen=True)
class Table:
    """Describes a physical table and its grain."""

    name: str
    source: TableSource
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
    """Describes a semantic dimension."""

    name: str
    label: str
    description: str
    table: str
    sql: str
    synonyms: tuple[str, ...] = ()


@dataclass(frozen=True)
class Metric:
    """Describes a semantic metric formula and usage constraints."""

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
    """Portable semantic domain context and physical source mappings."""

    id: str
    version: int
    owner: str
    description: str
    routing_terms: tuple[str, ...]
    examples: tuple[str, ...]
    tables: dict[str, Table]
    joins: dict[str, Join]
    dimensions: dict[str, Dimension]
    metrics: dict[str, Metric]

    @property
    def contract_version(self) -> str:
        """Returns a stable external contract version string."""
        return f"{self.id}:v{self.version}"
