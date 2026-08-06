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
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
from google.cloud import geminidataanalytics_v1beta as geminidataanalytics
from google.protobuf import field_mask_pb2

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config.agent_definitions import (  # noqa: E402
    AGENT_DEFINITIONS,
    AgentDefinition,
)
from config.ca_locations import ca_api_endpoint  # noqa: E402

load_dotenv(override=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT")
LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION", "global")
DATASET_ID = os.getenv("BIGQUERY_DATASET_ID")

# A deleted agent ID stays reserved until the soft delete completes, so a
# recreate has to wait it out.
SOFT_DELETE_WAIT_SECONDS = 60


def make_client(location: str) -> geminidataanalytics.DataAgentServiceClient:
    """Create a CA API client bound to the endpoint serving a location.

    Args:
        location: CA API resource location, for example ``global`` or
            ``asia-southeast1``.

    Returns:
        A DataAgentServiceClient targeting the matching regional endpoint.
    """
    if not location or location == "global":
        return geminidataanalytics.DataAgentServiceClient()
    return geminidataanalytics.DataAgentServiceClient(
        client_options={"api_endpoint": ca_api_endpoint(location)}
    )


def get_bq_refs(
    tables: tuple[str, ...],
) -> list[geminidataanalytics.BigQueryTableReference]:
    """Construct BigQuery table references.

    Args:
        tables: Table IDs within the configured dataset.

    Returns:
        List of BigQueryTableReference objects.
    """
    return [
        geminidataanalytics.BigQueryTableReference(
            project_id=PROJECT_ID,
            dataset_id=DATASET_ID,
            table_id=table_id,
        )
        for table_id in tables
    ]


def upsert_agent(
    client: geminidataanalytics.DataAgentServiceClient,
    agent_id: str,
    agent_definition: AgentDefinition,
) -> None:
    """Create a CA API Data Agent, or update it if it already exists.

    Args:
        client: DataAgentServiceClient instance.
        agent_id: Unique agent identifier.
        agent_definition: Agent definition with BigQuery table refs and scope.
    """
    bq_refs = get_bq_refs(agent_definition.tables)

    datasource_references = geminidataanalytics.DatasourceReferences(
        bq=geminidataanalytics.BigQueryTableReferences(table_references=bq_refs)
    )

    published_context = geminidataanalytics.Context(
        system_instruction=agent_definition.system_instruction,
        datasource_references=datasource_references,
    )

    agent = geminidataanalytics.DataAgent(
        data_analytics_agent=geminidataanalytics.DataAnalyticsAgent(
            published_context=published_context
        ),
        description=agent_definition.description,
    )

    # Try create first.
    logger.info("Creating agent: %s", agent_id)
    request = geminidataanalytics.CreateDataAgentRequest(
        parent=f"projects/{PROJECT_ID}/locations/{LOCATION}",
        data_agent_id=agent_id,
        data_agent=agent,
    )

    try:
        result = client.create_data_agent(request=request).result()
        logger.info("Agent created: %s", result.name)
        return
    except Exception as e:  # The CA API raises broad errors here.
        if "already exists" not in str(e).lower():
            logger.exception("Failed to create agent %s", agent_id)
            raise

    # Agent exists -- update instead.
    logger.info("Agent %s already exists, updating...", agent_id)
    agent.name = client.data_agent_path(PROJECT_ID, LOCATION, agent_id)
    update_request = geminidataanalytics.UpdateDataAgentRequest(
        data_agent=agent,
        update_mask=field_mask_pb2.FieldMask(
            paths=["description", "data_analytics_agent.published_context"]
        ),
    )

    try:
        result = client.update_data_agent(request=update_request).result()
        logger.info("Agent updated: %s", result.name)
        return
    except Exception as update_err:
        if "soft deleted" not in str(update_err).lower():
            raise

    logger.warning(
        "Agent %s is soft-deleted. Waiting %ds for deletion to complete before "
        "retrying create...",
        agent_id,
        SOFT_DELETE_WAIT_SECONDS,
    )
    time.sleep(SOFT_DELETE_WAIT_SECONDS)
    result = client.create_data_agent(request=request).result()
    logger.info("Agent created (after soft-delete wait): %s", result.name)


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
    if not DATASET_ID:
        raise ValueError("BIGQUERY_DATASET_ID must be set.")

    client = make_client(LOCATION)

    for agent_definition in AGENT_DEFINITIONS:
        agent_id = os.getenv(
            agent_definition.env_agent_id,
            agent_definition.default_agent_id,
        )
        if not agent_id:
            raise ValueError(f"{agent_definition.env_agent_id} must be set.")
        upsert_agent(
            client=client,
            agent_id=agent_id,
            agent_definition=agent_definition,
        )

    list_agents(client)


if __name__ == "__main__":
    main()
