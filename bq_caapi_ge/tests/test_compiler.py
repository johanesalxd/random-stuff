"""Tests for semantic.compiler Tier-1 deterministic contract compiler."""

from __future__ import annotations

import dataclasses
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pytest  # noqa: E402

from semantic.compiler import (  # noqa: E402
    CompiledMetricQuery,
    CoverageError,
    FilterClause,
    compile_metric_query,
)
from semantic.registry import load_contract  # noqa: E402
from semantic.types import Metric  # noqa: E402


@pytest.fixture
def orders_contract():
    return load_contract("config/semantic_contracts/thelook_orders.yaml")


@pytest.fixture
def inventory_contract():
    return load_contract("config/semantic_contracts/thelook_inventory.yaml")


def test_compile_filter_only_scalar_query(orders_contract) -> None:
    res = compile_metric_query(
        orders_contract,
        metric_id="completed_revenue",
        filters=[FilterClause("country", "=", ("United States",))],
    )
    assert isinstance(res, CompiledMetricQuery)
    assert res.metric_id == "completed_revenue"
    assert res.group_by_dimensions == ()
    assert res.filter_dimensions == ("country",)

    # 1-column output: no group by dimensions in SELECT
    assert "SUM(order_items.sale_price) AS completed_revenue" in res.sql
    assert "country AS country" not in res.sql
    assert "GROUP BY" not in res.sql
    assert "WHERE order_items.status = 'Complete' AND users.country = 'United States'" in res.sql


def test_compile_with_group_by(orders_contract) -> None:
    res = compile_metric_query(
        orders_contract,
        metric_id="completed_revenue",
        group_by_dimension_ids=["country"],
    )
    assert res.group_by_dimensions == ("country",)
    assert "users.country AS country" in res.sql
    assert "SUM(order_items.sale_price) AS completed_revenue" in res.sql
    assert "GROUP BY users.country" in res.sql
    assert "ORDER BY completed_revenue DESC, country" in res.sql


def test_compile_active_buyer_rate_left_join(orders_contract) -> None:
    # 1:N fan-out join path allowed for COUNT(DISTINCT) ratio
    res = compile_metric_query(
        orders_contract,
        metric_id="active_buyer_rate",
        group_by_dimension_ids=["country"],
    )
    assert "LEFT JOIN `bigquery-public-data.thelook_ecommerce.orders` AS orders" in res.sql
    assert "SAFE_DIVIDE(COUNT(DISTINCT CASE WHEN orders.status = 'Complete' THEN orders.user_id END)" in res.sql
    assert "NULLIF(COUNT(DISTINCT users.id), 0)" in res.sql


def test_compile_fanout_rejection_for_sum(orders_contract) -> None:
    # Create invalid metric where base_table=users attempts 1:N join on SUM
    bad_metrics = dict(orders_contract.metrics)
    bad_metrics["bad_sum"] = Metric(
        name="bad_sum",
        label="Bad Sum",
        description="Fanout sum",
        type="sum",
        base_table="users",
        allowed_dimensions=("country",),
        join_path=("users__orders",),
        allowed_filters={"country": ("=",)},
        sql="orders.order_id",
    )
    invalid_contract = dataclasses.replace(orders_contract, metrics=bad_metrics)

    with pytest.raises(CoverageError, match="Join traversal introduces 1:N/M:N fan-out"):
        compile_metric_query(invalid_contract, metric_id="bad_sum")


def test_compile_compound_ratio_fanout_rejection(orders_contract) -> None:
    bad_metrics = dict(orders_contract.metrics)
    bad_metrics["compound_ratio"] = Metric(
        name="compound_ratio",
        label="Compound ratio",
        description="Compound ratio on fanout",
        type="ratio",
        base_table="users",
        numerator_sql="COUNT(DISTINCT orders.user_id) + SUM(orders.order_id)",
        denominator_sql="COUNT(DISTINCT users.id)",
        allowed_dimensions=("country",),
        join_path=("users__orders",),
        allowed_filters={"country": ("=",)},
    )
    invalid_contract = dataclasses.replace(orders_contract, metrics=bad_metrics)
    with pytest.raises(CoverageError, match="Join traversal introduces 1:N/M:N fan-out"):
        compile_metric_query(invalid_contract, metric_id="compound_ratio")


