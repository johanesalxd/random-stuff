"""Tests for the historical deterministic SQL compiler."""

from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from semantic.compiler import compile_query  # noqa: E402
from semantic.registry import (  # noqa: E402
    load_contract,
    validate_compiler_contract,
    validate_contract,
)
from semantic.types import (  # noqa: E402
    CompileError,
    ContractError,
    Dimension,
    IntentFilter,
    Join,
    QueryIntent,
)


def test_load_contract_validates_first_metrics():
    """Tests the default contract loads with the planned first metrics."""
    contract = load_contract()

    assert contract.contract_version == "thelook_orders:v1"
    assert contract.description == ("Order, customer, and completed-revenue analytics.")
    assert set(contract.metrics) == {
        "completed_order_count",
        "completed_revenue",
        "average_order_value",
        "top_users_by_completed_revenue",
    }


def test_portable_validation_does_not_enforce_compiler_capabilities():
    """Tests active semantic context can exceed historical compiler features."""
    contract = load_contract()
    metric = contract.metrics["completed_revenue"]
    portable_contract = replace(
        contract,
        metrics={
            **contract.metrics,
            metric.name: replace(
                metric,
                type="median",
                default_order_by="business_priority",
            ),
        },
    )

    validate_contract(portable_contract)

    with pytest.raises(ContractError, match="unsupported type"):
        validate_compiler_contract(portable_contract)


def test_compile_query_completed_orders_by_country_is_stable():
    """Tests SQL compilation is deterministic for the same intent."""
    contract = load_contract()
    intent = QueryIntent(
        metric="completed_order_count",
        dimensions=("country",),
    )

    first = compile_query(contract, intent)
    second = compile_query(contract, intent)

    assert first.sql == second.sql
    assert first.sql == "\n".join(
        [
            "SELECT",
            "  users.country AS country,",
            "  COUNT(DISTINCT orders.order_id) AS completed_order_count",
            "FROM `bigquery-public-data.thelook_ecommerce.orders` AS orders",
            "LEFT JOIN `bigquery-public-data.thelook_ecommerce.users` AS users",
            "  ON users.id = orders.user_id",
            "WHERE",
            "  orders.status = 'Complete'",
            "GROUP BY 1",
            "ORDER BY country",
        ]
    )
    assert first.compiled_from_contract is True
    assert first.parameters == ()


def test_compile_query_uses_parameters_for_user_filters():
    """Tests user-provided filters compile to query parameters."""
    contract = load_contract()
    compiled = compile_query(
        contract,
        QueryIntent(
            metric="completed_order_count",
            dimensions=("country",),
            filters=(IntentFilter("country", "=", "United States"),),
        ),
    )

    assert "users.country = @p1_country" in compiled.sql
    assert "United States" not in compiled.sql
    assert compiled.parameters[0].name == "p1_country"
    assert compiled.parameters[0].value == "United States"


def test_compile_query_in_filter_uses_unnest_parameter():
    """Tests IN filters compile to array parameters via UNNEST."""
    contract = load_contract()
    compiled = compile_query(
        contract,
        QueryIntent(
            metric="completed_revenue",
            filters=(IntentFilter("country", "IN", ["US", "UK"]),),
        ),
    )

    assert "users.country IN UNNEST(@p1_country)" in compiled.sql
    assert compiled.parameters[0].value == ["US", "UK"]


def test_compile_query_average_order_value_uses_safe_divide():
    """Tests ratio metrics compile with safe arithmetic."""
    contract = load_contract()
    compiled = compile_query(
        contract,
        QueryIntent(metric="average_order_value", dimensions=("country",)),
    )

    assert (
        "SAFE_DIVIDE(SUM(order_items.sale_price), "
        "COUNT(DISTINCT order_items.order_id)) AS average_order_value"
    ) in compiled.sql
    assert "order_items.status = 'Complete'" in compiled.sql


def test_compile_query_base_table_only_does_not_emit_unused_join():
    """Tests metrics without dimensions query only their base table."""
    contract = load_contract()

    compiled = compile_query(contract, QueryIntent(metric="completed_revenue"))

    assert (
        "FROM `bigquery-public-data.thelook_ecommerce.order_items` AS order_items"
        in compiled.sql
    )
    assert "JOIN" not in compiled.sql


