"""Tests for bq_discovery.iam_scanner internal functions."""

from __future__ import annotations

from google.cloud import asset_v1
from google.iam.v1 import policy_pb2

from bq_discovery.iam_scanner import (
    _build_asset_types,
    _extract_member_type,
    _parse_project_resource_name,
    _parse_resource_name,
    _process_result,
)
from bq_discovery.models import (
    PermissionSource,
    ResourceType,
)

# --- _parse_resource_name ---


def test_parse_resource_name_dataset():
    """Dataset resource name returns (project, dataset, None)."""
    result = _parse_resource_name(
        "//bigquery.googleapis.com/projects/my-proj/datasets/my_ds"
    )
    assert result == ("my-proj", "my_ds", None)


def test_parse_resource_name_table():
    """Table resource name returns (project, dataset, table)."""
    result = _parse_resource_name(
        "//bigquery.googleapis.com/projects/p/datasets/d/tables/t"
    )
    assert result == ("p", "d", "t")


def test_parse_resource_name_empty_string():
    """Empty string returns empty components."""
    assert _parse_resource_name("") == ("", "", None)


def test_parse_resource_name_malformed():
    """Malformed string without recognized segments returns empty components."""
    assert _parse_resource_name("some/random/path") == ("", "", None)


# --- _extract_member_type ---


def test_extract_member_type_user():
    """User member returns 'user'."""
    assert _extract_member_type("user:alice@example.com") == "user"


def test_extract_member_type_group():
    """Group member returns 'group'."""
    assert _extract_member_type("group:team@example.com") == "group"


def test_extract_member_type_service_account():
    """Service account member returns 'serviceAccount'."""
    assert (
        _extract_member_type("serviceAccount:sa@proj.iam.gserviceaccount.com")
        == "serviceAccount"
    )


def test_extract_member_type_domain():
    """Domain member returns 'domain'."""
    assert _extract_member_type("domain:example.com") == "domain"


def test_extract_member_type_all_users():
    """allUsers returns 'specialGroup'."""
    assert _extract_member_type("allUsers") == "specialGroup"


def test_extract_member_type_all_authenticated_users():
    """allAuthenticatedUsers returns 'specialGroup'."""
    assert _extract_member_type("allAuthenticatedUsers") == "specialGroup"


def test_extract_member_type_unknown():
    """Unrecognized member without colon returns 'unknown'."""
    assert _extract_member_type("somethingweird") == "unknown"


def test_extract_member_type_project_editor():
    """projectEditor:project-id returns 'projectEditor'."""
    assert _extract_member_type("projectEditor:my-proj") == "projectEditor"


# --- _build_asset_types ---


def test_build_asset_types_all():
    """All resource types produce all three asset type strings."""
    types = {
        ResourceType.PROJECT,
        ResourceType.DATASET,
        ResourceType.TABLE,
        ResourceType.VIEW,
    }
    result = _build_asset_types(types)
    assert "cloudresourcemanager.googleapis.com/Project" in result
    assert "bigquery.googleapis.com/Dataset" in result
    assert "bigquery.googleapis.com/Table" in result
    assert len(result) == 3


def test_build_asset_types_dataset_only():
    """Dataset-only produces single bigquery Dataset asset type."""
    result = _build_asset_types({ResourceType.DATASET})
    assert result == ["bigquery.googleapis.com/Dataset"]


def test_build_asset_types_table_only():
    """TABLE produces bigquery Table asset type."""
    result = _build_asset_types({ResourceType.TABLE})
    assert result == ["bigquery.googleapis.com/Table"]


def test_build_asset_types_view_only():
    """VIEW also produces bigquery Table asset type."""
    result = _build_asset_types({ResourceType.VIEW})
    assert result == ["bigquery.googleapis.com/Table"]


def test_build_asset_types_table_and_view():
    """TABLE + VIEW produces single bigquery Table asset type (no duplicate)."""
    result = _build_asset_types({ResourceType.TABLE, ResourceType.VIEW})
    assert result == ["bigquery.googleapis.com/Table"]


def test_build_asset_types_project_only():
    """PROJECT produces cloudresourcemanager Project asset type."""
    result = _build_asset_types({ResourceType.PROJECT})
    assert result == ["cloudresourcemanager.googleapis.com/Project"]


def test_build_asset_types_empty_set():
    """Empty set produces empty list."""
    assert _build_asset_types(set()) == []


# --- _parse_project_resource_name ---


def test_parse_project_resource_name_standard():
    """Standard resource name returns project ID."""
    result = _parse_project_resource_name(
        "//cloudresourcemanager.googleapis.com/projects/my-project-id"
    )
    assert result == "my-project-id"


def test_parse_project_resource_name_empty():
    """Empty string returns empty string."""
    assert _parse_project_resource_name("") == ""


def test_parse_project_resource_name_no_projects_segment():
    """String without 'projects' segment returns empty string."""
    assert _parse_project_resource_name("//some/other/resource") == ""


# --- _process_result ---


def _make_iam_result(
    resource: str,
    asset_type: str,
    bindings: list[tuple[str, list[str]]],
) -> asset_v1.IamPolicySearchResult:
    """Build an IamPolicySearchResult for testing."""
    policy = policy_pb2.Policy(
        bindings=[
            policy_pb2.Binding(role=role, members=members) for role, members in bindings
        ]
    )
    result = asset_v1.IamPolicySearchResult(
        resource=resource,
        asset_type=asset_type,
        policy=policy,
    )
    return result


