"""IAM policy scanner using Cloud Asset Inventory.

Uses searchAllIamPolicies to discover all IAM policy bindings for BigQuery
resources. When project_ids are specified, scopes each call to
projects/{project_id} to avoid org-wide rate limits. When no project_ids
are specified, performs a single paginated call across the entire organization.

Folder scanning always uses org-wide scope regardless of project_ids, because
folder resources exist above projects in the GCP hierarchy and cannot be
discovered via project-scoped CAI calls.

Limitations:
    - Only captures IAM policies, not legacy dataset ACLs (use acl_scanner
      for those).
    - Cannot distinguish between TABLE and VIEW resource types — both are
      indexed as bigquery.googleapis.com/Table in Cloud Asset Inventory.
"""

from __future__ import annotations

import logging

from google.cloud import asset_v1

from bq_discovery.models import (
    PermissionEntry,
    PermissionSource,
    ResourceType,
)

logger = logging.getLogger(__name__)


def _parse_resource_name(resource: str) -> tuple[str, str, str | None]:
    """Parse a BigQuery full resource name into components.

    Args:
        resource: Full resource name, e.g.:
            //bigquery.googleapis.com/projects/p/datasets/d
            //bigquery.googleapis.com/projects/p/datasets/d/tables/t

    Returns:
        Tuple of (project_id, dataset_id, resource_id or None).
    """
    parts = resource.split("/")
    project_id = ""
    dataset_id = ""
    resource_id = None

    for i, part in enumerate(parts):
        if part == "projects" and i + 1 < len(parts):
            project_id = parts[i + 1]
        elif part == "datasets" and i + 1 < len(parts):
            dataset_id = parts[i + 1]
        elif part == "tables" and i + 1 < len(parts):
            resource_id = parts[i + 1]

    return project_id, dataset_id, resource_id


def _extract_member_type(member: str) -> str:
    """Extract the member type prefix from an IAM member string.

    Args:
        member: IAM member like "user:alice@example.com", or a special
            principal like "allUsers" or "allAuthenticatedUsers".

    Returns:
        The member type (user, group, serviceAccount, domain,
        specialGroup, etc.).
    """
    if member in ("allUsers", "allAuthenticatedUsers"):
        return "specialGroup"
    if ":" in member:
        return member.split(":")[0]
    return "unknown"


def _parse_folder_resource_name(resource: str) -> str:
    """Parse a folder resource name into a folder ID.

    Args:
        resource: Full resource name, e.g.:
            //cloudresourcemanager.googleapis.com/folders/123456789

    Returns:
        The folder numeric ID string, or empty string if not found.
    """
    parts = resource.split("/")
    for i, part in enumerate(parts):
        if part == "folders" and i + 1 < len(parts):
            return parts[i + 1]
    return ""


def _build_asset_types(resource_types: set[ResourceType]) -> list[str]:
    """Build the list of Cloud Asset asset type strings to search.

    Args:
        resource_types: Set of requested resource types.

    Returns:
        List of Cloud Asset API asset type strings.
    """
    asset_types: list[str] = []

    if ResourceType.FOLDER in resource_types:
        asset_types.append("cloudresourcemanager.googleapis.com/Folder")

    if ResourceType.PROJECT in resource_types:
        asset_types.append("cloudresourcemanager.googleapis.com/Project")

    if ResourceType.DATASET in resource_types:
        asset_types.append("bigquery.googleapis.com/Dataset")

    if ResourceType.TABLE in resource_types or ResourceType.VIEW in resource_types:
        asset_types.append("bigquery.googleapis.com/Table")

    return asset_types


def _parse_project_resource_name(resource: str) -> str:
    """Parse a project resource name into a project ID.

    Args:
        resource: Full resource name, e.g.:
            //cloudresourcemanager.googleapis.com/projects/my-project-id

    Returns:
        The project ID string.
    """
    parts = resource.split("/")
    for i, part in enumerate(parts):
        if part == "projects" and i + 1 < len(parts):
            return parts[i + 1]
    return ""


def _process_result(
    result: asset_v1.IamPolicySearchResult,
    resource_types: set[ResourceType],
    project_ids: list[str] | None,
    entries: list[PermissionEntry],
) -> None:
    """Process a single IAM policy search result into entries.

    Args:
        result: A single IAM policy search result from Cloud Asset.
        resource_types: Set of requested resource types for filtering.
        project_ids: Optional list of project IDs to filter by.
        entries: List to append matching PermissionEntry objects to.
    """
    asset_type = result.asset_type
    resource = result.resource

    # Determine resource type and parse resource name
    if asset_type == "cloudresourcemanager.googleapis.com/Folder":
        if ResourceType.FOLDER not in resource_types:
            return
        res_type = ResourceType.FOLDER
        folder_id = _parse_folder_resource_name(resource)
        if not folder_id:
            logger.warning("Could not parse folder resource name: %s", resource)
            return
        project_id = ""
        dataset_id = ""
        resource_id = folder_id
    elif asset_type == "cloudresourcemanager.googleapis.com/Project":
        res_type = ResourceType.PROJECT
        project_id = _parse_project_resource_name(resource)
        dataset_id = ""
        resource_id = None
    elif asset_type == "bigquery.googleapis.com/Dataset":
        res_type = ResourceType.DATASET
        project_id, dataset_id, resource_id = _parse_resource_name(resource)
    elif asset_type == "bigquery.googleapis.com/Table":
        # Cloud Asset Inventory does not distinguish table vs view.
        # Both are reported as bigquery.googleapis.com/Table.
        res_type = ResourceType.TABLE
        project_id, dataset_id, resource_id = _parse_resource_name(resource)
    else:
        return

    # Folder entries have no project_id; skip the project filter for them.
    if (
        res_type != ResourceType.FOLDER
        and project_ids
        and project_id not in project_ids
    ):
        return

    # Check if this resource type was requested. For TABLE asset type,
    # also accept if VIEW was requested since asset inventory cannot
    # distinguish between them.
    if res_type not in resource_types:
        if not (res_type == ResourceType.TABLE and ResourceType.VIEW in resource_types):
            return

    for binding in result.policy.bindings:
        role = binding.role
        for member in binding.members:
            member_type = _extract_member_type(member)
            entries.append(
                PermissionEntry(
                    project_id=project_id,
                    dataset_id=dataset_id,
                    resource_id=resource_id,
                    resource_type=res_type,
                    role=role,
                    member=member,
                    member_type=member_type,
                    source=PermissionSource.IAM_POLICY,
                )
            )


