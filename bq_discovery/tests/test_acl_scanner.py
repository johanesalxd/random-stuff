"""Tests for bq_discovery.acl_scanner internal functions."""

from __future__ import annotations

from google.cloud import bigquery

from bq_discovery.acl_scanner import (
    _format_dataset_ref,
    _format_routine_ref,
    _format_table_ref,
    _parse_access_entry,
)
from bq_discovery.models import PermissionSource, ResourceType

# --- _format_table_ref ---


def test_format_table_ref_dict():
    """Dict entity_id formats as 'prefix:project.dataset.table'."""
    result = _format_table_ref(
        {"projectId": "p", "datasetId": "d", "tableId": "t"}, "view"
    )
    assert result == "view:p.d.t"


def test_format_table_ref_string():
    """String entity_id formats as 'prefix:entity_id'."""
    assert _format_table_ref("some_ref", "view") == "view:some_ref"


def test_format_table_ref_missing_keys():
    """Dict with missing keys uses empty strings for missing components."""
    result = _format_table_ref({"projectId": "p"}, "view")
    assert result == "view:p.."


# --- _format_dataset_ref ---


def test_format_dataset_ref_nested_dict():
    """Nested dict with 'dataset' key containing projectId/datasetId."""
    result = _format_dataset_ref({"dataset": {"projectId": "p", "datasetId": "d"}})
    assert result == "dataset:p.d"


def test_format_dataset_ref_flat_dict():
    """Flat dict without 'dataset' key uses dict itself."""
    result = _format_dataset_ref({"projectId": "p", "datasetId": "d"})
    assert result == "dataset:p.d"


def test_format_dataset_ref_string():
    """String entity_id formats as 'dataset:entity_id'."""
    assert _format_dataset_ref("some_ref") == "dataset:some_ref"


def test_format_dataset_ref_nested_non_dict():
    """Nested 'dataset' key with string value formats as 'dataset:value'."""
    result = _format_dataset_ref({"dataset": "string_value"})
    assert result == "dataset:string_value"


# --- _format_routine_ref ---


def test_format_routine_ref_dict():
    """Dict entity_id formats as 'routine:project.dataset.routine'."""
    result = _format_routine_ref({"projectId": "p", "datasetId": "d", "routineId": "r"})
    assert result == "routine:p.d.r"


def test_format_routine_ref_string():
    """String entity_id formats as 'routine:entity_id'."""
    assert _format_routine_ref("some_ref") == "routine:some_ref"


def test_format_routine_ref_missing_keys():
    """Dict with missing keys uses empty strings for missing components."""
    result = _format_routine_ref({"projectId": "p"})
    assert result == "routine:p.."


# --- _parse_access_entry ---


def _make_access_entry(
    role: str | None, entity_type: str, entity_id: str | dict
) -> bigquery.AccessEntry:
    """Create a BigQuery AccessEntry for testing."""
    return bigquery.AccessEntry(
        role=role,
        entity_type=entity_type,
        entity_id=entity_id,
    )


def test_parse_access_entry_user():
    """userByEmail entry produces member='user:email' with member_type='user'."""
    entry = _parse_access_entry(
        _make_access_entry("READER", "userByEmail", "alice@x.com"),
        "proj-1",
        "ds-1",
    )
    assert entry is not None
    assert entry.member == "user:alice@x.com"
    assert entry.member_type == "user"
    assert entry.role == "READER"


def test_parse_access_entry_group():
    """groupByEmail entry produces member='group:email'."""
    entry = _parse_access_entry(
        _make_access_entry("WRITER", "groupByEmail", "team@x.com"),
        "proj-1",
        "ds-1",
    )
    assert entry is not None
    assert entry.member == "group:team@x.com"
    assert entry.member_type == "group"


def test_parse_access_entry_special_group():
    """specialGroup entry produces member='specialGroup:name'."""
    entry = _parse_access_entry(
        _make_access_entry("READER", "specialGroup", "projectReaders"),
        "proj-1",
        "ds-1",
    )
    assert entry is not None
    assert entry.member == "specialGroup:projectReaders"
    assert entry.member_type == "specialGroup"


def test_parse_access_entry_domain():
    """domain entry produces member='domain:example.com'."""
    entry = _parse_access_entry(
        _make_access_entry("READER", "domain", "example.com"),
        "proj-1",
        "ds-1",
    )
    assert entry is not None
    assert entry.member == "domain:example.com"
    assert entry.member_type == "domain"


def test_parse_access_entry_iam_member_with_colon():
    """iamMember with 'type:email' extracts the type prefix."""
    entry = _parse_access_entry(
        _make_access_entry("READER", "iamMember", "user:bob@x.com"),
        "proj-1",
        "ds-1",
    )
    assert entry is not None
    assert entry.member == "user:bob@x.com"
    assert entry.member_type == "user"


def test_parse_access_entry_iam_member_without_colon():
    """iamMember without colon keeps 'iamMember' as member_type."""
    entry = _parse_access_entry(
        _make_access_entry("READER", "iamMember", "allUsers"),
        "proj-1",
        "ds-1",
    )
    assert entry is not None
    assert entry.member == "allUsers"
    assert entry.member_type == "iamMember"


def test_parse_access_entry_unknown_entity_type():
    """Unknown entity_type formats as 'type:id' with type as member_type."""
    entry = _parse_access_entry(
        _make_access_entry("READER", "newType", "some_id"),
        "proj-1",
        "ds-1",
    )
    assert entry is not None
    assert entry.member == "newType:some_id"
    assert entry.member_type == "newType"


def test_parse_access_entry_none_role():
    """None role defaults to 'NONE'."""
    entry = _parse_access_entry(
        _make_access_entry(None, "userByEmail", "alice@x.com"),
        "proj-1",
        "ds-1",
    )
    assert entry is not None
    assert entry.role == "NONE"


def test_parse_access_entry_sets_source_dataset_acl():
    """All parsed entries have source=PermissionSource.DATASET_ACL."""
    entry = _parse_access_entry(
        _make_access_entry("READER", "userByEmail", "alice@x.com"),
        "proj-1",
        "ds-1",
    )
    assert entry is not None
    assert entry.source == PermissionSource.DATASET_ACL


def test_parse_access_entry_sets_resource_type_dataset():
    """All parsed entries have resource_type=ResourceType.DATASET."""
    entry = _parse_access_entry(
        _make_access_entry("READER", "userByEmail", "alice@x.com"),
        "proj-1",
        "ds-1",
    )
    assert entry is not None
    assert entry.resource_type == ResourceType.DATASET


def test_parse_access_entry_resource_id_is_none():
    """All parsed entries have resource_id=None."""
    entry = _parse_access_entry(
        _make_access_entry("READER", "userByEmail", "alice@x.com"),
        "proj-1",
        "ds-1",
    )
    assert entry is not None
    assert entry.resource_id is None
