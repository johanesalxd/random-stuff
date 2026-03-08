"""Resolve projects within a GCP organization.

Recursively discovers all active projects under an organization,
including those nested inside folders.
"""

from __future__ import annotations

import logging
from collections import deque

from google.cloud import resourcemanager_v3

logger = logging.getLogger(__name__)


def list_org_projects(organization_id: str) -> list[str]:
    """List all active project IDs within a GCP organization.

    Recursively scans the organization hierarchy (org -> folders ->
    sub-folders) to find every project. Uses BFS traversal.

    Args:
        organization_id: The numeric organization ID.

    Returns:
        List of project IDs (strings), sorted alphabetically.
    """
    projects_client = resourcemanager_v3.ProjectsClient()
    folders_client = resourcemanager_v3.FoldersClient()

    project_ids: list[str] = []
    org_parent = f"organizations/{organization_id}"

    # BFS through the org hierarchy
    parents_to_scan: deque[str] = deque([org_parent])

    while parents_to_scan:
        parent = parents_to_scan.popleft()
        logger.debug("Scanning parent: %s", parent)

        # List projects under this parent
        try:
            request = resourcemanager_v3.ListProjectsRequest(parent=parent)
            for project in projects_client.list_projects(request=request):
                if project.state == resourcemanager_v3.Project.State.ACTIVE:
                    project_ids.append(project.project_id)
                    logger.info("Found project: %s", project.project_id)
        except Exception as e:
            logger.warning("Error listing projects under %s: %s", parent, e)

        # List folders under this parent and add to queue
        try:
            request = resourcemanager_v3.ListFoldersRequest(parent=parent)
            for folder in folders_client.list_folders(request=request):
                if folder.state == resourcemanager_v3.Folder.State.ACTIVE:
                    parents_to_scan.append(folder.name)
                    logger.debug("Found folder: %s", folder.name)
        except Exception as e:
            logger.warning("Error listing folders under %s: %s", parent, e)

    project_ids.sort()
    logger.info(
        "Total projects found in org %s: %s",
        organization_id,
        len(project_ids),
    )
    return project_ids
