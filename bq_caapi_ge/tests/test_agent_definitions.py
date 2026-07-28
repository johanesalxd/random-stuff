"""Tests for shared CA data-agent definitions."""

from __future__ import annotations

import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from config.agent_definitions import (  # noqa: E402
    AGENT_DEFINITIONS,
    unique_table_ids,
)


def _agent_by_env_id(env_agent_id: str):
    return next(
        agent for agent in AGENT_DEFINITIONS if agent.env_agent_id == env_agent_id
    )


def test_semantic_ca_agent_spans_full_thelook_dataset():
    """Tests the fallback agent is dataset-wide, not a domain subset."""
    orders = _agent_by_env_id("AGENT_ORDERS_ID")
    inventory = _agent_by_env_id("AGENT_INVENTORY_ID")
    semantic_ca = _agent_by_env_id("AGENT_SEMANTIC_CA_ID")

    assert semantic_ca.default_agent_id == "semantic_ca_agent"
    # The fallback must cover every table the narrow specialists cover.
    assert set(semantic_ca.tables) == set(orders.tables) | set(inventory.tables)
    assert set(semantic_ca.tables) >= set(orders.tables)
    assert set(semantic_ca.tables) >= set(inventory.tables)


def test_semantic_ca_agent_adds_no_new_enrichment_tables():
    """Tests the wide agent reuses existing tables, so enrichment scope is stable."""
    orders = _agent_by_env_id("AGENT_ORDERS_ID")
    inventory = _agent_by_env_id("AGENT_INVENTORY_ID")

    assert set(unique_table_ids()) == set(orders.tables) | set(inventory.tables)
