"""Tests for portable semantic contract context."""

from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from semantic.context import (  # noqa: E402
    build_semantic_context,
    build_semantic_index_entry,
)
from semantic.registry import load_contract, load_contracts  # noqa: E402
from semantic.types import ContractError  # noqa: E402


def test_load_contracts_loads_multiple_domains_in_path_order(monkeypatch):
    """Tests the default registry loads both portable sample domains."""
    monkeypatch.delenv("SEMANTIC_CONTRACT_PATH", raising=False)
    contracts = load_contracts()

    assert [contract.id for contract in contracts] == [
        "thelook_inventory",
        "thelook_orders",
    ]
    assert contracts[0].tables["products"].source.qualified_name == (
        "bigquery-public-data.thelook_ecommerce.products"
    )
    assert contracts[1].tables["orders"].source.qualified_name == (
        "bigquery-public-data.thelook_ecommerce.orders"
    )
    contexts = [build_semantic_context(contract) for contract in contracts]
    assert [context["id"] for context in contexts] == [
        "thelook_inventory",
        "thelook_orders",
    ]


def test_load_contract_accepts_explicit_file(tmp_path):
    """Tests the historical single-contract loader accepts an explicit file."""
    source_path = (
        Path(__file__).resolve().parents[1]
        / "config"
        / "semantic_contracts"
        / "thelook_inventory.yaml"
    )
    configured_path = tmp_path / "inventory.yaml"
    configured_path.write_text(
        source_path.read_text(encoding="utf-8"), encoding="utf-8"
    )
    contract = load_contract(configured_path)

    assert contract.id == "thelook_inventory"


def test_load_contracts_uses_configured_file(monkeypatch, tmp_path):
    """Tests SEMANTIC_CONTRACT_PATH can select one runtime contract file."""
    source_path = (
        Path(__file__).resolve().parents[1]
        / "config"
        / "semantic_contracts"
        / "thelook_inventory.yaml"
    )
    configured_path = tmp_path / "inventory.yaml"
    configured_path.write_text(
        source_path.read_text(encoding="utf-8"), encoding="utf-8"
    )
    monkeypatch.setenv("SEMANTIC_CONTRACT_PATH", str(configured_path))

    contracts = load_contracts()

    assert [contract.id for contract in contracts] == ["thelook_inventory"]


def test_load_contract_ignores_runtime_directory_setting(monkeypatch):
    """Tests the historical loader remains coherent with runtime configuration."""
    monkeypatch.setenv(
        "SEMANTIC_CONTRACT_PATH",
        str(PROJECT_ROOT / "config" / "semantic_contracts"),
    )

    contract = load_contract()

    assert contract.id == "thelook_orders"


def test_load_contracts_rejects_duplicate_domain_ids(tmp_path):
    """Tests directories cannot contain ambiguous semantic domain IDs."""
    source_path = (
        Path(__file__).resolve().parents[1]
        / "config"
        / "semantic_contracts"
        / "thelook_orders.yaml"
    )
    content = source_path.read_text(encoding="utf-8")
    (tmp_path / "first.yaml").write_text(content, encoding="utf-8")
    (tmp_path / "second.yaml").write_text(content, encoding="utf-8")

    with pytest.raises(ContractError, match="duplicate semantic contract IDs"):
        load_contracts(tmp_path)


@pytest.mark.parametrize(
    ("replacement", "message"),
    [
        ("version: true", "version must be an integer"),
        ("version: 0", "version must be between"),
        (
            "owner: analytics-platform\nunexpected_setting: enabled",
            "unknown fields",
        ),
    ],
)
def test_load_contract_rejects_ambiguous_or_unknown_schema(
    tmp_path,
    replacement,
    message,
):
    """Tests contract typos and YAML boolean integers fail explicitly."""
    source_path = PROJECT_ROOT / "config" / "semantic_contracts" / "thelook_orders.yaml"
    content = source_path.read_text(encoding="utf-8")
    if replacement.startswith("version"):
        content = content.replace("version: 1", replacement, 1)
    else:
        content = content.replace("owner: analytics-platform", replacement, 1)
    contract_path = tmp_path / "invalid.yaml"
    contract_path.write_text(content, encoding="utf-8")

    with pytest.raises(ContractError, match=message):
        load_contract(contract_path)


