"""Tests for the Froyo Lakehouse CA agent definition."""

from __future__ import annotations

from config.agent_definition import (
    LakehouseConfig,
    build_agent_definition,
)

_CONFIG = LakehouseConfig(
    project_id="demo-project",
    native_dataset="froyo_demo_ue4",
    federated_catalog="demo_glue_cat",
    glue_database="froyo_lakehouse",
    loyalty_table="global_loyalty",
    sales_table="sales_history",
)


def test_federated_dataset_id_is_catalog_dot_namespace():
    """Federated refs must use the P.C.N.T catalog.namespace dataset id."""
    assert _CONFIG.federated_dataset_id == "demo_glue_cat.froyo_lakehouse"


def test_agent_spans_native_and_federated_tables():
    """The agent covers the four native tables plus the two AWS Iceberg tables."""
    definition = build_agent_definition(_CONFIG, "froyo_lakehouse_analyst")

    refs = {(t.dataset_id, t.table_id) for t in definition.tables}
    assert refs == {
        ("froyo_demo_ue4", "products"),
        ("froyo_demo_ue4", "recipes"),
        ("froyo_demo_ue4", "ingredient_allergens"),
        ("froyo_demo_ue4", "product_allergens"),
        ("demo_glue_cat.froyo_lakehouse", "global_loyalty"),
        ("demo_glue_cat.froyo_lakehouse", "sales_history"),
    }


def test_agent_id_is_applied():
    """The provided agent id is carried onto the definition."""
    definition = build_agent_definition(_CONFIG, "custom_agent_id")
    assert definition.agent_id == "custom_agent_id"


def test_system_instruction_encodes_soy_exclusion_rule():
    """The soy-exclusion safety rule must be present in the instruction."""
    definition = build_agent_definition(_CONFIG, "froyo_lakehouse_analyst")
    instruction = definition.system_instruction.lower()

    assert "soy" in instruction
    assert "soy_sensitive_flag" in instruction
    assert "midnight base 204" in instruction


def test_system_instruction_names_cross_cloud_sources():
    """The instruction should reference both native and federated sources."""
    definition = build_agent_definition(_CONFIG, "froyo_lakehouse_analyst")
    instruction = definition.system_instruction

    assert "demo-project.froyo_demo_ue4.product_allergens" in instruction
    assert "demo-project.demo_glue_cat.froyo_lakehouse.global_loyalty" in instruction
    assert "demo-project.demo_glue_cat.froyo_lakehouse.sales_history" in instruction
