"""Dataset ACL scanner using the direct BigQuery API.

Iterates through all datasets in a set of projects and reads their
access_entries (legacy ACLs). This covers permission types that Cloud
Asset Inventory does not expose:

    - Legacy READER / WRITER / OWNER bindings
    - specialGroup (projectOwners, projectReaders, etc.)
    - domain-level access
    - authorizedView, authorizedDataset, authorizedRoutine

Only dataset-level ACLs are scanned. Table and view IAM policies are
already captured by the IAM scanner via Cloud Asset Inventory.
"""

from __future__ import annotations

import logging

from google.api_core.exceptions import (
    BadRequest,
    Forbidden,
    NotFound,
    PermissionDenied,
)
from google.cloud import bigquery

from bq_discovery.models import (
    PermissionEntry,
    PermissionSource,
    ResourceType,
)
from bq_discovery.resolvers.projects import list_org_projects

logger = logging.getLogger(__name__)

# Mapping from BigQuery ACL entity_type to a normalized member type string
_ENTITY_TYPE_MAP = {
    "userByEmail": "user",
    "groupByEmail": "group",
    "specialGroup": "specialGroup",
    "domain": "domain",
    "view": "authorizedView",
    "dataset": "authorizedDataset",
    "routine": "authorizedRoutine",
    "iamMember": "iamMember",
}


def _format_table_ref(entity_id: object, prefix: str) -> str:
    """Format a table/view reference entity_id as a readable string.

    Args:
        entity_id: Dict with projectId/datasetId/tableId keys, or a string.
        prefix: Prefix to use (e.g. "view").

    Returns:
        Formatted string like "view:project.dataset.table".
    """
    if isinstance(entity_id, dict):
        return (
            f"{prefix}:{entity_id.get('projectId', '')}."
            f"{entity_id.get('datasetId', '')}."
            f"{entity_id.get('tableId', '')}"
        )
    return f"{prefix}:{entity_id}"


def _format_dataset_ref(entity_id: object) -> str:
    """Format a dataset reference entity_id as a readable string.

    Args:
        entity_id: Dict with dataset/projectId/datasetId keys, or a string.

    Returns:
        Formatted string like "dataset:project.dataset".
    """
    if isinstance(entity_id, dict):
        ds_ref = entity_id.get("dataset", entity_id)
        if isinstance(ds_ref, dict):
            return (
                f"dataset:{ds_ref.get('projectId', '')}.{ds_ref.get('datasetId', '')}"
            )
        return f"dataset:{ds_ref}"
    return f"dataset:{entity_id}"


def _format_routine_ref(entity_id: object) -> str:
    """Format a routine reference entity_id as a readable string.

    Args:
        entity_id: Dict with projectId/datasetId/routineId keys, or a string.

    Returns:
        Formatted string like "routine:project.dataset.routine".
    """
    if isinstance(entity_id, dict):
        return (
            f"routine:{entity_id.get('projectId', '')}."
            f"{entity_id.get('datasetId', '')}."
            f"{entity_id.get('routineId', '')}"
        )
    return f"routine:{entity_id}"


def _parse_access_entry(
    access_entry: bigquery.AccessEntry,
    project_id: str,
    dataset_id: str,
) -> PermissionEntry | None:
    """Parse a single BigQuery AccessEntry into a PermissionEntry.

    Args:
        access_entry: A BigQuery dataset ACL entry.
        project_id: The project containing this dataset.
        dataset_id: The dataset ID.

    Returns:
        A PermissionEntry, or None if the entry cannot be parsed.
    """
    role = access_entry.role or "NONE"
    entity_type = access_entry.entity_type or "unknown"
    entity_id = access_entry.entity_id

    member_type = _ENTITY_TYPE_MAP.get(entity_type, entity_type)

    if entity_type in ("userByEmail", "groupByEmail", "specialGroup", "domain"):
        member = f"{member_type}:{entity_id}"

    elif entity_type == "view":
        member = _format_table_ref(entity_id, "view")
        member_type = "authorizedView"

    elif entity_type == "dataset":
        member = _format_dataset_ref(entity_id)
        member_type = "authorizedDataset"

    elif entity_type == "routine":
        member = _format_routine_ref(entity_id)
        member_type = "authorizedRoutine"

    elif entity_type == "iamMember":
        member = str(entity_id)
        if ":" in member:
            member_type = member.split(":")[0]

    else:
        member = f"{entity_type}:{entity_id}"

    return PermissionEntry(
        project_id=project_id,
        dataset_id=dataset_id,
        resource_id=None,
        resource_type=ResourceType.DATASET,
        role=role,
        member=member,
        member_type=member_type,
        source=PermissionSource.DATASET_ACL,
    )


