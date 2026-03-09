"""Tests for bq_discovery.scanner internal functions."""

from __future__ import annotations

from bq_discovery.models import (
    PermissionEntry,
    PermissionSource,
    ResourceType,
    ScanResult,
)
from bq_discovery.scanner import _compute_stats


def _make_entry(
    project_id: str = "proj-1",
    dataset_id: str = "ds-1",
    resource_id: str | None = None,
) -> PermissionEntry:
    """Create a PermissionEntry with minimal fields for stats testing."""
    return PermissionEntry(
        project_id=project_id,
        dataset_id=dataset_id,
        resource_id=resource_id,
        resource_type=ResourceType.DATASET,
        role="READER",
        member="user:a@x.com",
        member_type="user",
        source=PermissionSource.DATASET_ACL,
    )


def test_compute_stats_empty_entries():
    """Empty entries list produces all zero counts."""
    result = ScanResult(organization_id="123")
    _compute_stats(result)
    assert result.projects_scanned == 0
    assert result.datasets_scanned == 0
    assert result.resources_scanned == 0


def test_compute_stats_multiple_projects():
    """Distinct projects counted correctly."""
    result = ScanResult(organization_id="123")
    result.entries = [
        _make_entry(project_id="p1"),
        _make_entry(project_id="p2"),
        _make_entry(project_id="p1"),
    ]
    _compute_stats(result)
    assert result.projects_scanned == 2


def test_compute_stats_datasets_counted_by_pair():
    """Datasets with same name in different projects are counted separately."""
    result = ScanResult(organization_id="123")
    result.entries = [
        _make_entry(project_id="p1", dataset_id="ds"),
        _make_entry(project_id="p2", dataset_id="ds"),
    ]
    _compute_stats(result)
    assert result.datasets_scanned == 2


def test_compute_stats_resources_only_non_none():
    """Entries with resource_id=None are excluded from resources_scanned."""
    result = ScanResult(organization_id="123")
    result.entries = [
        _make_entry(resource_id=None),
        _make_entry(resource_id="table-1"),
    ]
    _compute_stats(result)
    assert result.resources_scanned == 1


def test_compute_stats_resources_deduplication():
    """Duplicate (project, dataset, resource_id) tuples are counted once."""
    result = ScanResult(organization_id="123")
    result.entries = [
        _make_entry(resource_id="t1"),
        _make_entry(resource_id="t1"),
        _make_entry(resource_id="t2"),
    ]
    _compute_stats(result)
    assert result.resources_scanned == 2
