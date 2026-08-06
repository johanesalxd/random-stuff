"""Tests for Dataplex metadata enrichment helpers."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config.agent_definitions import unique_table_ids  # noqa: E402
from scripts import enrich_bigquery_metadata as enrich  # noqa: E402
from scripts.enrich_bigquery_metadata import (  # noqa: E402
    apply_documentation_to_schema,
    bigquery_dataset_resource,
    bigquery_table_resource,
    build_data_documentation_payload,
    build_data_profile_payload,
    count_non_partitioned_tables,
    documentation_labels,
    enrich_table,
    extract_table_documentation,
    merge_field_descriptions,
    normalize_results_table,
    parse_args,
    publish_documentation_to_table,
    scan_id,
    update_mask_for_payload,
    upsert_scan,
    validate_dataplex_location,
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
    # Truncation must keep the prefix, or scans from different tools collide.
    assert first.startswith(f"{enrich.DATAPLEX_SCAN_PREFIX}-table-docs-")


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


def test_build_data_documentation_payload_omits_scope_for_dataset_scans():
    """Tests dataset-level documentation scans send no generation scopes.

    Dataplex rejects a dataset-level scan that carries generationScopes, so the
    scope must be dropped rather than defaulted.
    """
    payload = build_data_documentation_payload(
        resource="//bigquery.googleapis.com/projects/project-a/datasets/dataset_a",
        generation_scope=None,
        publish=True,
    )

    assert "generationScopes" not in payload["dataDocumentationSpec"]
    assert payload["dataDocumentationSpec"]["catalogPublishingEnabled"] is True


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


def test_normalize_results_table_rejects_malformed_value():
    """Tests a bare table name is rejected instead of silently misconfiguring."""
    with pytest.raises(ValueError, match="resource URI or"):
        normalize_results_table("just_a_table")


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


def test_validate_dataplex_location_allows_single_regions():
    """Tests a single region passes the pre-flight location check."""
    assert validate_dataplex_location("us-central1") is None


def test_validate_dataplex_location_rejects_multi_regions_with_a_replacement():
    """Tests BigQuery multi-regions are rejected before Dataplex 400s.

    Dataplex DataScans must live in a single region. Passing "us" returns an
    opaque "Malformed name" error, so the guard must name a usable region.
    """
    with pytest.raises(ValueError, match="us-central1"):
        validate_dataplex_location("us")

    with pytest.raises(ValueError, match="europe-west1"):
        validate_dataplex_location("EU")


def test_count_non_partitioned_tables_excludes_views_and_partitioned(monkeypatch):
    """Tests only non-partitioned base tables count toward the Dataplex minimum."""
    listing = {
        "tables": [
            {"type": "TABLE"},
            {"type": "TABLE", "timePartitioning": {"type": "DAY"}},
            {"type": "TABLE", "rangePartitioning": {"field": "id"}},
            {"type": "VIEW"},
            {},
        ]
    }
    monkeypatch.setattr(enrich, "PROJECT_ID", "project-a")
    monkeypatch.setattr(
        enrich, "request", lambda method, url, token, payload=None: listing
    )

    assert count_non_partitioned_tables("dataset_a", token="token") == 2


def test_count_non_partitioned_tables_returns_negative_one_when_listing_fails(
    monkeypatch,
):
    """Tests an unreadable dataset yields -1 so the caller skips the pre-check.

    The count is only an optimisation; losing it must not abort enrichment.
    """

    def fail(method: str, url: str, token: str, payload: dict | None = None):
        raise RuntimeError("403 permission denied")

    monkeypatch.setattr(enrich, "PROJECT_ID", "project-a")
    monkeypatch.setattr(enrich, "request", fail)

    assert count_non_partitioned_tables("dataset_a", token="token") == -1


def test_documentation_labels_carry_the_scan_reference(monkeypatch):
    """Tests publish labels point BigQuery at the scan holding the results."""
    monkeypatch.setattr(enrich, "PROJECT_ID", "project-a")
    monkeypatch.setattr(enrich, "DATAPLEX_LOCATION", "us-central1")

    labels = documentation_labels("bq-caapi-table-docs-orders")

    assert labels == {
        "dataplex-data-documentation-published-scan": "bq-caapi-table-docs-orders",
        "dataplex-data-documentation-published-project": "project-a",
        "dataplex-data-documentation-published-location": "us-central1",
    }


def test_publish_documentation_to_table_patches_labels(monkeypatch):
    """Tests publishing sets the Dataplex labels on the BigQuery table."""
    calls: list[tuple[str, str, dict | None]] = []

    monkeypatch.setattr(enrich, "PROJECT_ID", "project-a")
    monkeypatch.setattr(enrich, "DATAPLEX_LOCATION", "us-central1")
    monkeypatch.setattr(
        enrich,
        "request",
        lambda method, url, token, payload=None: (
            calls.append((method, url, payload)) or {}
        ),
    )

    publish_documentation_to_table(
        "dataset_a", "orders", "scan-a", token="token", dry_run=False
    )

    method, url, payload = calls[0]
    assert method == "PATCH"
    assert url.endswith("/projects/project-a/datasets/dataset_a/tables/orders")
    assert payload["labels"]["dataplex-data-documentation-published-scan"] == "scan-a"


def test_publish_documentation_to_table_skips_the_api_call_on_dry_run(monkeypatch):
    """Tests a dry run reports the intent without mutating the table."""

    def fail(method: str, url: str, token: str, payload: dict | None = None):
        raise AssertionError("dry run must not call the BigQuery API")

    monkeypatch.setattr(enrich, "request", fail)

    publish_documentation_to_table(
        "dataset_a", "orders", "scan-a", token="token", dry_run=True
    )


def test_extract_table_documentation_reads_overview_and_columns():
    """Tests the generated overview and described columns are pulled off a job."""
    job = {
        "dataDocumentationResult": {
            "tableResult": {
                "overview": "Customer orders.",
                "schema": {
                    "fields": [
                        {"name": "order_id", "description": "Unique order id."},
                        {"name": "status", "description": "Fulfilment status."},
                        {"name": "undocumented"},
                    ]
                },
            }
        }
    }

    overview, descriptions = extract_table_documentation(job)

    assert overview == "Customer orders."
    assert descriptions == {
        "order_id": "Unique order id.",
        "status": "Fulfilment status.",
    }


def test_extract_table_documentation_handles_missing_job():
    """Tests a run without --wait yields empty documentation, not an error."""
    assert extract_table_documentation(None) == ("", {})


def test_merge_field_descriptions_preserves_type_and_sets_description():
    """Tests merging keeps field type and mode and only touches described columns.

    A patch that dropped type or mode would rewrite the table schema.
    """
    existing = [
        {"name": "order_id", "type": "INTEGER", "mode": "REQUIRED"},
        {"name": "status", "type": "STRING", "mode": "NULLABLE"},
    ]

    merged = merge_field_descriptions(existing, {"status": "Fulfilment status."})

    by_name = {field["name"]: field for field in merged}
    assert by_name["status"] == {
        "name": "status",
        "type": "STRING",
        "mode": "NULLABLE",
        "description": "Fulfilment status.",
    }
    assert "description" not in by_name["order_id"]
    assert by_name["order_id"]["mode"] == "REQUIRED"


def test_apply_documentation_to_schema_writes_overview_and_columns(monkeypatch):
    """Tests the schema patch carries the overview and merged field descriptions."""
    calls: list[tuple[str, str, dict | None]] = []

    def fake_request(method: str, url: str, token: str, payload: dict | None = None):
        calls.append((method, url, payload))
        if method == "GET":
            return {
                "schema": {
                    "fields": [
                        {"name": "order_id", "type": "INTEGER", "mode": "REQUIRED"}
                    ]
                }
            }
        return {}

    monkeypatch.setattr(enrich, "PROJECT_ID", "project-a")
    monkeypatch.setattr(enrich, "request", fake_request)

    apply_documentation_to_schema(
        "dataset_a",
        "orders",
        overview="Customer orders.",
        descriptions={"order_id": "Unique order id."},
        token="token",
        dry_run=False,
    )

    assert [call[0] for call in calls] == ["GET", "PATCH"]
    patch = calls[1][2]
    assert patch["description"] == "Customer orders."
    assert patch["schema"]["fields"] == [
        {
            "name": "order_id",
            "type": "INTEGER",
            "mode": "REQUIRED",
            "description": "Unique order id.",
        }
    ]


def test_apply_documentation_to_schema_skips_when_nothing_was_generated(monkeypatch):
    """Tests an empty documentation result leaves the table schema untouched."""

    def fail(method: str, url: str, token: str, payload: dict | None = None):
        raise AssertionError("nothing to write, so the table must not be read")

    monkeypatch.setattr(enrich, "request", fail)

    apply_documentation_to_schema(
        "dataset_a",
        "orders",
        overview="",
        descriptions={},
        token="token",
        dry_run=False,
    )


def _enrich_args(**overrides) -> argparse.Namespace:
    """Build a parsed-argument stand-in for enrich_table.

    Args:
        **overrides: Fields to override on the default argument set.

    Returns:
        An argparse.Namespace with every field enrich_table reads.
    """
    defaults = {
        "skip_profile": True,
        "skip_table_docs": False,
        "skip_schema_write_back": False,
        "profile_mode": "STANDARD",
        "generation_scope": "ALL",
        "wait": True,
        "poll_interval": 0,
        "dry_run": False,
    }
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


def test_enrich_table_publishes_labels_then_writes_the_schema(monkeypatch):
    """Tests a documented table gets both the Insights labels and a schema patch.

    Publishing labels alone leaves the descriptions invisible to anything
    reading the table directly, so both steps must run.
    """
    job = {
        "dataDocumentationResult": {
            "tableResult": {
                "overview": "Customer orders.",
                "schema": {
                    "fields": [{"name": "order_id", "description": "Unique order id."}]
                },
            }
        }
    }
    published: list[tuple[str, str, str]] = []
    written: list[tuple[str, str, str, dict[str, str]]] = []

    monkeypatch.setattr(enrich, "PROJECT_ID", "project-a")
    monkeypatch.setattr(enrich, "DATASET_ID", "dataset_a")
    monkeypatch.setattr(
        enrich,
        "create_and_run_scan",
        lambda name, payload, token, wait, poll_interval, dry_run: job,
    )
    monkeypatch.setattr(
        enrich,
        "publish_documentation_to_table",
        lambda dataset_id, table_id, scan_name, token, dry_run: published.append(
            (dataset_id, table_id, scan_name)
        ),
    )
    monkeypatch.setattr(
        enrich,
        "apply_documentation_to_schema",
        lambda dataset_id, table_id, overview, descriptions, token, dry_run: (
            written.append((dataset_id, table_id, overview, descriptions))
        ),
    )

    enrich_table(
        "orders",
        _enrich_args(),
        token="token",
        sampling_percent=None,
        export_results_table=None,
        publish=True,
    )

    assert published == [
        ("dataset_a", "orders", "bq-caapi-table-docs-dataset-a-orders")
    ]
    assert written == [
        ("dataset_a", "orders", "Customer orders.", {"order_id": "Unique order id."})
    ]


def test_enrich_table_honours_skip_schema_write_back(monkeypatch):
    """Tests --skip-schema-write-back keeps the catalog entry but not the patch."""
    published: list[str] = []

    monkeypatch.setattr(enrich, "PROJECT_ID", "project-a")
    monkeypatch.setattr(enrich, "DATASET_ID", "dataset_a")
    monkeypatch.setattr(
        enrich,
        "create_and_run_scan",
        lambda name, payload, token, wait, poll_interval, dry_run: {},
    )
    monkeypatch.setattr(
        enrich,
        "publish_documentation_to_table",
        lambda dataset_id, table_id, scan_name, token, dry_run: published.append(
            table_id
        ),
    )

    def fail(*args, **kwargs):
        raise AssertionError("--skip-schema-write-back must not patch the schema")

    monkeypatch.setattr(enrich, "apply_documentation_to_schema", fail)

    enrich_table(
        "orders",
        _enrich_args(skip_schema_write_back=True),
        token="token",
        sampling_percent=None,
        export_results_table=None,
        publish=True,
    )

    assert published == ["orders"]
