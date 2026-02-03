"""Admin tools for managing Conversational Analytics agents."""

import logging
import os

from dotenv import load_dotenv
from google.cloud import geminidataanalytics_v1beta as geminidataanalytics
from google.protobuf import field_mask_pb2

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT")
LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION", "global")
DATASET_ID = os.getenv("BIGQUERY_DATASET_ID")
AGENT_A_ID = os.getenv("AGENT_ORDERS_ID")
AGENT_B_ID = os.getenv("AGENT_INVENTORY_ID")


def get_bq_refs(tables: list[str]) -> list[geminidataanalytics.BigQueryTableReference]:
    """Construct BigQuery table references.

    Args:
        tables: List of table IDs.

    Returns:
        List of BigQueryTableReference objects.
    """
    return [
        geminidataanalytics.BigQueryTableReference(
            project_id=PROJECT_ID, dataset_id=DATASET_ID, table_id=table
        )
        for table in tables
    ]


def update_agent_a(client: geminidataanalytics.DataAgentServiceClient) -> None:
    """Update Agent A with order and user context.

    Args:
        client: DataAgentServiceClient instance.
    """
    logger.info(f"Updating Agent A: {AGENT_A_ID}...")
    tables = ["users", "orders", "order_items", "events"]
    bq_refs = get_bq_refs(tables)

    datasource_references = geminidataanalytics.DatasourceReferences(
        bq=geminidataanalytics.BigQueryTableReferences(table_references=bq_refs)
    )

    published_context = geminidataanalytics.Context(
        system_instruction=(
            "You are an expert in Order and User behavior analysis. "
            "Focus on customer journeys, order statuses, and site events."
        ),
        datasource_references=datasource_references,
    )

    agent = geminidataanalytics.DataAgent(
        name=client.data_agent_path(PROJECT_ID, LOCATION, AGENT_A_ID),
        data_analytics_agent=geminidataanalytics.DataAnalyticsAgent(
            published_context=published_context
        ),
        description="Specialized agent for Orders and Users.",
    )

    update_mask = field_mask_pb2.FieldMask(
        paths=["description", "data_analytics_agent.published_context"]
    )

    request = geminidataanalytics.UpdateDataAgentRequest(
        data_agent=agent,
        update_mask=update_mask,
    )

    operation = client.update_data_agent(request=request)
    result = operation.result()
    logger.info(f"Agent A updated successfully: {result.name}")


def create_agent_b(client: geminidataanalytics.DataAgentServiceClient) -> None:
    """Create Agent B with inventory and product context.

    Args:
        client: DataAgentServiceClient instance.
    """
    logger.info(f"Creating Agent B: {AGENT_B_ID}...")
    tables = ["products", "inventory_items", "distribution_centers"]
    bq_refs = get_bq_refs(tables)

    datasource_references = geminidataanalytics.DatasourceReferences(
        bq=geminidataanalytics.BigQueryTableReferences(table_references=bq_refs)
    )

    published_context = geminidataanalytics.Context(
        system_instruction=(
            "You are an expert in Inventory and Product logistics. "
            "Focus on stock levels, product catalog, and distribution efficiency."
        ),
        datasource_references=datasource_references,
    )

    agent = geminidataanalytics.DataAgent(
        data_analytics_agent=geminidataanalytics.DataAnalyticsAgent(
            published_context=published_context
        ),
        description="Specialized agent for Inventory and Products.",
    )

    request = geminidataanalytics.CreateDataAgentRequest(
        parent=f"projects/{PROJECT_ID}/locations/{LOCATION}",
        data_agent_id=AGENT_B_ID,
        data_agent=agent,
    )

    try:
        operation = client.create_data_agent(request=request)
        result = operation.result()
        logger.info(f"Agent B created successfully: {result.name}")
    except Exception as e:
        if "already exists" in str(e).lower():
            logger.info("Agent B already exists, skipping creation.")
        else:
            logger.error(f"Failed to create Agent B: {e}", exc_info=True)
            raise


def list_agents(client: geminidataanalytics.DataAgentServiceClient) -> None:
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
        logger.info(f"Agent Found - ID: {agent_id}, Description: {agent.description}")


if __name__ == "__main__":
    client = geminidataanalytics.DataAgentServiceClient()
    update_agent_a(client)
    create_agent_b(client)
    list_agents(client)
