"""Shared deterministic join planning for validation and SQL compilation."""

from __future__ import annotations

from dataclasses import dataclass

from semantic.types import Join, Metric, SemanticContract


class JoinPlanError(ValueError):
    """Raised when a declared join path cannot reach required tables."""


@dataclass(frozen=True)
class PlannedJoin:
    """One ordered join selected from a metric's declared path."""

    join: Join
    table: str
    introduces_fan_out: bool


def plan_joins(
    contract: SemanticContract,
    metric: Metric,
    required_tables: set[str],
) -> tuple[PlannedJoin, ...]:
    """Plans joins in the exact order emitted by the SQL compiler.

    Args:
        contract: Validated semantic contract.
        metric: Metric whose declared join path is used.
        required_tables: Physical tables required by selected dimensions.

    Returns:
        Ordered joins needed to reach all required tables.

    Raises:
        JoinPlanError: If the ordered path cannot reach all required tables.
    """
    joined_tables = {metric.base_table}
    planned = []
    if required_tables.issubset(joined_tables):
        return ()

    for join_name in metric.join_path:
        join = contract.joins[join_name]
        if join.left in joined_tables and join.right not in joined_tables:
            planned.append(
                PlannedJoin(
                    join=join,
                    table=join.right,
                    introduces_fan_out=join.relationship
                    in {"one_to_many", "many_to_many"},
                )
            )
            joined_tables.add(join.right)
        elif join.right in joined_tables and join.left not in joined_tables:
            planned.append(
                PlannedJoin(
                    join=join,
                    table=join.left,
                    introduces_fan_out=join.relationship
                    in {"many_to_one", "many_to_many"},
                )
            )
            joined_tables.add(join.left)

        if required_tables.issubset(joined_tables):
            return tuple(planned)

    missing_tables = required_tables - joined_tables
    raise JoinPlanError(
        f"missing ordered join path for tables: {sorted(missing_tables)}"
    )
