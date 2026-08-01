"""Tests for the Froyo Lakehouse CA agent definition."""

from __future__ import annotations

import dataclasses

from config.agent_definition import (
    LakehouseConfig,
    build_agent_definition,
    env_flag,
)

_CONFIG = LakehouseConfig(
    project_id="demo-project",
    native_dataset="froyo_demo_ue4",
    federated_catalog="demo_glue_cat",
    glue_database="froyo_lakehouse",
    loyalty_table="global_loyalty",
    sales_table="sales_history",
)

_NO_AWS_CONFIG = dataclasses.replace(_CONFIG, no_aws=True)


def test_federated_dataset_id_is_catalog_dot_namespace():
    """Federated refs must use the P.C.N.T catalog.namespace dataset id."""
    assert _CONFIG.federated_dataset_id == "demo_glue_cat.froyo_lakehouse"


def test_agent_spans_native_and_federated_tables():
    """The agent covers the four native tables plus the two AWS Iceberg tables."""
    definition = build_agent_definition(_CONFIG, "froyo_lakehouse_agent")

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
    definition = build_agent_definition(_CONFIG, "froyo_lakehouse_agent")
    instruction = definition.system_instruction.lower()

    assert "soy" in instruction
    assert "soy_sensitive_flag" in instruction
    assert "midnight base 204" in instruction


def test_system_instruction_names_cross_cloud_sources():
    """The instruction should reference both native and federated sources."""
    definition = build_agent_definition(_CONFIG, "froyo_lakehouse_agent")
    instruction = definition.system_instruction

    assert "demo-project.froyo_demo_ue4.product_allergens" in instruction
    assert "demo-project.demo_glue_cat.froyo_lakehouse.global_loyalty" in instruction
    assert "demo-project.demo_glue_cat.froyo_lakehouse.sales_history" in instruction


def test_no_aws_collapses_analytics_tables_into_the_native_dataset():
    """In GCP-only mode loyalty and sales are ordinary native BigQuery tables."""
    definition = build_agent_definition(_NO_AWS_CONFIG, "froyo_lakehouse_agent")

    refs = {(t.dataset_id, t.table_id) for t in definition.tables}
    assert refs == {
        ("froyo_demo_ue4", "products"),
        ("froyo_demo_ue4", "recipes"),
        ("froyo_demo_ue4", "ingredient_allergens"),
        ("froyo_demo_ue4", "product_allergens"),
        ("froyo_demo_ue4", "global_loyalty"),
        ("froyo_demo_ue4", "sales_history"),
    }


def test_no_aws_instruction_drops_cross_cloud_claims():
    """The agent must not describe native tables as AWS-resident."""
    instruction = build_agent_definition(
        _NO_AWS_CONFIG, "froyo_lakehouse_agent"
    ).system_instruction

    assert "demo-project.froyo_demo_ue4.global_loyalty" in instruction
    assert "demo_glue_cat" not in instruction
    assert "AWS" not in instruction
    assert "Iceberg" not in instruction


def test_no_aws_preserves_the_soy_exclusion_rule():
    """The allergen safety rule is independent of where the tables live."""
    instruction = build_agent_definition(
        _NO_AWS_CONFIG, "froyo_lakehouse_agent"
    ).system_instruction.lower()

    assert "soy_sensitive_flag" in instruction
    assert "midnight base 204" in instruction


def test_no_aws_changes_the_agent_description():
    """The description must not advertise cross-cloud federation in GCP-only mode."""
    federated = build_agent_definition(_CONFIG, "a").description
    native_only = build_agent_definition(_NO_AWS_CONFIG, "a").description

    assert "AWS-federated" in federated
    assert "AWS" not in native_only


def test_build_agent_definition_ignores_ambient_no_aws_env(monkeypatch):
    """Mode comes from the config object, never from the process environment."""
    monkeypatch.setenv("NO_AWS", "true")
    definition = build_agent_definition(_CONFIG, "froyo_lakehouse_agent")

    refs = {t.dataset_id for t in definition.tables}
    assert "demo_glue_cat.froyo_lakehouse" in refs


def test_env_flag_accepts_the_same_spellings_as_the_shell_helper(monkeypatch):
    """Python and lib/no_aws.sh must agree on what counts as enabled."""
    for enabled in ("1", "true", "TRUE", "yes", "on", " true "):
        monkeypatch.setenv("NO_AWS", enabled)
        assert env_flag("NO_AWS") is True, enabled

    for disabled in ("0", "false", "no", "off", ""):
        monkeypatch.setenv("NO_AWS", disabled)
        assert env_flag("NO_AWS") is False, disabled

    monkeypatch.delenv("NO_AWS")
    assert env_flag("NO_AWS") is False
