"""Tests for Dataplex metadata enrichment helpers."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config.agent_definitions import unique_table_ids  # noqa: E402
from scripts import enrich_bigquery_metadata as enrich  # noqa: E402
from scripts.enrich_bigquery_metadata import (  # noqa: E402
    bigquery_dataset_resource,
    bigquery_table_resource,
    build_data_documentation_payload,
    build_data_profile_payload,
    normalize_results_table,
    parse_args,
    scan_id,
    update_mask_for_payload,
    upsert_scan,
    wait_for_operation,
    wait_for_scan_job,
)


def test_bigquery_resource_builders_return_dataplex_uris():
    """Tests BigQuery dataset and table resources use expected URI forms."""
    dataset_resource = bigquery_dataset_resource("project-a", "dataset_a")
    table_resource = bigquery_table_resource("project-a", "dataset_a", "orders")

    assert dataset_resource == (
        "//bigquery.googleapis.com/projects/project-a/datasets/dataset_a"
    )
    assert table_resource == (
        "//bigquery.googleapis.com/projects/project-a/datasets/dataset_a/tables/orders"
    )


def test_scan_id_normalizes_and_limits_length():
    """Tests scan IDs are Dataplex-safe and deterministic."""
    first = scan_id(
        "table_docs",
        "Dataset_With_Underscores",
        "Very_Long_Table_Name" * 5,
    )
    second = scan_id(
        "table_docs",
        "Dataset_With_Underscores",
        "Very_Long_Table_Name" * 5,
    )

    assert first == second
    assert len(first) <= 63
    assert first[0].isalpha()
    assert "_" not in first


def test_build_data_documentation_payload_includes_scope_and_publishing():
    """Tests documentation payloads include scan type, scope, and publishing."""
    payload = build_data_documentation_payload(
        resource="//bigquery.googleapis.com/projects/project-a/datasets/dataset_a",
        generation_scope="ALL",
        publish=True,
    )

    assert payload["type"] == "DATA_DOCUMENTATION"
    assert payload["dataDocumentationSpec"] == {
        "generationScopes": ["ALL"],
        "catalogPublishingEnabled": True,
    }


def test_build_data_profile_payload_rejects_lightweight_sampling():
    """Tests LIGHTWEIGHT profile scans reject standard-only sampling."""
    with pytest.raises(ValueError, match="LIGHTWEIGHT"):
        build_data_profile_payload(
            resource="//bigquery.googleapis.com/projects/project-a/datasets/d/tables/t",
            mode="LIGHTWEIGHT",
            publish=False,
            sampling_percent=10.0,
        )


def test_build_data_profile_payload_adds_export_table():
    """Tests profile payloads include BigQuery export configuration."""
    payload = build_data_profile_payload(
        resource="//bigquery.googleapis.com/projects/project-a/datasets/d/tables/t",
        mode="STANDARD",
        publish=True,
        sampling_percent=20.0,
        export_results_table=(
            "//bigquery.googleapis.com/projects/p/datasets/d/tables/profile"
        ),
    )

    assert payload["type"] == "DATA_PROFILE"
    assert payload["dataProfileSpec"]["samplingPercent"] == 20.0
    assert payload["dataProfileSpec"]["postScanActions"] == {
        "bigqueryExport": {
            "resultsTable": (
                "//bigquery.googleapis.com/projects/p/datasets/d/tables/profile"
            )
        }
    }


def test_update_mask_for_payload_matches_scan_type():
    """Tests patch update masks include the active scan specification."""
    docs_payload = build_data_documentation_payload(
        resource="//bigquery.googleapis.com/projects/project-a/datasets/d",
        generation_scope="ALL",
        publish=True,
    )
    profile_payload = build_data_profile_payload(
        resource="//bigquery.googleapis.com/projects/project-a/datasets/d/tables/t",
        mode="STANDARD",
        publish=True,
    )

    assert update_mask_for_payload(docs_payload) == (
        "data,executionSpec,dataDocumentationSpec"
    )
    assert update_mask_for_payload(profile_payload) == (
        "data,executionSpec,dataProfileSpec"
    )


def test_wait_for_operation_polls_until_done(monkeypatch):
    """Tests DataScan create/update operations are polled before job runs."""
    requests: list[tuple[str, str]] = []

    def fake_request(method: str, url: str, token: str, payload: dict | None = None):
        del token, payload
        requests.append((method, url))
        return {"name": "projects/p/locations/us/operations/op-1", "done": True}

    monkeypatch.setattr(enrich.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(enrich, "request", fake_request)

    result = wait_for_operation(
        {"name": "projects/p/locations/us/operations/op-1"},
        token="token",
    )

    assert result["done"] is True
    assert requests == [
        (
            "GET",
            "https://dataplex.googleapis.com/v1/"
            "projects/p/locations/us/operations/op-1",
        )
    ]


def test_wait_for_operation_raises_on_operation_error():
    """Tests failed Dataplex operations surface an actionable error."""
    with pytest.raises(RuntimeError, match="operation op-1 failed"):
        wait_for_operation(
            {"name": "op-1", "done": True, "error": {"message": "bad scan"}},
            token="token",
        )


def test_upsert_scan_patches_existing_scan(monkeypatch):
    """Tests existing scans are patched so config changes are not stale."""
    calls: list[tuple[str, str, dict | None]] = []

    def fake_request(method: str, url: str, token: str, payload: dict | None = None):
        del token
        calls.append((method, url, payload))
        if method == "POST":
            raise RuntimeError("ALREADY_EXISTS: scan exists")
        return {"name": "projects/p/locations/us/operations/op-1", "done": True}

    monkeypatch.setattr(enrich, "PROJECT_ID", "project-a")
    monkeypatch.setattr(enrich, "DATAPLEX_LOCATION", "us")
    monkeypatch.setattr(enrich, "request", fake_request)

    payload = build_data_documentation_payload(
        resource="//bigquery.googleapis.com/projects/project-a/datasets/d",
        generation_scope="TABLE_AND_COLUMN_DESCRIPTIONS",
        publish=False,
    )
    upsert_scan("scan-a", payload, token="token", dry_run=False)

    assert [call[0] for call in calls] == ["POST", "PATCH"]
    assert calls[1][1].endswith(
        "/dataScans/scan-a?updateMask=data%2CexecutionSpec%2CdataDocumentationSpec"
    )
    assert calls[1][2]["name"] == "projects/project-a/locations/us/dataScans/scan-a"


def test_wait_for_scan_job_accepts_succeeded_with_errors(monkeypatch):
    """Tests --wait exits on Dataplex's partial-success terminal state."""
    monkeypatch.setattr(
        enrich,
        "request",
        lambda method, url, token: {"state": "SUCCEEDED_WITH_ERRORS"},
    )

    result = wait_for_scan_job(
        "scan-a",
        "job-a",
        token="token",
        poll_interval=0,
    )

    assert result["state"] == "SUCCEEDED_WITH_ERRORS"


def test_parse_args_rejects_invalid_env_profile_mode(monkeypatch):
    """Tests env profile mode is validated like CLI profile mode."""
    monkeypatch.setattr(sys, "argv", ["enrich_bigquery_metadata.py"])
    monkeypatch.setenv("DATA_PROFILE_MODE", "bad-mode")

    with pytest.raises(ValueError, match="DATA_PROFILE_MODE"):
        parse_args()


def test_normalize_results_table_accepts_project_dataset_table():
    """Tests profile export table shorthand is normalized to a resource URI."""
    result = normalize_results_table("project_a.dataset_a.profile_results")

    assert result == (
        "//bigquery.googleapis.com/projects/project_a/datasets/dataset_a"
        "/tables/profile_results"
    )


def test_unique_table_ids_returns_agent_tables_once():
    """Tests shared config exposes the default-path table set."""
    assert unique_table_ids() == [
        "users",
        "orders",
        "order_items",
        "events",
        "products",
        "inventory_items",
        "distribution_centers",
    ]