def _scan_project_acls(
    project_id: str,
    project_index: int,
    total_projects: int,
) -> tuple[list[PermissionEntry], list[str]]:
    """Scan dataset ACLs for all datasets in a single project.

    Args:
        project_id: The GCP project ID to scan.
        project_index: 1-based index of this project (for progress logging).
        total_projects: Total number of projects being scanned.

    Returns:
        Tuple of (entries, errors).
    """
    entries: list[PermissionEntry] = []
    errors: list[str] = []

    logger.info(
        "Scanning project ACLs [%s/%s]: %s",
        project_index,
        total_projects,
        project_id,
    )

    try:
        bq_client = bigquery.Client(project=project_id)
    except Exception as e:
        errors.append(f"Cannot create BQ client for {project_id}: {e}")
        return entries, errors

    try:
        datasets = list(bq_client.list_datasets())
    except (BadRequest, Forbidden, PermissionDenied) as e:
        errors.append(f"No access to list datasets in {project_id}: {e}")
        return entries, errors
    except Exception as e:
        errors.append(f"Error listing datasets in {project_id}: {e}")
        return entries, errors

    total_datasets = len(datasets)
    for ds_index, dataset_ref in enumerate(datasets, start=1):
        dataset_id = dataset_ref.dataset_id
        logger.info(
            "  Dataset [%s/%s]: %s.%s",
            ds_index,
            total_datasets,
            project_id,
            dataset_id,
        )

        try:
            dataset = bq_client.get_dataset(f"{project_id}.{dataset_id}")
        except (BadRequest, NotFound, Forbidden, PermissionDenied) as e:
            logger.warning(
                "Skipping dataset %s.%s: %s",
                project_id,
                dataset_id,
                e,
            )
            continue
        except Exception as e:
            errors.append(f"Error fetching dataset {project_id}.{dataset_id}: {e}")
            continue

        for access_entry in dataset.access_entries:
            entry = _parse_access_entry(access_entry, project_id, dataset_id)
            if entry:
                entries.append(entry)

    return entries, errors


def scan_dataset_acls(
    organization_id: str,
    project_ids: list[str] | None = None,
) -> tuple[list[PermissionEntry], list[str]]:
    """Scan dataset ACLs across all projects in an organization.

    Discovers all projects in the organization (or uses the provided list),
    then iterates datasets in each project to read their access_entries.

    Args:
        organization_id: Numeric GCP organization ID. Used to discover
            projects if project_ids is not provided.
        project_ids: Optional list of specific project IDs to scan.
            If None, projects are discovered from the organization.

    Returns:
        Tuple of (entries, errors) where entries is a list of
        PermissionEntry objects sourced from DATASET_ACL, and errors is
        a list of error strings for any failures encountered.
    """
    if project_ids is None:
        logger.info(
            "Discovering projects for org %s",
            organization_id,
        )
        project_ids = list_org_projects(organization_id)

    total_projects = len(project_ids)
    logger.info("Scanning dataset ACLs across %s projects", total_projects)

    all_entries: list[PermissionEntry] = []
    all_errors: list[str] = []

    for index, project_id in enumerate(project_ids, start=1):
        try:
            entries, errors = _scan_project_acls(project_id, index, total_projects)
            all_entries.extend(entries)
            all_errors.extend(errors)
        except Exception as e:
            logger.error("Unexpected error scanning project %s: %s", project_id, e)
            all_errors.append(f"Unexpected error scanning project {project_id}: {e}")

    logger.info(
        "Dataset ACL scan complete: %s entries from %s projects",
        len(all_entries),
        total_projects,
    )
    return all_entries, all_errors
