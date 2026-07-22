"""Deterministic SQL policy guardrails for Phase 8.

This module statically validates model-authored BigQuery SQL before any dry run or
execution. It enforces two guarantees that the execution engine cannot:

- read-only: exactly one statement, and that statement is a ``SELECT``/``WITH``
  query with no DDL or DML anywhere in the tree
- source scope: every referenced physical table is fully qualified and belongs to
  the exact set of sources the grounding step selected

Parsing uses ``sqlglot`` with the BigQuery dialect so common table expressions,
subqueries, and aliases are resolved at the AST level rather than by fragile text
matching. The module never generates or executes SQL.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

import sqlglot
from sqlglot import exp
from sqlglot.errors import SqlglotError

# Bounds keep validation predictable and reject pathological inputs early.
_MAX_SQL_CHARS = 20_000
_MAX_REFERENCED_TABLES = 25

# Node types that must never appear anywhere in a read-only query tree. Resolved
# defensively so a sqlglot version that renames or drops a type cannot crash us.
_FORBIDDEN_TYPE_NAMES = (
    "Insert",
    "Update",
    "Delete",
    "Merge",
    "Create",
    "Drop",
    "Alter",
    "Command",
    "Set",
    "TruncateTable",
    "Grant",
)


class SqlPolicyError(ValueError):
    """Raised for malformed policy inputs (not for policy rejections)."""


@dataclass(frozen=True)
class SqlPolicyResult:
    """Outcome of static SQL policy validation."""

    allowed: bool
    referenced_sources: tuple[str, ...]
    out_of_scope: tuple[str, ...]
    violations: tuple[str, ...]

    def to_context(self) -> dict[str, Any]:
        """Returns a JSON-safe representation for provenance payloads."""
        return {
            "allowed": self.allowed,
            "referenced_sources": list(self.referenced_sources),
            "out_of_scope": list(self.out_of_scope),
            "violations": list(self.violations),
        }


def extract_table_references(sql: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Extracts physical table references, separating qualified from unqualified.

    Common table expression names are not physical tables and are excluded. A
    reference is considered qualified only when it carries project, dataset, and
    table parts (``project.dataset.table``).

    Args:
        sql: The SQL text to inspect.

    Returns:
        A tuple ``(qualified, unqualified)`` of sorted, de-duplicated names.

    Raises:
        SqlPolicyError: If the SQL cannot be parsed.
    """
    statements = _parse(sql)
    cte_names = set()
    qualified: set[str] = set()
    unqualified: set[str] = set()
    for statement in statements:
        for cte in statement.find_all(exp.CTE):
            cte_names.add(cte.alias_or_name.lower())
    for statement in statements:
        for table in statement.find_all(exp.Table):
            name = table.name
            # A bare name matching a CTE alias is a reference to that CTE.
            if not table.catalog and not table.db and name.lower() in cte_names:
                continue
            parts = [part for part in (table.catalog, table.db, table.name) if part]
            full = ".".join(parts)
            if table.catalog and table.db and table.name:
                qualified.add(full)
            elif full:
                unqualified.add(full)
    return tuple(sorted(qualified)), tuple(sorted(unqualified))


def validate_sql(sql: str, *, permitted_sources: Iterable[str]) -> SqlPolicyResult:
    """Validates read-only status and source scope for model-authored SQL.

    Args:
        sql: The SQL text to validate.
        permitted_sources: Fully qualified sources the SQL may reference. These
            come from the selected catalog route, never from the compute project.

    Returns:
        A :class:`SqlPolicyResult`. ``allowed`` is ``True`` only when there are no
        violations and every referenced source is in scope.
    """
    permitted = frozenset(permitted_sources)
    violations: list[str] = []

    if not isinstance(sql, str) or not sql.strip():
        return SqlPolicyResult(False, (), (), ("empty sql",))
    if len(sql) > _MAX_SQL_CHARS:
        return SqlPolicyResult(False, (), (), (f"sql exceeds {_MAX_SQL_CHARS} chars",))

    try:
        statements = _parse(sql)
    except SqlPolicyError as error:
        return SqlPolicyResult(False, (), (), (str(error),))

    if len(statements) != 1:
        violations.append("sql must contain exactly one statement")
    statement = statements[0]
    if not isinstance(statement, exp.Query):
        violations.append("sql must be a read-only SELECT query")
    forbidden = _forbidden_types()
    if any(statement.find_all(*forbidden)):
        violations.append("sql must not contain DDL or DML operations")

    qualified, unqualified = extract_table_references(sql)
    if unqualified:
        violations.append(
            "sql must use fully qualified project.dataset.table names: "
            + ", ".join(unqualified)
        )
    if len(qualified) > _MAX_REFERENCED_TABLES:
        violations.append(f"sql references more than {_MAX_REFERENCED_TABLES} tables")
    if not qualified:
        violations.append("sql must reference at least one permitted source")

    out_of_scope = tuple(source for source in qualified if source not in permitted)
    if out_of_scope:
        violations.append(
            "sql references out-of-scope sources: " + ", ".join(out_of_scope)
        )

    allowed = not violations
    return SqlPolicyResult(
        allowed=allowed,
        referenced_sources=qualified,
        out_of_scope=out_of_scope,
        violations=tuple(violations),
    )


def _parse(sql: str) -> list[exp.Expression]:
    try:
        parsed = sqlglot.parse(sql, read="bigquery")
    except SqlglotError as error:
        raise SqlPolicyError(f"unparseable sql: {error}") from error
    statements = [statement for statement in parsed if statement is not None]
    if not statements:
        raise SqlPolicyError("unparseable sql: no statements")
    return statements


def _forbidden_types() -> tuple[type[exp.Expression], ...]:
    types: list[type[exp.Expression]] = []
    for name in _FORBIDDEN_TYPE_NAMES:
        candidate = getattr(exp, name, None)
        if isinstance(candidate, type) and issubclass(candidate, exp.Expression):
            types.append(candidate)
    return tuple(types)
