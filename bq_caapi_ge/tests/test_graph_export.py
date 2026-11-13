"""Tests for semantic.graph_export Property Graph, constraints, and verified queries exporter."""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pytest  # noqa: E402

from semantic.graph_export import (  # noqa: E402
    GraphExportError,
    GraphExportResult,
    build_data_agent_datasource_references,
    export_fk_constraints_ddl,
    export_property_graph_ddl,
    export_verified_queries,
)
from semantic.registry import load_contract  # noqa: E402
from semantic.types import Join, SemanticContract, Table, TableSource  # noqa: E402


@pytest.fixture
def orders_contract():
    return load_contract("config/semantic_contracts/thelook_orders.yaml")


@pytest.fixture
def inventory_contract():
    return load_contract("config/semantic_contracts/thelook_inventory.yaml")


def test_export_orders_property_graph(orders_contract) -> None:
    res = export_property_graph_ddl(
        orders_contract,
        graph_project="test-project",
        graph_dataset="test_dataset",
    )
    assert isinstance(res, GraphExportResult)
    assert res.graph_name == "thelook_orders_graph"
    assert "completed_order_count" in res.exported_metrics
    assert "completed_revenue" in res.exported_metrics
    assert "average_order_value" in res.exported_metrics

    skipped_ids = {sm.metric_id for sm in res.skipped_metrics}
    assert "top_users_by_completed_revenue" in skipped_ids
    assert "active_buyer_rate" in skipped_ids

    assert "CREATE OR REPLACE PROPERTY GRAPH `test-project.test_dataset.thelook_orders_graph`" in res.ddl
    assert "NODE TABLES (" in res.ddl
    assert "DEFAULT LABEL OPTIONS (description = 'order grain')" in res.ddl
    assert "EDGE TABLES (" in res.ddl
    assert "OrdersToUsers" in res.ddl
    assert "OrderItemsToOrders" in res.ddl


def test_export_property_graph_rejects_cycle() -> None:
    tab_a = Table(
        name="table_a",
        source=TableSource(project="p", dataset="d", table="table_a"),
        primary_key="id",
        grain="record",
        foreign_keys={"b_id": "table_b.id"},
    )
    tab_b = Table(
        name="table_b",
        source=TableSource(project="p", dataset="d", table="table_b"),
        primary_key="id",
        grain="record",
        foreign_keys={"a_id": "table_a.id"},
    )
    join_ab = Join(
        name="a__b",
        left="table_a",
        right="table_b",
        on="table_a.b_id = table_b.id",
        relationship="many_to_one",
    )
    join_ba = Join(
        name="b__a",
        left="table_b",
        right="table_a",
        on="table_b.a_id = table_a.id",
        relationship="many_to_one",
    )
    contract = SemanticContract(
        id="cycle_contract",
        version=1,
        owner="test-owner",
        description="Cycle test contract",
        routing_terms=(),
        examples=(),
        tables={"table_a": tab_a, "table_b": tab_b},
        joins={"a__b": join_ab, "b__a": join_ba},
        dimensions={},
        metrics={},
    )
    with pytest.raises(GraphExportError, match="Property graph relationships contain a cycle"):
        export_property_graph_ddl(
            contract,
            graph_project="test-project",
            graph_dataset="test_dataset",
        )


def test_export_inventory_property_graph(inventory_contract) -> None:
    res = export_property_graph_ddl(
        inventory_contract,
        graph_project="test-project",
        graph_dataset="test_dataset",
    )
    assert res.graph_name == "thelook_inventory_graph"
    assert "product_count" in res.exported_metrics
    assert "available_inventory_item_count" in res.exported_metrics
    assert len(res.skipped_metrics) == 0

    assert "ProductsToDistributionCenters" in res.ddl
    assert "InventoryItemsToProducts" in res.ddl


