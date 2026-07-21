"""Tests for semantic contract loading and deterministic SQL compilation."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from semantic.compiler import compile_query  # noqa: E402
from semantic.registry import load_contract, validate_contract  # noqa: E402
from semantic.types import (  # noqa: E402
    CompileError,
    ContractError,
    Dimension,
    IntentFilter,
    QueryIntent,
    SemanticContract,
)


def test_load_contract_validates_first_metrics():
    """Tests the default contract loads with the planned first metrics."""
    contract = load_contract()

    assert contract.contract_version == "thelook_ecommerce:v1"
    assert contract.certified is True
    assert set(contract.metrics) == {
        "completed_order_count",
        "completed_revenue",
        "average_order_value",
        "top_users_by_completed_revenue",
    }


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
            "FROM `thelook_ecommerce.orders` AS orders",
            "LEFT JOIN `thelook_ecommerce.users` AS users",
            "  ON users.id = orders.user_id",
            "WHERE",
            "  orders.status = 'Complete'",
            "GROUP BY 1",
            "ORDER BY country",
        ]
    )
    assert first.certified is True
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


def test_validate_contract_rejects_unreachable_dimension():
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
    bad_contract = SemanticContract(
        version=contract.version,
        dataset=contract.dataset,
        owner=contract.owner,
        certified=contract.certified,
        tables=contract.tables,
        joins=contract.joins,
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
        validate_contract(bad_contract)
