"""Tests for bq_discovery.scanner internal functions."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from bq_discovery.models import (
    PermissionEntry,
    PermissionSource,
    ResourceType,
    ScanResult,
)
from bq_discovery.scanner import _compute_stats, _expand_groups


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


def test_compute_stats_folder_entries_excluded_from_projects():
    """Folder entries with empty project_id do not inflate projects_scanned."""
    result = ScanResult(organization_id="123")
    result.entries = [
        _make_entry(project_id="proj-1"),
        PermissionEntry(
            project_id="",
            dataset_id="",
            resource_id="111222333",
            resource_type=ResourceType.FOLDER,
            role="roles/bigquery.admin",
            member="user:a@x.com",
            member_type="user",
            source=PermissionSource.IAM_POLICY,
        ),
    ]
    _compute_stats(result)
    assert result.projects_scanned == 1


# --- _expand_groups ---


def _make_group_entry(
    group_email: str = "team@example.com",
    project_id: str = "proj-1",
    dataset_id: str = "ds-1",
    role: str = "roles/bigquery.dataViewer",
) -> PermissionEntry:
    """Create a group PermissionEntry for expand_groups testing."""
    return PermissionEntry(
        project_id=project_id,
        dataset_id=dataset_id,
        resource_id=None,
        resource_type=ResourceType.DATASET,
        role=role,
        member=f"group:{group_email}",
        member_type="group",
        source=PermissionSource.IAM_POLICY,
    )


def test_expand_groups_no_groups_returns_empty():
    """Entries with no group members return empty list and no errors."""
    entries = [_make_entry()]  # user entry, not a group
    expanded, errors = _expand_groups(entries)
    assert expanded == []
    assert errors == []


def test_expand_groups_resolver_init_failure_returns_error_preserves_results():
    """GroupResolver construction failure returns error string; no exception raised."""
    entries = [_make_group_entry()]
    with patch(
        "bq_discovery.scanner.GroupResolver",
        side_effect=Exception("API not enabled"),
    ):
        expanded, errors = _expand_groups(entries)
    assert expanded == []
    assert len(errors) == 1
    assert "API not enabled" in errors[0]


def test_expand_groups_strips_group_prefix_for_lookup():
    """Group email is stripped of 'group:' prefix before resolving."""
    entries = [_make_group_entry(group_email="data-team@example.com")]
    mock_resolver = MagicMock()
    mock_resolver.resolve_group.return_value = [
        {"email": "alice@example.com", "type": "user"}
    ]
    with patch("bq_discovery.scanner.GroupResolver", return_value=mock_resolver):
        expanded, errors = _expand_groups(entries)
    mock_resolver.resolve_group.assert_called_once_with("data-team@example.com")
    assert errors == []


def test_expand_groups_creates_entries_with_inherited_from_group():
    """Expanded entries carry inherited_from_group set to the group email."""
    entries = [_make_group_entry(group_email="team@example.com")]
    mock_resolver = MagicMock()
    mock_resolver.resolve_group.return_value = [
        {"email": "alice@example.com", "type": "user"},
        {"email": "bot@proj.iam.gserviceaccount.com", "type": "serviceAccount"},
    ]
    with patch("bq_discovery.scanner.GroupResolver", return_value=mock_resolver):
        expanded, errors = _expand_groups(entries)
    assert len(expanded) == 2
    assert errors == []
    assert all(e.inherited_from_group == "team@example.com" for e in expanded)
    members = {e.member for e in expanded}
    assert "user:alice@example.com" in members
    assert "serviceAccount:bot@proj.iam.gserviceaccount.com" in members


def test_expand_groups_copies_source_fields_from_original_entry():
    """Expanded entries inherit project_id, dataset_id, role, source from original."""
    original = _make_group_entry(
        group_email="team@example.com",
        project_id="my-proj",
        dataset_id="my-ds",
        role="roles/bigquery.dataEditor",
    )
    mock_resolver = MagicMock()
    mock_resolver.resolve_group.return_value = [
        {"email": "alice@example.com", "type": "user"}
    ]
    with patch("bq_discovery.scanner.GroupResolver", return_value=mock_resolver):
        expanded, _ = _expand_groups([original])
    assert len(expanded) == 1
    e = expanded[0]
    assert e.project_id == "my-proj"
    assert e.dataset_id == "my-ds"
    assert e.role == "roles/bigquery.dataEditor"
    assert e.source == PermissionSource.IAM_POLICY


def test_expand_groups_empty_resolve_result_skipped():
    """Groups that resolve to no members produce no expanded entries."""
    entries = [_make_group_entry()]
    mock_resolver = MagicMock()
    mock_resolver.resolve_group.return_value = []
    with patch("bq_discovery.scanner.GroupResolver", return_value=mock_resolver):
        expanded, errors = _expand_groups(entries)
    assert expanded == []
    assert errors == []


def test_expand_groups_resolve_error_captured_continues():
    """Exception from resolve_group is captured as error; processing continues."""
    entry1 = _make_group_entry(group_email="bad@example.com")
    entry2 = _make_group_entry(group_email="good@example.com")
    mock_resolver = MagicMock()

    def side_effect(email):
        if email == "bad@example.com":
            raise RuntimeError("lookup failed")
        return [{"email": "alice@example.com", "type": "user"}]

    mock_resolver.resolve_group.side_effect = side_effect
    with patch("bq_discovery.scanner.GroupResolver", return_value=mock_resolver):
        expanded, errors = _expand_groups([entry1, entry2])
    assert len(errors) == 1
    assert "bad@example.com" in errors[0]
    assert len(expanded) == 1
