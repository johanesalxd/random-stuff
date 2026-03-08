"""Main orchestrator for BigQuery permission discovery.

Combines two complementary data sources:

1. Cloud Asset Inventory (iam_scanner) — fast, org-wide IAM policy scan
   covering datasets, tables, and views in a single paginated API call.

2. Direct BigQuery API (acl_scanner) — dataset ACL scan covering legacy
   READER/WRITER/OWNER bindings, specialGroup, domain, authorizedView,
   authorizedDataset, and authorizedRoutine entries that Cloud Asset
   Inventory does not expose.
"""

from __future__ import annotations

import logging

from bq_discovery.acl_scanner import scan_dataset_acls
from bq_discovery.iam_scanner import scan_iam_policies
from bq_discovery.models import (
    PermissionEntry,
    ResourceType,
    ScanResult,
)
from bq_discovery.resolvers.groups import GroupResolver

logger = logging.getLogger(__name__)


def run_scan(
    organization_id: str,
    resource_types: set[ResourceType] | None = None,
    project_ids: list[str] | None = None,
    skip_acls: bool = False,
    expand_groups: bool = False,
) -> ScanResult:
    """Run a BigQuery permission discovery scan.

    Combines IAM policy data from Cloud Asset Inventory with dataset ACL
    data from the direct BigQuery API, then optionally expands group
    memberships to individual users via the Cloud Identity API.

    Args:
        organization_id: The numeric GCP organization ID.
        resource_types: Set of resource types to scan.
            Defaults to all (dataset, table, view).
        project_ids: Optional list of specific project IDs to scan.
            If None, discovers all projects from the organization.
        skip_acls: If True, skip the dataset ACL scan and return only
            IAM policy entries from Cloud Asset Inventory.
        expand_groups: Whether to expand group memberships to individual
            users via the Cloud Identity API.

    Returns:
        ScanResult containing all discovered permission entries.
    """
    if resource_types is None:
        resource_types = {
            ResourceType.PROJECT,
            ResourceType.DATASET,
            ResourceType.TABLE,
            ResourceType.VIEW,
        }

    result = ScanResult(organization_id=organization_id)

    logger.info(
        "Starting scan: org=%s, resource_types=%s, skip_acls=%s, expand_groups=%s",
        organization_id,
        [t.value for t in resource_types],
        skip_acls,
        expand_groups,
    )

    # --- Phase 1: IAM policies via Cloud Asset Inventory ---
    iam_entries, iam_errors = scan_iam_policies(
        organization_id=organization_id,
        resource_types=resource_types,
        project_ids=project_ids,
    )
    result.entries.extend(iam_entries)
    result.errors.extend(iam_errors)

    # --- Phase 2: Dataset ACLs via direct BigQuery API ---
    if not skip_acls and ResourceType.DATASET in resource_types:
        acl_entries, acl_errors = scan_dataset_acls(
            organization_id=organization_id,
            project_ids=project_ids,
        )
        result.entries.extend(acl_entries)
        result.errors.extend(acl_errors)

    # Compute statistics before optional group expansion
    _compute_stats(result)

    # --- Phase 3: Expand group memberships (optional) ---
    if expand_groups:
        expanded = _expand_groups(result.entries)
        result.entries.extend(expanded)
        result.groups_expanded = len(
            {e.inherited_from_group for e in expanded if e.inherited_from_group}
        )

    logger.info(
        "Scan complete: %s entries, %s errors",
        len(result.entries),
        len(result.errors),
    )
    return result


def _compute_stats(result: ScanResult) -> None:
    """Compute summary statistics from scan entries in place.

    Args:
        result: The ScanResult to update with statistics.
    """
    result.projects_scanned = len({e.project_id for e in result.entries})
    result.datasets_scanned = len(
        {(e.project_id, e.dataset_id) for e in result.entries}
    )
    result.resources_scanned = len(
        {
            (e.project_id, e.dataset_id, e.resource_id)
            for e in result.entries
            if e.resource_id
        }
    )


def _expand_groups(
    entries: list[PermissionEntry],
) -> list[PermissionEntry]:
    """Expand group members into individual permission entries.

    Collects all unique group emails from the entries, resolves each
    group to its individual members via Cloud Identity, and creates
    new PermissionEntry objects that trace back to the original group.

    Args:
        entries: The original permission entries to scan for groups.

    Returns:
        New permission entries for individual group members.
        The original group entries are not modified.
    """
    group_emails: set[str] = set()
    for entry in entries:
        if entry.member_type == "group":
            email = entry.member
            if ":" in email:
                email = email.split(":", 1)[1]
            group_emails.add(email)

    if not group_emails:
        logger.info("No group members found to expand")
        return []

    logger.info("Expanding %s groups", len(group_emails))
    resolver = GroupResolver()
    expanded: list[PermissionEntry] = []

    for group_email in sorted(group_emails):
        members = resolver.resolve_group(group_email)
        if not members:
            continue

        group_entries = [
            e
            for e in entries
            if e.member_type == "group" and e.member.endswith(f":{group_email}")
        ]

        for entry in group_entries:
            for member in members:
                expanded.append(
                    PermissionEntry(
                        project_id=entry.project_id,
                        dataset_id=entry.dataset_id,
                        resource_id=entry.resource_id,
                        resource_type=entry.resource_type,
                        role=entry.role,
                        member=f"{member['type']}:{member['email']}",
                        member_type=member["type"],
                        source=entry.source,
                        inherited_from_group=group_email,
                    )
                )

    logger.info("Expanded into %s individual entries", len(expanded))
    return expanded
