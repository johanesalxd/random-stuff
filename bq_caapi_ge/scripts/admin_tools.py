"""Admin tools for managing Conversational Analytics agents.

Creates or updates CA API Data Agents for the thelook_ecommerce demo:
  - Orders & Users agent (customer journeys, order statuses, site events)
  - Inventory & Products agent (stock levels, product catalog, distribution)

Idempotent: safe to run repeatedly. Creates agents on first run, updates
existing agents on subsequent runs.

Usage::

    export GOOGLE_CLOUD_PROJECT=<your-project>
    uv run python scripts/admin_tools.py
"""

from __future__ import annotations

import logging
import os

from dotenv import load_dotenv
from google.cloud import geminidataanalytics_v1beta as geminidataanalytics
from google.protobuf import field_mask_pb2

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT")
LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION", "global")
DATASET_ID = os.getenv("BIGQUERY_DATASET_ID")
AGENT_ORDERS_ID = os.getenv("AGENT_ORDERS_ID")
AGENT_INVENTORY_ID = os.getenv("AGENT_INVENTORY_ID")


def get_bq_refs(
    tables: list[str],
) -> list[geminidataanalytics.BigQueryTableReference]:
    """Construct BigQuery table references.

    Args:
        tables: List of table IDs within the configured dataset.

    Returns:
        List of BigQueryTableReference objects.
    """
    return [
        geminidataanalytics.BigQueryTableReference(
            project_id=PROJECT_ID, dataset_id=DATASET_ID, table_id=table
        )
        for table in tables
    ]


def upsert_agent(
    client: geminidataanalytics.DataAgentServiceClient,
    agent_id: str,
    description: str,
    tables: list[str],
    system_instruction: str,
) -> None:
    """Create a CA API Data Agent, or update it if it already exists.

    Args:
        client: DataAgentServiceClient instance.
        agent_id: Unique agent identifier.
        description: Human-readable agent description.
        tables: List of BQ table names for this agent.
        system_instruction: System prompt for the agent.
    """
    bq_refs = get_bq_refs(tables)

    datasource_references = geminidataanalytics.DatasourceReferences(
        bq=geminidataanalytics.BigQueryTableReferences(table_references=bq_refs)
    )

    published_context = geminidataanalytics.Context(
        system_instruction=system_instruction,
        datasource_references=datasource_references,
    )

    agent = geminidataanalytics.DataAgent(
        data_analytics_agent=geminidataanalytics.DataAnalyticsAgent(
            published_context=published_context
        ),
        description=description,
    )

    # Try create first.
    logger.info("Creating agent: %s", agent_id)
    request = geminidataanalytics.CreateDataAgentRequest(
        parent=f"projects/{PROJECT_ID}/locations/{LOCATION}",
        data_agent_id=agent_id,
        data_agent=agent,
    )

    try:
        operation = client.create_data_agent(request=request)
        result = operation.result()
        logger.info("Agent created: %s", result.name)
    except Exception as e:
        if "already exists" not in str(e).lower():
            logger.error("Failed to create agent %s", agent_id, exc_info=True)
            raise

        # Agent exists -- update instead.
        logger.info("Agent %s already exists, updating...", agent_id)
        agent.name = client.data_agent_path(PROJECT_ID, LOCATION, agent_id)

        update_mask = field_mask_pb2.FieldMask(
            paths=["description", "data_analytics_agent.published_context"]
        )
        update_request = geminidataanalytics.UpdateDataAgentRequest(
            data_agent=agent,
            update_mask=update_mask,
        )
        try:
            operation = client.update_data_agent(request=update_request)
            result = operation.result()
            logger.info("Agent updated: %s", result.name)
        except Exception as update_err:
            if "soft deleted" in str(update_err).lower():
                logger.warning(
                    "Agent %s is soft-deleted. Waiting 60s for deletion to "
                    "complete before retrying create...",
                    agent_id,
                )
                import time

                time.sleep(60)
                operation = client.create_data_agent(request=request)
                result = operation.result()
                logger.info("Agent created (after soft-delete wait): %s", result.name)
            else:
                raise


def list_agents(
    client: geminidataanalytics.DataAgentServiceClient,
) -> None:
    """List all agents in the project.

    Args:
        client: DataAgentServiceClient instance.
    """
    logger.info("Listing all agents in project...")
    request = geminidataanalytics.ListDataAgentsRequest(
        parent=f"projects/{PROJECT_ID}/locations/{LOCATION}",
    )
    page_result = client.list_data_agents(request=request)
    for agent in page_result:
        agent_id = agent.name.split("/")[-1]
        logger.info(
            "Agent Found - ID: %s, Description: %s", agent_id, agent.description
        )


def main() -> None:
    """Create or update all demo agents."""
    if not PROJECT_ID:
        raise ValueError("GOOGLE_CLOUD_PROJECT must be set.")

    client = geminidataanalytics.DataAgentServiceClient()

    upsert_agent(
        client=client,
        agent_id=AGENT_ORDERS_ID,
        description="Specialized agent for Orders and Users.",
        tables=["users", "orders", "order_items", "events"],
        system_instruction=(
            "You are an expert in Order and User behavior analysis. "
            "Focus on customer journeys, order statuses, and site events."
        ),
    )

    upsert_agent(
        client=client,
        agent_id=AGENT_INVENTORY_ID,
        description="Specialized agent for Inventory and Products.",
        tables=["products", "inventory_items", "distribution_centers"],
        system_instruction=(
            "You are an expert in Inventory and Product logistics. "
            "Focus on stock levels, product catalog, and distribution efficiency."
        ),
    )

    list_agents(client)


if __name__ == "__main__":
    main()
