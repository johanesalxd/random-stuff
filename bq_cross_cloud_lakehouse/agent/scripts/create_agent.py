"""Create or update the Froyo Lakehouse CA API data agent.

Provisions a single Conversational Analytics API data agent that spans the
native BigQuery knowledge tables and the AWS-federated Iceberg tables of the
cross-cloud lakehouse demo. Federated tables are referenced with the four-part
P.C.N.T syntax (dataset id = ``<catalog>.<namespace>``).

Idempotent: creates the agent on first run, updates it on subsequent runs.

Usage::

    cp .env.example .env      # then edit
    uv run python scripts/create_agent.py
"""

from __future__ import annotations

import logging
import os
import sys
import time
from pathlib import Path

from google.cloud import geminidataanalytics_v1beta as geminidataanalytics
from google.protobuf import field_mask_pb2

_AGENT_ROOT = Path(__file__).resolve().parents[1]
if str(_AGENT_ROOT) not in sys.path:
    sys.path.insert(0, str(_AGENT_ROOT))

from config.agent_definition import (
    AgentDefinition,
    build_agent_definition,
    load_lakehouse_config,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

SOFT_DELETE_WAIT_SECONDS = 60


def make_client(location: str) -> geminidataanalytics.DataAgentServiceClient:
    """Create a CA API client bound to the correct regional endpoint.

    Args:
        location: CA API resource location (for example ``global`` or
            ``us-east4``).

    Returns:
        A DataAgentServiceClient targeting the matching endpoint.
    """
    if not location or location == "global":
        return geminidataanalytics.DataAgentServiceClient()

    endpoint = f"geminidataanalytics.{location}.rep.googleapis.com"
    if "-" in location:
        # Regional (not multi-region) endpoints use a different host form.
        endpoint = f"geminidataanalytics-{location}.googleapis.com"
    return geminidataanalytics.DataAgentServiceClient(
        client_options={"api_endpoint": endpoint}
    )


def build_bq_references(
    project_id: str,
    definition: AgentDefinition,
) -> list[geminidataanalytics.BigQueryTableReference]:
    """Construct BigQuery table references for the agent.

    Args:
        project_id: GCP project id.
        definition: The agent definition holding table references.

    Returns:
        List of BigQueryTableReference protos. Federated tables carry a
        ``<catalog>.<namespace>`` dataset id (P.C.N.T).
    """
    return [
        geminidataanalytics.BigQueryTableReference(
            project_id=project_id,
            dataset_id=table.dataset_id,
            table_id=table.table_id,
        )
        for table in definition.tables
    ]


def upsert_agent(
    client: geminidataanalytics.DataAgentServiceClient,
    project_id: str,
    location: str,
    definition: AgentDefinition,
) -> None:
    """Create the data agent, or update it if it already exists.

    Args:
        client: DataAgentServiceClient instance.
        project_id: GCP project id.
        location: CA API resource location.
        definition: The agent definition to apply.
    """
    bq_refs = build_bq_references(project_id, definition)
    datasource_references = geminidataanalytics.DatasourceReferences(
        bq=geminidataanalytics.BigQueryTableReferences(table_references=bq_refs)
    )
    published_context = geminidataanalytics.Context(
        system_instruction=definition.system_instruction,
        datasource_references=datasource_references,
    )
    agent = geminidataanalytics.DataAgent(
        data_analytics_agent=geminidataanalytics.DataAnalyticsAgent(
            published_context=published_context
        ),
        description=definition.description,
    )

    request = geminidataanalytics.CreateDataAgentRequest(
        parent=f"projects/{project_id}/locations/{location}",
        data_agent_id=definition.agent_id,
        data_agent=agent,
    )

    logger.info("Creating agent: %s", definition.agent_id)
    try:
        result = client.create_data_agent(request=request).result()
        logger.info("Agent created: %s", result.name)
        return
    except Exception as e:  # CA API raises broad errors here.
        if "already exists" not in str(e).lower():
            logger.exception("Failed to create agent %s", definition.agent_id)
            raise

    logger.info("Agent %s already exists, updating...", definition.agent_id)
    agent.name = client.data_agent_path(project_id, location, definition.agent_id)
    update_request = geminidataanalytics.UpdateDataAgentRequest(
        data_agent=agent,
        update_mask=field_mask_pb2.FieldMask(
            paths=["description", "data_analytics_agent.published_context"]
        ),
    )
    try:
        result = client.update_data_agent(request=update_request).result()
        logger.info("Agent updated: %s", result.name)
    except Exception as update_err:
        if "soft deleted" not in str(update_err).lower():
            raise
        logger.warning(
            "Agent %s is soft-deleted. Waiting %ds before recreating...",
            definition.agent_id,
            SOFT_DELETE_WAIT_SECONDS,
        )
        time.sleep(SOFT_DELETE_WAIT_SECONDS)
        result = client.create_data_agent(request=request).result()
        logger.info("Agent created (after soft-delete wait): %s", result.name)


def list_agents(
    client: geminidataanalytics.DataAgentServiceClient,
    project_id: str,
    location: str,
) -> None:
    """Log all data agents in the project/location.

    Args:
        client: DataAgentServiceClient instance.
        project_id: GCP project id.
        location: CA API resource location.
    """
    logger.info("Listing data agents in projects/%s/locations/%s", project_id, location)
    request = geminidataanalytics.ListDataAgentsRequest(
        parent=f"projects/{project_id}/locations/{location}",
    )
    for agent in client.list_data_agents(request=request):
        logger.info(
            "Agent found - id=%s description=%s",
            agent.name.split("/")[-1],
            agent.description,
        )


def main() -> None:
    """Create or update the Froyo Lakehouse CA data agent."""
    config = load_lakehouse_config()
    location = os.getenv("GOOGLE_CLOUD_LOCATION", "global")
    agent_id = os.getenv("AGENT_ID", "froyo_lakehouse_analyst")

    definition = build_agent_definition(config, agent_id)

    logger.info(
        "Provisioning agent '%s' over %d tables (project=%s, location=%s).",
        agent_id,
        len(definition.tables),
        config.project_id,
        location,
    )
    for table in definition.tables:
        logger.info(
            "  table: %s.%s.%s", config.project_id, table.dataset_id, table.table_id
        )

    client = make_client(location)
    upsert_agent(client, config.project_id, location, definition)
    list_agents(client, config.project_id, location)


if __name__ == "__main__":
    main()
