"""Cleanup utility for removing specific agents and listing all agents with details."""

import logging
import os

from dotenv import load_dotenv
from google.cloud import geminidataanalytics_v1beta as geminidataanalytics

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


def cleanup_agents(
    client: geminidataanalytics.DataAgentServiceClient, agent_ids: list[str]
) -> None:
    """Delete specific data agents.

    Args:
        client: DataAgentServiceClient instance.
        agent_ids: List of agent IDs to delete.
    """
    for agent_id in agent_ids:
        name = client.data_agent_path(PROJECT_ID, LOCATION, agent_id)
        logger.info(f"Deleting agent: {agent_id}...")
        try:
            client.delete_data_agent(name=name)
            logger.info(f"Successfully deleted {agent_id}")
        except Exception as e:
            logger.error(f"Failed to delete {agent_id}: {e}", exc_info=True)


def list_all_agents_with_details(
    client: geminidataanalytics.DataAgentServiceClient,
) -> None:
    """List all agents in the project with their full configuration details.

    Args:
        client: DataAgentServiceClient instance.
    """
    logger.info("--- Current Data Agents in Project ---")
    request = geminidataanalytics.ListDataAgentsRequest(
        parent=f"projects/{PROJECT_ID}/locations/{LOCATION}",
    )
    page_result = client.list_data_agents(request=request)

    for agent in page_result:
        agent_id = agent.name.split("/")[-1]
        logger.info(f"Agent ID: {agent_id}")
        logger.info(f"Display Name: {agent.display_name or 'N/A'}")
        logger.info(f"Description: {agent.description or 'No description'}")

        ctx = agent.data_analytics_agent.published_context
        logger.info(f"System Instruction: {ctx.system_instruction[:100]}...")

        if ctx.datasource_references.bq:
            tables = [
                f"{t.dataset_id}.{t.table_id}"
                for t in ctx.datasource_references.bq.table_references
            ]
            logger.info(f"Tables: {', '.join(tables)}")

        if ctx.datasource_references.looker:
            explores = [
                f"{e.lookml_model}.{e.explore}"
                for e in ctx.datasource_references.looker.explore_references
            ]
            logger.info(f"Looker Explores: {', '.join(explores)}")


if __name__ == "__main__":
    client = geminidataanalytics.DataAgentServiceClient()

    # Define agents to remove if any
    agents_to_remove = []
    if agents_to_remove:
        cleanup_agents(client, agents_to_remove)

    # List with details
    list_all_agents_with_details(client)