def test_load_contract_rejects_duplicate_yaml_keys(tmp_path):
    """Tests duplicate YAML fields cannot silently override semantic context."""
    contract_path = tmp_path / "duplicate.yaml"
    contract_path.write_text(
        """id: first
id: second
version: 1
owner: team
description: Duplicate root key.
routing_terms: [duplicate]
tables: {}
joins: {}
dimensions: {}
metrics: {}
""",
        encoding="utf-8",
    )

    with pytest.raises(ContractError, match="duplicate key"):
        load_contract(contract_path)


@pytest.mark.parametrize(
    ("sql_value", "message"),
    [
        ("{unexpected: mapping}", "sql must be a non-empty string"),
        (f"'{'x' * 4_001}'", "sql exceeds 4000 characters"),
    ],
)
def test_load_contract_rejects_invalid_metric_expression(
    tmp_path,
    sql_value,
    message,
):
    """Tests optional SQL guidance remains bounded and JSON-safe."""
    source_path = PROJECT_ROOT / "config" / "semantic_contracts" / "thelook_orders.yaml"
    content = source_path.read_text(encoding="utf-8").replace(
        "sql: orders.order_id",
        f"sql: {sql_value}",
        1,
    )
    contract_path = tmp_path / "invalid-expression.yaml"
    contract_path.write_text(content, encoding="utf-8")

    with pytest.raises(ContractError, match=message):
        load_contract(contract_path)


def test_load_contract_rejects_non_yaml_extension(tmp_path):
    """Tests explicit contract files use the documented YAML extensions."""
    contract_path = tmp_path / "contract.txt"
    contract_path.write_text("id: example", encoding="utf-8")

    with pytest.raises(ContractError, match="must use .yaml or .yml"):
        load_contract(contract_path)


def test_build_semantic_context_is_domain_neutral_and_json_safe(monkeypatch):
    """Tests context is derived from configuration without certification state."""
    monkeypatch.delenv("SEMANTIC_CONTRACT_PATH", raising=False)
    contract = load_contract()

    context = build_semantic_context(contract)

    assert context["id"] == "thelook_orders"
    assert context["description"] == (
        "Order, customer, and completed-revenue analytics."
    )
    assert context["routing_terms"] == [
        "orders",
        "customers",
        "revenue",
        "sales",
        "average order value",
    ]
    assert context["examples"] == [
        "How many completed orders were placed by country?",
        "Which customers generated the most completed revenue?",
    ]
    assert "certified" not in context
    assert "dataset" not in context
    assert {table["name"]: table["source"] for table in context["tables"]}[
        "orders"
    ] == "bigquery-public-data.thelook_ecommerce.orders"
    assert {metric["name"] for metric in context["metrics"]} == {
        "average_order_value",
        "completed_order_count",
        "completed_revenue",
        "top_users_by_completed_revenue",
    }
    assert json.loads(json.dumps(context)) == context


def test_build_semantic_index_entry_omits_physical_expressions(monkeypatch):
    """Tests routing context contains semantics without SQL or source details."""
    monkeypatch.delenv("SEMANTIC_CONTRACT_PATH", raising=False)
    contract = load_contract()

    index_entry = build_semantic_index_entry(contract)

    serialized = json.dumps(index_entry)
    assert index_entry["id"] == contract.id
    assert index_entry["examples"] == list(contract.examples)
    assert "completed_revenue" in serialized
    assert "bigquery-public-data" not in serialized
    assert "expression" not in serialized