def test_compile_query_top_users_applies_required_dimension_and_limit():
    """Tests top-user metric injects grouping, ordering, and default limit."""
    contract = load_contract()
    compiled = compile_query(
        contract,
        QueryIntent(metric="top_users_by_completed_revenue"),
    )

    assert "users.id AS user_id" in compiled.sql
    assert "ORDER BY top_users_by_completed_revenue DESC" in compiled.sql
    assert compiled.sql.endswith("LIMIT 10")
    assert compiled.dimensions == ("user_id",)


def test_compile_query_rejects_excessive_limit():
    """Tests structured intents cannot request unbounded result limits."""
    contract = load_contract()

    with pytest.raises(CompileError, match="must not exceed 1000"):
        compile_query(
            contract,
            QueryIntent(metric="top_users_by_completed_revenue", limit=1001),
        )


def test_compile_query_rejects_unsupported_metric():
    """Tests out-of-contract metrics do not compile."""
    contract = load_contract()

    with pytest.raises(CompileError, match="unsupported metric"):
        compile_query(contract, QueryIntent(metric="gross_margin"))


def test_compile_query_rejects_unsupported_dimension():
    """Tests dimensions outside metric coverage do not compile."""
    contract = load_contract()

    with pytest.raises(CompileError, match="not allowed"):
        compile_query(
            contract,
            QueryIntent(metric="completed_order_count", dimensions=("user_id",)),
        )


def test_compile_query_rejects_unsupported_filter_operator():
    """Tests filters must use the metric allowlisted operators."""
    contract = load_contract()

    with pytest.raises(CompileError, match="operator != is not allowed"):
        compile_query(
            contract,
            QueryIntent(
                metric="completed_order_count",
                filters=(IntentFilter("country", "!=", "US"),),
            ),
        )


def test_compile_query_rejects_unsupported_filter_dimension():
    """Tests filters outside metric coverage do not compile."""
    contract = load_contract()

    with pytest.raises(CompileError, match="filter user_id is not allowed"):
        compile_query(
            contract,
            QueryIntent(
                metric="completed_order_count",
                filters=(IntentFilter("user_id", "=", 1),),
            ),
        )


@pytest.mark.parametrize("value", [[], ["US", 1]])
def test_compile_query_rejects_unsafe_in_filter_values(value):
    """Tests IN filters require non-empty values of one type."""
    contract = load_contract()

    with pytest.raises(CompileError, match="requires"):
        compile_query(
            contract,
            QueryIntent(
                metric="completed_revenue",
                filters=(IntentFilter("country", "IN", value),),
            ),
        )


@pytest.mark.parametrize("value", [None, {"country": "US"}])
def test_compile_query_rejects_unsupported_scalar_filter_values(value):
    """Tests scalar filters use only supported BigQuery parameter types."""
    contract = load_contract()

    with pytest.raises(CompileError, match="unsupported filter value type"):
        compile_query(
            contract,
            QueryIntent(
                metric="completed_revenue",
                filters=(IntentFilter("country", "=", value),),
            ),
        )


def test_validate_compiler_contract_rejects_unreachable_dimension():
    """Tests contract validation enforces join reachability."""
    contract = load_contract()
    bad_dimensions = dict(contract.dimensions)
    bad_dimensions["product_category"] = Dimension(
        name="product_category",
        label="Product category",
        description="Product category.",
        table="order_items",
        sql="order_items.product_id",
    )
    bad_contract = replace(
        contract,
        dimensions=bad_dimensions,
        metrics={
            **contract.metrics,
            "completed_order_count": contract.metrics[
                "completed_order_count"
            ].__class__(
                **{
                    **contract.metrics["completed_order_count"].__dict__,
                    "allowed_dimensions": ("product_category",),
                }
            ),
        },
    )

    with pytest.raises(ContractError, match="not reachable"):
        validate_compiler_contract(bad_contract)


