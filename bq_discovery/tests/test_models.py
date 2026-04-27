"""Tests for bq_discovery.models."""

from __future__ import annotations

import csv
import io
import json

from bq_discovery.models import (
    PermissionEntry,
    PermissionSource,
    ResourceType,
    ScanResult,
)


def _make_entry(
    project_id: str = "proj-1",
    dataset_id: str = "ds-1",
    resource_id: str | None = None,
    resource_type: ResourceType = ResourceType.DATASET,
    role: str = "READER",
    member: str = "user:alice@example.com",
    member_type: str = "user",
    source: PermissionSource = PermissionSource.DATASET_ACL,
    inherited_from_group: str | None = None,
) -> PermissionEntry:
    """Create a PermissionEntry with sensible defaults for testing."""
    return PermissionEntry(
        project_id=project_id,
        dataset_id=dataset_id,
        resource_id=resource_id,
        resource_type=resource_type,
        role=role,
        member=member,
        member_type=member_type,
        source=source,
        inherited_from_group=inherited_from_group,
    )


def _make_result(
    entries: list[PermissionEntry] | None = None,
    errors: list[str] | None = None,
) -> ScanResult:
    """Create a ScanResult with sensible defaults for testing."""
    result = ScanResult(organization_id="123456")
    if entries:
        result.entries = entries
    if errors:
        result.errors = errors
    return result


# --- PermissionEntry.to_dict ---


def test_to_dict_all_fields_populated():
    """Entry with all fields converts to dict with enum values as strings."""
    entry = _make_entry(
        resource_id="table-1",
        resource_type=ResourceType.TABLE,
        source=PermissionSource.IAM_POLICY,
        inherited_from_group="team@example.com",
    )
    d = entry.to_dict()
    assert d["resource_type"] == "table"
    assert d["source"] == "iam_policy"
    assert d["resource_id"] == "table-1"
    assert d["inherited_from_group"] == "team@example.com"


def test_to_dict_project_resource_type():
    """Project-level entry has resource_type='project' in dict."""
    d = _make_entry(
        resource_type=ResourceType.PROJECT,
        dataset_id="",
    ).to_dict()
    assert d["resource_type"] == "project"
    assert d["dataset_id"] == ""


def test_to_dict_folder_resource_type():
    """Folder entry serialises resource_type='folder' with folder ID in resource_id."""
    d = _make_entry(
        project_id="",
        dataset_id="",
        resource_id="123456789",
        resource_type=ResourceType.FOLDER,
    ).to_dict()
    assert d["resource_type"] == "folder"
    assert d["project_id"] == ""
    assert d["dataset_id"] == ""
    assert d["resource_id"] == "123456789"


# --- ScanResult.to_json ---


def test_to_json_empty_entries():
    """Empty scan result produces valid JSON with metadata and empty entries."""
    result = _make_result()
    parsed = json.loads(result.to_json())
    assert parsed["entries"] == []
    assert "metadata" in parsed


def test_to_json_with_entries():
    """Scan result with entries serializes all entries."""
    result = _make_result(entries=[_make_entry(), _make_entry(member="user:bob@x.com")])
    parsed = json.loads(result.to_json())
    assert len(parsed["entries"]) == 2


def test_to_json_metadata_fields():
    """JSON output includes all expected metadata fields."""
    result = _make_result()
    parsed = json.loads(result.to_json())
    meta = parsed["metadata"]
    expected_keys = {
        "organization_id",
        "strategy",
        "scanned_at",
        "projects_scanned",
        "datasets_scanned",
        "resources_scanned",
        "groups_expanded",
        "errors",
    }
    assert set(meta.keys()) == expected_keys


def test_to_json_with_errors():
    """Error strings appear in metadata.errors array."""
    result = _make_result(errors=["err1", "err2"])
    parsed = json.loads(result.to_json())
    assert parsed["metadata"]["errors"] == ["err1", "err2"]


def test_to_json_strategy_default():
    """Default strategy is 'hybrid'."""
    result = _make_result()
    parsed = json.loads(result.to_json())
    assert parsed["metadata"]["strategy"] == "hybrid"


# --- ScanResult.to_jsonl ---


def test_to_jsonl_empty_entries():
    """Empty scan result produces empty string."""
    result = _make_result()
    assert result.to_jsonl() == ""


def test_to_jsonl_single_entry():
    """Single entry produces one JSON line with denormalized fields."""
    result = _make_result(entries=[_make_entry()])
    lines = result.to_jsonl().strip().split("\n")
    assert len(lines) == 1
    parsed = json.loads(lines[0])
    assert parsed["organization_id"] == "123456"


def test_to_jsonl_each_line_is_valid_json():
    """Every line in JSONL output parses independently as valid JSON."""
    result = _make_result(entries=[_make_entry(), _make_entry()])
    for line in result.to_jsonl().strip().split("\n"):
        parsed = json.loads(line)
        assert "project_id" in parsed


def test_to_jsonl_denormalizes_scanned_at():
    """Each JSONL line contains the scanned_at from the ScanResult."""
    result = _make_result(entries=[_make_entry()])
    parsed = json.loads(result.to_jsonl())
    assert parsed["scanned_at"] == result.scanned_at


# --- ScanResult.to_csv ---


def test_to_csv_empty_entries():
    """Empty scan result produces header row only."""
    result = _make_result()
    lines = result.to_csv().strip().split("\n")
    assert len(lines) == 1  # header only


def test_to_csv_header_row():
    """CSV header contains all expected column names in order."""
    result = _make_result()
    header = result.to_csv().strip().split("\n")[0]
    expected = (
        "organization_id,scanned_at,project_id,dataset_id,"
        "resource_id,resource_type,role,member,member_type,"
        "source,inherited_from_group"
    )
    assert header == expected


def test_to_csv_denormalizes_organization_id():
    """Each CSV row contains the organization_id from ScanResult."""
    result = _make_result(entries=[_make_entry()])
    reader = csv.DictReader(io.StringIO(result.to_csv()))
    for row in reader:
        assert row["organization_id"] == "123456"


def test_to_csv_none_resource_id():
    """None resource_id is serialized as empty string in CSV."""
    result = _make_result(entries=[_make_entry(resource_id=None)])
    reader = csv.DictReader(io.StringIO(result.to_csv()))
    for row in reader:
        assert row["resource_id"] == ""
