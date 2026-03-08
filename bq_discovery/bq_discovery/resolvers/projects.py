"""Resolve projects within a GCP organization.

Recursively discovers all active projects under an organization,
including those nested inside folders.
"""

from __future__ import annotations

import logging
from collections import deque

from google.cloud import resourcemanager_v3

logger = logging.getLogger(__name__)


def list_org_projects_info(organization_id: str) -> list[dict[str, str]]:
    """List all active projects within a GCP organization with metadata.

    Recursively scans the organization hierarchy (org -> folders ->
    sub-folders) to find every active project. Uses BFS traversal.

    Args:
        organization_id: The numeric organization ID.

    Returns:
        List of dicts with keys 'project_id' and 'project_number',
        sorted alphabetically by project_id.
    """
    projects_client = resourcemanager_v3.ProjectsClient()
    folders_client = resourcemanager_v3.FoldersClient()

    projects: list[dict[str, str]] = []
    org_parent = f"organizations/{organization_id}"

    parents_to_scan: deque[str] = deque([org_parent])

    while parents_to_scan:
        parent = parents_to_scan.popleft()
        logger.debug("Scanning parent: %s", parent)

        try:
            request = resourcemanager_v3.ListProjectsRequest(parent=parent)
            for project in projects_client.list_projects(request=request):
                if project.state == resourcemanager_v3.Project.State.ACTIVE:
                    # project.name is "projects/PROJECT_NUMBER"
                    project_number = project.name.split("/")[-1]
                    projects.append(
                        {
                            "project_id": project.project_id,
                            "project_number": project_number,
                        }
                    )
                    logger.info("Found project: %s", project.project_id)
        except Exception as e:
            logger.warning("Error listing projects under %s: %s", parent, e)

        try:
            request = resourcemanager_v3.ListFoldersRequest(parent=parent)
            for folder in folders_client.list_folders(request=request):
                if folder.state == resourcemanager_v3.Folder.State.ACTIVE:
                    parents_to_scan.append(folder.name)
                    logger.debug("Found folder: %s", folder.name)
        except Exception as e:
            logger.warning("Error listing folders under %s: %s", parent, e)

    projects.sort(key=lambda p: p["project_id"])
    logger.info(
        "Total projects found in org %s: %s",
        organization_id,
        len(projects),
    )
    return projects


def list_org_projects(organization_id: str) -> list[str]:
    """List all active project IDs within a GCP organization.

    Convenience wrapper around list_org_projects_info() that returns
    only project ID strings.

    Args:
        organization_id: The numeric organization ID.

    Returns:
        List of project IDs (strings), sorted alphabetically.
    """
    return [p["project_id"] for p in list_org_projects_info(organization_id)]
