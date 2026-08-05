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


def test_agent_definitions_contain_only_domain_baselines():
    """Tests the remaining CA agents are the two domain baselines."""
    orders = _agent_by_env_id("AGENT_ORDERS_ID")
    inventory = _agent_by_env_id("AGENT_INVENTORY_ID")

    assert len(AGENT_DEFINITIONS) == 2
    assert orders.default_agent_id == "order_user_agent"
    assert inventory.default_agent_id == "inventory_product_agent"
    assert set(unique_table_ids()) == set(orders.tables) | set(inventory.tables)