def test_compile_ratio_filter_on_fanout_rejection(orders_contract) -> None:
    # Adding an allowed filter on orders to active_buyer_rate should be rejected because orders is reached via 1:N fanout
    bad_metrics = dict(orders_contract.metrics)
    bad_metrics["active_buyer_rate_filtered"] = Metric(
        name="active_buyer_rate_filtered",
        label="Active buyer rate with order filter",
        description="Invalid filter on fanout",
        type="ratio",
        base_table="users",
        numerator_sql="COUNT(DISTINCT CASE WHEN orders.status = 'Complete' THEN orders.user_id END)",
        denominator_sql="COUNT(DISTINCT users.id)",
        allowed_dimensions=("country",),
        join_path=("users__orders",),
        allowed_filters={"order_status": ("=",), "country": ("=",)},
    )
    invalid_contract = dataclasses.replace(orders_contract, metrics=bad_metrics)

    with pytest.raises(CoverageError, match="would shrink ratio denominator"):
        compile_metric_query(
            invalid_contract,
            metric_id="active_buyer_rate_filtered",
            filters=[FilterClause("order_status", "=", ("Complete",))],
        )


def test_compile_safe_parent_filter_on_aov(orders_contract) -> None:
    # average_order_value (base: order_items) joining N:1 up to orders and users.
    # Filtering on users.country is safe (no fanout table).
    res = compile_metric_query(
        orders_contract,
        metric_id="average_order_value",
        filters=[FilterClause("country", "=", ("United States",))],
    )
    assert "users.country = 'United States'" in res.sql
    assert "LEFT JOIN" not in res.sql
    assert "INNER JOIN `bigquery-public-data.thelook_ecommerce.users`" in res.sql


def test_compile_literal_escaping_obrien(orders_contract) -> None:
    res = compile_metric_query(
        orders_contract,
        metric_id="completed_revenue",
        filters=[FilterClause("country", "=", ("O'Brien",))],
    )
    assert r"'O\'Brien'" in res.sql


def test_compile_literal_validation_rejections(orders_contract) -> None:
    with pytest.raises(CoverageError, match="Boolean literals are not supported"):
        compile_metric_query(
            orders_contract,
            metric_id="completed_revenue",
            filters=[FilterClause("country", "=", (True,))],  # type: ignore[arg-type]
        )

    with pytest.raises(CoverageError, match="NaN or Infinity"):
        compile_metric_query(
            orders_contract,
            metric_id="completed_revenue",
            filters=[FilterClause("country", "=", (float("nan"),))],
        )

    with pytest.raises(CoverageError, match="None literal"):
        compile_metric_query(
            orders_contract,
            metric_id="completed_revenue",
            filters=[FilterClause("country", "=", (None,))],  # type: ignore[arg-type]
        )


def test_compile_in_operator(orders_contract) -> None:
    res = compile_metric_query(
        orders_contract,
        metric_id="completed_revenue",
        filters=[FilterClause("country", "IN", ("United States", "Japan", "United Kingdom"))],
    )
    assert "users.country IN ('United States', 'Japan', 'United Kingdom')" in res.sql


def test_compile_inventory_metrics(inventory_contract) -> None:
    res = compile_metric_query(
        inventory_contract,
        metric_id="available_inventory_item_count",
        group_by_dimension_ids=["product_brand"],
    )
    assert "COUNT(DISTINCT inventory_items.id) AS available_inventory_item_count" in res.sql
    assert "inventory_items.sold_at IS NULL" in res.sql
    assert "products.brand AS product_brand" in res.sql


def test_compile_contradictory_required_filter_rejection(orders_contract) -> None:
    with pytest.raises(CoverageError):
        compile_metric_query(
            orders_contract,
            metric_id="completed_order_count",
            filters=[FilterClause("order_status", "=", ("Cancelled",))],
        )

    with pytest.raises(CoverageError):
        compile_metric_query(
            orders_contract,
            metric_id="completed_order_count",
            filters=[FilterClause("order_status", "!=", ("Complete",))],
        )

    with pytest.raises(CoverageError):
        compile_metric_query(
            orders_contract,
            metric_id="completed_order_count",
            filters=[FilterClause("order_status", "IN", ("Cancelled", "Processing"))],
        )

    res = compile_metric_query(
        orders_contract,
        metric_id="completed_order_count",
        filters=[FilterClause("order_status", "=", ("Complete",))],
    )
    assert "orders.status = 'Complete'" in res.sql

    metric = orders_contract.metrics["completed_order_count"]
    allowed_filters = dict(metric.allowed_filters)
    allowed_filters["order_status"] = ("=", "!=", "IN")
    updated_metric = dataclasses.replace(metric, allowed_filters=allowed_filters)
    updated_metrics = dict(orders_contract.metrics)
    updated_metrics["completed_order_count"] = updated_metric
    contract_with_neq = dataclasses.replace(orders_contract, metrics=updated_metrics)

    with pytest.raises(CoverageError, match="contradicts required filter"):
        compile_metric_query(
            contract_with_neq,
            metric_id="completed_order_count",
            filters=[FilterClause("order_status", "!=", ("Complete",))],
        )