def test_validate_contract_rejects_unknown_join_relationship():
    """Tests join cardinality metadata uses a supported relationship."""
    contract = load_contract()
    join = contract.joins["users__orders"]
    bad_contract = replace(
        contract,
        joins={
            **contract.joins,
            join.name: replace(join, relationship="sometimes_many"),
        },
    )

    with pytest.raises(ContractError, match="unsupported relationship"):
        validate_contract(bad_contract)


def test_validate_contract_requires_foreign_key_to_primary_key():
    """Tests declared foreign keys target the registered primary key."""
    contract = load_contract()
    orders = contract.tables["orders"]
    bad_contract = replace(
        contract,
        tables={
            **contract.tables,
            orders.name: replace(
                orders,
                foreign_keys={"user_id": "users.legacy_id"},
            ),
        },
    )

    with pytest.raises(ContractError, match="must reference the primary key"):
        validate_contract(bad_contract)


def test_validate_compiler_contract_rejects_sum_dimension_with_join_fan_out():
    """Tests additive metrics cannot traverse a fan-out join."""
    contract = load_contract()
    metric = contract.metrics["completed_revenue"]
    bad_contract = replace(
        contract,
        metrics={
            **contract.metrics,
            metric.name: replace(
                metric,
                base_table="users",
                sql="users.id",
                allowed_dimensions=("order_status",),
                allowed_filters={},
                join_path=("users__orders",),
            ),
        },
    )

    with pytest.raises(ContractError, match="introduces fan-out"):
        validate_compiler_contract(bad_contract)


def test_validate_compiler_contract_uses_join_order_for_fan_out():
    """Tests a later safe route cannot hide the compiler's earlier fan-out path."""
    contract = load_contract()
    metric = contract.metrics["completed_revenue"]
    item_dimension = Dimension(
        name="item_id",
        label="Item ID",
        description="Order item identifier.",
        table="order_items",
        sql="order_items.id",
    )
    safe_join = Join(
        name="users__items_safe",
        left="users",
        right="order_items",
        on="users.id = order_items.user_id",
        relationship="one_to_one",
    )
    bad_contract = replace(
        contract,
        joins={**contract.joins, safe_join.name: safe_join},
        dimensions={**contract.dimensions, item_dimension.name: item_dimension},
        metrics={
            **contract.metrics,
            metric.name: replace(
                metric,
                base_table="users",
                sql="users.id",
                allowed_dimensions=(item_dimension.name,),
                allowed_filters={},
                join_path=(
                    "users__orders",
                    safe_join.name,
                ),
            ),
        },
    )

    with pytest.raises(ContractError, match="introduces fan-out"):
        validate_compiler_contract(bad_contract)


def test_validate_compiler_contract_rejects_out_of_order_join_path():
    """Tests validation rejects paths the ordered compiler cannot emit."""
    contract = load_contract()
    metric = contract.metrics["completed_revenue"]
    item_dimension = Dimension(
        name="item_id",
        label="Item ID",
        description="Order item identifier.",
        table="order_items",
        sql="order_items.id",
    )
    bad_contract = replace(
        contract,
        dimensions={**contract.dimensions, item_dimension.name: item_dimension},
        metrics={
            **contract.metrics,
            metric.name: replace(
                metric,
                base_table="users",
                allowed_dimensions=(item_dimension.name,),
                allowed_filters={},
                join_path=("orders__order_items", "users__orders"),
            ),
        },
    )

    with pytest.raises(ContractError, match="not reachable"):
        validate_compiler_contract(bad_contract)


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"required_dimensions": ("user_id",), "allowed_dimensions": ()}, "allowed"),
        ({"default_order_by": "random"}, "unsupported default order"),
        ({"default_limit": 0}, "between 1 and 1000"),
        ({"default_limit": 1001}, "between 1 and 1000"),
    ],
)
def test_validate_compiler_contract_rejects_invalid_metric_defaults(changes, message):
    """Tests metric defaults are valid before runtime compilation."""
    contract = load_contract()
    metric = contract.metrics["top_users_by_completed_revenue"]
    bad_contract = replace(
        contract,
        metrics={**contract.metrics, metric.name: replace(metric, **changes)},
    )

    with pytest.raises(ContractError, match=message):
        validate_compiler_contract(bad_contract)