def scan_iam_policies(
    organization_id: str,
    resource_types: set[ResourceType],
    project_ids: list[str] | None = None,
) -> tuple[list[PermissionEntry], list[str]]:
    """Scan IAM policies using Cloud Asset Inventory.

    When project_ids are provided, performs one searchAllIamPolicies call
    per project scoped to projects/{project_id}, avoiding org-wide rate
    limits. When project_ids is None, performs a single paginated call
    scoped to organizations/{organization_id}.

    Folder scanning always uses org-wide scope regardless of project_ids,
    because folder resources exist above projects in the GCP hierarchy and
    cannot be discovered via project-scoped CAI calls. When project_ids is
    provided and FOLDER is in resource_types, an additional org-scoped call
    is made for folder-only asset types.

    Args:
        organization_id: Numeric GCP organization ID.
        resource_types: Set of resource types to include in results.
        project_ids: Optional list of project IDs. When provided, scopes
            each CAI call to the individual project. When None, scans the
            entire organization.

    Returns:
        Tuple of (entries, errors) where entries is a list of
        PermissionEntry objects and errors is a list of error strings.
    """
    client = asset_v1.AssetServiceClient()
    entries: list[PermissionEntry] = []
    errors: list[str] = []

    # Split FOLDER from the remaining types: folders require org scope even
    # when project_ids restricts everything else.
    folder_types: set[ResourceType] = set()
    non_folder_types: set[ResourceType] = set()
    for rt in resource_types:
        if rt == ResourceType.FOLDER:
            folder_types.add(rt)
        else:
            non_folder_types.add(rt)

    if project_ids:
        # Per-project scan for non-folder resources
        non_folder_asset_types = _build_asset_types(non_folder_types)
        if non_folder_asset_types:
            for project_id in project_ids:
                scope = f"projects/{project_id}"
                logger.info(
                    "Scanning IAM policies via Cloud Asset Inventory, scope=%s",
                    scope,
                )
                try:
                    request = asset_v1.SearchAllIamPoliciesRequest(
                        scope=scope,
                        asset_types=non_folder_asset_types,
                    )
                    for result in client.search_all_iam_policies(request=request):
                        _process_result(result, resource_types, None, entries)
                except Exception as e:
                    logger.error(
                        "Cloud Asset Inventory scan failed for project %s: %s",
                        project_id,
                        e,
                    )
                    errors.append(
                        f"Cloud Asset Inventory scan failed for project "
                        f"{project_id}: {e}"
                    )

        # Additional org-scoped scan for folders (cannot use project scope)
        if folder_types:
            folder_asset_types = _build_asset_types(folder_types)
            org_scope = f"organizations/{organization_id}"
            logger.info(
                "Scanning folder IAM policies via Cloud Asset Inventory, scope=%s "
                "(folder scanning always uses org scope)",
                org_scope,
            )
            try:
                request = asset_v1.SearchAllIamPoliciesRequest(
                    scope=org_scope,
                    asset_types=folder_asset_types,
                )
                for result in client.search_all_iam_policies(request=request):
                    _process_result(result, resource_types, None, entries)
            except Exception as e:
                logger.error("Cloud Asset Inventory folder scan failed: %s", e)
                errors.append(f"Cloud Asset Inventory folder scan failed: {e}")
    else:
        # Single org-wide scan for all resource types
        asset_types = _build_asset_types(resource_types)
        if not asset_types:
            return entries, errors

        scope = f"organizations/{organization_id}"
        logger.info(
            "Scanning IAM policies via Cloud Asset Inventory, scope=%s",
            scope,
        )
        try:
            request = asset_v1.SearchAllIamPoliciesRequest(
                scope=scope,
                asset_types=asset_types,
            )
            for result in client.search_all_iam_policies(request=request):
                _process_result(result, resource_types, project_ids, entries)
        except Exception as e:
            logger.error("Cloud Asset Inventory scan failed: %s", e)
            errors.append(f"Cloud Asset Inventory scan failed: {e}")

    logger.info(
        "IAM policy scan complete: %s entries found",
        len(entries),
    )
    return entries, errors
