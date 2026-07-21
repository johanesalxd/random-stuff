"""Minimal agent definitions for BigQuery CA API demo agents."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AgentDefinition:
    """Configuration for one CA API data agent.

    Args:
        env_agent_id: Environment variable that can override the agent ID.
        default_agent_id: Default CA API data agent ID.
        description: Human-readable agent description.
        tables: BigQuery table IDs available to the agent.
        system_instruction: Short business scope for the agent.
    """

    env_agent_id: str
    default_agent_id: str
    description: str
    tables: tuple[str, ...]
    system_instruction: str


AGENT_DEFINITIONS: tuple[AgentDefinition, ...] = (
    AgentDefinition(
        env_agent_id="AGENT_ORDERS_ID",
        default_agent_id="order_user_agent",
        description="Specialized agent for orders, users, and customer behavior.",
        tables=("users", "orders", "order_items", "events"),
        system_instruction=(
            "You are an ecommerce orders and customer behavior analyst. "
            "Focus on customer journeys, order status, web events, and "
            "order-level revenue questions."
        ),
    ),
    AgentDefinition(
        env_agent_id="AGENT_INVENTORY_ID",
        default_agent_id="inventory_product_agent",
        description="Specialized agent for inventory, products, and logistics.",
        tables=("products", "inventory_items", "distribution_centers"),
        system_instruction=(
            "You are an ecommerce inventory and logistics analyst. Focus on "
            "product catalog, stock availability, distribution centers, and "
            "inventory movement."
        ),
    ),
)


def unique_table_ids() -> list[str]:
    """Return unique table IDs referenced by all configured agents.

    Returns:
        Unique table IDs in first-seen order.
    """
    table_ids: list[str] = []
    seen: set[str] = set()
    for agent in AGENT_DEFINITIONS:
        for table in agent.tables:
            if table in seen:
                continue
            table_ids.append(table)
            seen.add(table)
    return table_ids
