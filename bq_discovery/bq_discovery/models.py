"""Data models for GCP BigQuery permission discovery."""

from __future__ import annotations

import csv
import io
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum


class ResourceType(Enum):
    """GCP resource types relevant to BigQuery access auditing.

    Folder-level IAM bindings cascade to all projects, datasets, and
    tables underneath them and are therefore relevant to a BigQuery
    access audit even though folders are not BigQuery resources
    themselves.
    """

    PROJECT = "project"
    FOLDER = "folder"
    DATASET = "dataset"
    TABLE = "table"
    VIEW = "view"
    # Future extensibility:
    # MODEL = "model"
    # ROUTINE = "routine"


class PermissionSource(Enum):
    """Source of the permission entry."""

    DATASET_ACL = "dataset_acl"
    IAM_POLICY = "iam_policy"


@dataclass
class PermissionEntry:
    """A single permission binding for a BigQuery resource.

    Attributes:
        project_id: GCP project ID containing the resource. Empty string
            for folder-level entries (folders are above projects).
        dataset_id: BigQuery dataset ID. Empty string for project- or
            folder-level entries.
        resource_id: Table or view ID for table/view entries. Folder
            numeric ID for folder entries. None for dataset/project-level
            entries.
        resource_type: Type of the resource.
        role: IAM role or dataset ACL role (READER, WRITER, OWNER).
        member: Member identifier (e.g. "user:alice@example.com").
        member_type: Type of member (user, group, serviceAccount, etc.).
        source: Whether from dataset ACL or IAM policy.
        inherited_from_group: Group email if expanded from group membership.
    """

    project_id: str
    dataset_id: str
    resource_id: str | None
    resource_type: ResourceType
    role: str
    member: str
    member_type: str
    source: PermissionSource
    inherited_from_group: str | None = None

    def to_dict(self) -> dict:
        """Convert to a JSON-serializable dictionary.

        Returns:
            Dict with enum values serialized as strings.
        """
        return {
            "project_id": self.project_id,
            "dataset_id": self.dataset_id,
            "resource_id": self.resource_id,
            "resource_type": self.resource_type.value,
            "role": self.role,
            "member": self.member,
            "member_type": self.member_type,
            "source": self.source.value,
            "inherited_from_group": self.inherited_from_group,
        }


@dataclass
class ScanResult:
    """Result of a permission discovery scan.

    Attributes:
        organization_id: GCP organization ID that was scanned.
        strategy: Scan mode identifier. Always "hybrid" (IAM + ACLs).
        scanned_at: ISO 8601 timestamp of when the scan started.
        projects_scanned: Number of distinct projects found in results.
        datasets_scanned: Number of distinct datasets found in results.
        resources_scanned: Number of distinct tables/views found in results.
        groups_expanded: Number of groups resolved to individual members.
        errors: List of error messages encountered during the scan.
        entries: List of permission entries discovered.
    """

    organization_id: str
    strategy: str = "hybrid"
    scanned_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    projects_scanned: int = 0
    datasets_scanned: int = 0
    resources_scanned: int = 0
    groups_expanded: int = 0
    errors: list[str] = field(default_factory=list)
    entries: list[PermissionEntry] = field(default_factory=list)

    def to_json(self, indent: int = 2) -> str:
        """Serialize the scan result to pretty-printed JSON.

        Includes a metadata block and an entries array.

        Args:
            indent: Number of spaces for JSON indentation.

        Returns:
            Pretty-printed JSON string.
        """
        return json.dumps(
            {
                "metadata": {
                    "organization_id": self.organization_id,
                    "strategy": self.strategy,
                    "scanned_at": self.scanned_at,
                    "projects_scanned": self.projects_scanned,
                    "datasets_scanned": self.datasets_scanned,
                    "resources_scanned": self.resources_scanned,
                    "groups_expanded": self.groups_expanded,
                    "errors": self.errors,
                },
                "entries": [e.to_dict() for e in self.entries],
            },
            indent=indent,
        )

    def to_jsonl(self) -> str:
        """Serialize the scan result to newline-delimited JSON (JSONL).

        Each line is a self-contained JSON object representing one
        permission entry, with organization_id and scanned_at
        denormalized into every row. Compatible with BigQuery JSONL
        import (bq load --source_format=NEWLINE_DELIMITED_JSON).

        Returns:
            String of newline-separated JSON objects, one per entry.
        """
        lines: list[str] = []
        for entry in self.entries:
            row = {
                "organization_id": self.organization_id,
                "scanned_at": self.scanned_at,
            }
            row.update(entry.to_dict())
            lines.append(json.dumps(row))
        return "\n".join(lines)

    def to_csv(self) -> str:
        """Serialize the scan result to CSV.

        Includes a header row. organization_id and scanned_at are
        denormalized into every row. Compatible with BigQuery CSV import
        (bq load --source_format=CSV --skip_leading_rows=1).

        Returns:
            CSV string with header and one data row per permission entry.
        """
        fieldnames = [
            "organization_id",
            "scanned_at",
            "project_id",
            "dataset_id",
            "resource_id",
            "resource_type",
            "role",
            "member",
            "member_type",
            "source",
            "inherited_from_group",
        ]
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for entry in self.entries:
            row = {
                "organization_id": self.organization_id,
                "scanned_at": self.scanned_at,
            }
            row.update(entry.to_dict())
            writer.writerow(row)
        return buf.getvalue()