def test_process_result_dataset_entry():
    """Dataset asset type creates entries with ResourceType.DATASET."""
    result = _make_iam_result(
        "//bigquery.googleapis.com/projects/p/datasets/d",
        "bigquery.googleapis.com/Dataset",
        [("roles/bigquery.dataViewer", ["user:a@x.com"])],
    )
    entries = []
    _process_result(result, {ResourceType.DATASET}, None, entries)
    assert len(entries) == 1
    assert entries[0].resource_type == ResourceType.DATASET
    assert entries[0].dataset_id == "d"


def test_process_result_table_entry():
    """Table asset type creates entries with ResourceType.TABLE."""
    result = _make_iam_result(
        "//bigquery.googleapis.com/projects/p/datasets/d/tables/t",
        "bigquery.googleapis.com/Table",
        [("roles/bigquery.dataViewer", ["user:a@x.com"])],
    )
    entries = []
    _process_result(result, {ResourceType.TABLE}, None, entries)
    assert len(entries) == 1
    assert entries[0].resource_type == ResourceType.TABLE
    assert entries[0].resource_id == "t"


def test_process_result_project_entry():
    """Project asset type creates entries with ResourceType.PROJECT."""
    result = _make_iam_result(
        "//cloudresourcemanager.googleapis.com/projects/my-proj",
        "cloudresourcemanager.googleapis.com/Project",
        [("roles/editor", ["user:a@x.com"])],
    )
    entries = []
    _process_result(result, {ResourceType.PROJECT}, None, entries)
    assert len(entries) == 1
    assert entries[0].resource_type == ResourceType.PROJECT
    assert entries[0].project_id == "my-proj"
    assert entries[0].dataset_id == ""
    assert entries[0].resource_id is None


def test_process_result_unknown_asset_type_skipped():
    """Unknown asset type produces no entries."""
    result = _make_iam_result(
        "//storage.googleapis.com/buckets/b",
        "storage.googleapis.com/Bucket",
        [("roles/storage.admin", ["user:a@x.com"])],
    )
    entries = []
    _process_result(result, {ResourceType.DATASET, ResourceType.TABLE}, None, entries)
    assert len(entries) == 0


def test_process_result_project_filter_match():
    """Entry passes when project_id is in the filter list."""
    result = _make_iam_result(
        "//bigquery.googleapis.com/projects/p1/datasets/d",
        "bigquery.googleapis.com/Dataset",
        [("roles/bigquery.dataViewer", ["user:a@x.com"])],
    )
    entries = []
    _process_result(result, {ResourceType.DATASET}, ["p1"], entries)
    assert len(entries) == 1


def test_process_result_project_filter_no_match():
    """Entry is skipped when project_id is not in the filter list."""
    result = _make_iam_result(
        "//bigquery.googleapis.com/projects/p2/datasets/d",
        "bigquery.googleapis.com/Dataset",
        [("roles/bigquery.dataViewer", ["user:a@x.com"])],
    )
    entries = []
    _process_result(result, {ResourceType.DATASET}, ["p1"], entries)
    assert len(entries) == 0


def test_process_result_project_filter_none():
    """All entries pass when project_ids is None."""
    result = _make_iam_result(
        "//bigquery.googleapis.com/projects/any/datasets/d",
        "bigquery.googleapis.com/Dataset",
        [("roles/bigquery.dataViewer", ["user:a@x.com"])],
    )
    entries = []
    _process_result(result, {ResourceType.DATASET}, None, entries)
    assert len(entries) == 1


def test_process_result_resource_type_filter():
    """Entry is skipped when its resource type was not requested."""
    result = _make_iam_result(
        "//bigquery.googleapis.com/projects/p/datasets/d",
        "bigquery.googleapis.com/Dataset",
        [("roles/bigquery.dataViewer", ["user:a@x.com"])],
    )
    entries = []
    _process_result(result, {ResourceType.TABLE}, None, entries)
    assert len(entries) == 0


def test_process_result_view_accepted_when_table_asset():
    """TABLE asset type is accepted when VIEW is in requested types."""
    result = _make_iam_result(
        "//bigquery.googleapis.com/projects/p/datasets/d/tables/t",
        "bigquery.googleapis.com/Table",
        [("roles/bigquery.dataViewer", ["user:a@x.com"])],
    )
    entries = []
    _process_result(result, {ResourceType.VIEW}, None, entries)
    assert len(entries) == 1


def test_process_result_multiple_bindings():
    """Result with multiple bindings and members produces multiple entries."""
    result = _make_iam_result(
        "//bigquery.googleapis.com/projects/p/datasets/d",
        "bigquery.googleapis.com/Dataset",
        [
            ("roles/bigquery.dataViewer", ["user:a@x.com", "user:b@x.com"]),
            ("roles/bigquery.dataEditor", ["group:team@x.com"]),
        ],
    )
    entries = []
    _process_result(result, {ResourceType.DATASET}, None, entries)
    assert len(entries) == 3


def test_process_result_sets_source_iam_policy():
    """All entries have source=PermissionSource.IAM_POLICY."""
    result = _make_iam_result(
        "//bigquery.googleapis.com/projects/p/datasets/d",
        "bigquery.googleapis.com/Dataset",
        [("roles/bigquery.dataViewer", ["user:a@x.com"])],
    )
    entries = []
    _process_result(result, {ResourceType.DATASET}, None, entries)
    assert entries[0].source == PermissionSource.IAM_POLICY