def test_export_fk_constraints_rejects_public_data(orders_contract) -> None:
    with pytest.raises(ValueError, match="Cannot generate ALTER TABLE constraints for read-only"):
        export_fk_constraints_ddl(
            orders_contract,
            target_project="bigquery-public-data",
            target_dataset="thelook_ecommerce",
        )


def test_export_fk_constraints_rejects_invalid_identifiers(orders_contract) -> None:
    with pytest.raises(GraphExportError, match="Invalid target_project"):
        export_fk_constraints_ddl(
            orders_contract,
            target_project="invalid;project",
            target_dataset="curated_orders",
        )
    with pytest.raises(GraphExportError, match="Invalid target_dataset"):
        export_fk_constraints_ddl(
            orders_contract,
            target_project="valid_project",
            target_dataset="invalid;dataset",
        )


def test_export_fk_constraints_emits_checks_and_alters(orders_contract) -> None:
    ddl = export_fk_constraints_ddl(
        orders_contract,
        target_project="my-corp-project",
        target_dataset="curated_orders",
    )
    assert "Pre-flight: Check primary key uniqueness" in ddl
    assert "Pre-flight: Check orphans" in ddl
    assert "ALTER TABLE `my-corp-project.curated_orders.orders`" in ddl
    assert "ADD PRIMARY KEY (order_id) NOT ENFORCED" in ddl
    assert "ADD CONSTRAINT IF NOT EXISTS fk_orders_user_id_users" in ddl
    assert "FOREIGN KEY (user_id) REFERENCES `my-corp-project.curated_orders.users`(id) NOT ENFORCED" in ddl


def test_export_verified_queries(orders_contract) -> None:
    vqs = export_verified_queries(orders_contract)
    assert len(vqs) == len(orders_contract.metrics)
    metric_names = {m.name for m in orders_contract.metrics.values()}
    vq_ids = {vq.query_id for vq in vqs}
    assert metric_names == vq_ids
    vqs_by_id = {vq.query_id: vq for vq in vqs}
    assert vqs_by_id["completed_order_count"].question == "How many completed orders are there?"
    assert vqs_by_id["completed_revenue"].question == "What is the completed revenue?"
    assert vqs_by_id["average_order_value"].question == "What is the average order value?"
    assert vqs_by_id["active_buyer_rate"].question == "What is the active buyer rate?"
    assert vqs_by_id["top_users_by_completed_revenue"].question == "Show top users by completed revenue"
    for vq in vqs:
        assert vq.sql.startswith("SELECT")


def test_build_datasource_references(orders_contract) -> None:
    refs = build_data_agent_datasource_references(
        orders_contract,
        graph_project="my-project",
        graph_dataset="my_dataset",
        graph_name="orders_graph",
    )
    assert "tableReferences" in refs
    assert len(refs["tableReferences"]) == 3
    assert "propertyGraphReferences" in refs
    assert refs["propertyGraphReferences"][0]["propertyGraphId"] == "orders_graph"


def test_core_only_sys_modules_isolation() -> None:
    """Verifies that importing semantic core modules does NOT load optional-extra dependencies."""
    code = f"""
import sys
from pathlib import Path

# Add project root
sys.path.insert(0, {repr(str(PROJECT_ROOT))})

# Import all core modules
import semantic
import semantic.registry
import semantic.sql_lex
import semantic.numeric_reconcile
import semantic.compiler
import semantic.guardrails
import semantic.graph_export
import semantic.rls_impersonation

forbidden = [
    'google.adk',
    'pydantic',
    'flask',
    'google.cloud.dataplex',
    'grpc',
    'google.cloud.geminidataanalytics',
]
for mod in forbidden:
    if mod in sys.modules:
        print(f"FORBIDDEN_IMPORT: {{mod}}", file=sys.stderr)
        sys.exit(1)

print("ISOLATION_OK")
"""
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, f"Core module isolation failed: {result.stderr}"
    assert "ISOLATION_OK" in result.stdout
