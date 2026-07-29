"""Tests for the Dataplex metadata enrichment helpers.

These cover the pure, deterministic parts of the enrichment tooling: the
native/federated table split (from the agent config) and the scan-payload,
scan-id, resource-URI, and publish-label builders (from the script). No live
Dataplex, BigQuery, or gcloud calls are made.
"""

from __future__ import annotations

import os

import pytest

# The script resolves project/location from the environment at import time.
# Pin them so the import is deterministic regardless of local config files.
os.environ.setdefault("GCP_PROJECT", "test-project")
os.environ.setdefault("GCP_REGION", "us-east4")
os.environ.setdefault("FROYO_NATIVE_DATASET", "froyo_demo_ue4")
os.environ.setdefault("FEDERATED_CATALOG", "demo_glue_cat")
os.environ.setdefault("GLUE_DATABASE", "froyo_lakehouse")
os.environ.setdefault("DATAPLEX_SCAN_PREFIX", "froyo-agent")

from config.agent_definition import (
    LakehouseConfig,
    federated_table_refs,
    is_federated_dataset_id,
    native_table_ids,
)
from scripts import enrich_bigquery_metadata as enrich

_CONFIG = LakehouseConfig(
    project_id="demo-project",
    native_dataset="froyo_demo_ue4",
    federated_catalog="demo_glue_cat",
    glue_database="froyo_lakehouse",
    loyalty_table="global_loyalty",
    sales_table="sales_history",
)


def test_is_federated_dataset_id_distinguishes_native_from_pcnt():
    """A dotted dataset id is federated; a bare dataset id is native."""
    assert is_federated_dataset_id("demo_glue_cat.froyo_lakehouse") is True
    assert is_federated_dataset_id("froyo_demo_ue4") is False


def test_native_table_ids_returns_only_the_four_native_tables():
    """Only the single-dataset knowledge tables are treated as native."""
    assert set(native_table_ids(_CONFIG)) == {
        "products",
        "recipes",
        "ingredient_allergens",
        "product_allergens",
    }


def test_federated_table_refs_returns_the_two_aws_iceberg_tables():
    """Federated refs carry the catalog.namespace dataset id and table name."""
    assert set(federated_table_refs(_CONFIG)) == {
        ("demo_glue_cat.froyo_lakehouse", "global_loyalty"),
        ("demo_glue_cat.froyo_lakehouse", "sales_history"),
    }


def test_data_profile_payload_standard_publishes_and_samples():
    """STANDARD profile carries sampling percent and catalog publishing."""
    payload = enrich.build_data_profile_payload(
        resource="//bigquery.googleapis.com/projects/p/datasets/d/tables/t",
        mode="STANDARD",
        publish=True,
        sampling_percent=10.0,
    )
    assert payload["type"] == "DATA_PROFILE"
    assert payload["dataProfileSpec"]["mode"] == "STANDARD"
    assert payload["dataProfileSpec"]["samplingPercent"] == 10.0
    assert payload["dataProfileSpec"]["catalogPublishingEnabled"] is True


def test_data_profile_payload_lightweight_rejects_sampling():
    """LIGHTWEIGHT mode cannot take a sampling percentage."""
    with pytest.raises(ValueError, match="LIGHTWEIGHT"):
        enrich.build_data_profile_payload(
            resource="//bigquery.googleapis.com/projects/p/datasets/d/tables/t",
            mode="LIGHTWEIGHT",
            publish=True,
            sampling_percent=5.0,
        )


def test_data_documentation_payload_wraps_scope_and_publish_flag():
    """Documentation payload nests the generation scope and publish flag."""
    payload = enrich.build_data_documentation_payload(
        resource="//bigquery.googleapis.com/projects/p/datasets/d/tables/t",
        generation_scope="ALL",
        publish=False,
    )
    assert payload["type"] == "DATA_DOCUMENTATION"
    assert payload["dataDocumentationSpec"]["generationScopes"] == ["ALL"]
    assert payload["dataDocumentationSpec"]["catalogPublishingEnabled"] is False


def test_data_documentation_payload_omits_scope_for_dataset_scans():
    """Dataset-level documentation scans must not send generation scopes."""
    payload = enrich.build_data_documentation_payload(
        resource="//bigquery.googleapis.com/projects/p/datasets/d",
        generation_scope=None,
        publish=True,
    )
    assert "generationScopes" not in payload["dataDocumentationSpec"]
    assert payload["dataDocumentationSpec"]["catalogPublishingEnabled"] is True


def test_scan_id_is_slugified_and_prefixed():
    """Scan ids are lowercase, hyphenated, and carry the configured prefix."""
    result = enrich.scan_id("profile", "froyo_demo_ue4", "products")
    assert result == "froyo-agent-profile-froyo-demo-ue4-products"


def test_scan_id_hashes_when_too_long():
    """Over-long scan ids collapse to a bounded, hashed slug."""
    result = enrich.scan_id("table-docs", "d" * 60, "t" * 60)
    assert len(result) <= 63
    assert result.startswith("froyo-agent-table-docs-")


def test_bigquery_table_resource_supports_federated_dotted_dataset():
    """Federated refs render the catalog.namespace as the dataset segment."""
    resource = enrich.bigquery_table_resource(
        "demo-project", "demo_glue_cat.froyo_lakehouse", "sales_history"
    )
    assert resource == (
        "//bigquery.googleapis.com/projects/demo-project/"
        "datasets/demo_glue_cat.froyo_lakehouse/tables/sales_history"
    )


def test_normalize_results_table_accepts_three_part_name():
    """A project.dataset.table string is converted to a resource URI."""
    assert enrich.normalize_results_table("p.d.t") == (
        "//bigquery.googleapis.com/projects/p/datasets/d/tables/t"
    )


def test_normalize_results_table_rejects_malformed_value():
    """A non three-part, non-URI value is rejected."""
    with pytest.raises(ValueError, match="resource URI or"):
        enrich.normalize_results_table("just_a_table")


def test_documentation_labels_carry_the_scan_reference():
    """Publish labels reference the scan, project, and location."""
    labels = enrich.documentation_labels("froyo-agent-table-docs-products")
    assert labels["dataplex-data-documentation-published-scan"] == (
        "froyo-agent-table-docs-products"
    )
    assert "dataplex-data-documentation-published-project" in labels
    assert "dataplex-data-documentation-published-location" in labels


def test_extract_table_documentation_reads_overview_and_columns():
    """Generated overview and column descriptions are pulled from a docs job."""
    job = {
        "dataDocumentationResult": {
            "tableResult": {
                "overview": "Product catalog.",
                "schema": {
                    "fields": [
                        {"name": "product_id", "description": "Unique product id."},
                        {"name": "category", "description": "Product classification."},
                        {"name": "no_desc"},
                    ]
                },
            }
        }
    }
    overview, descriptions = enrich.extract_table_documentation(job)
    assert overview == "Product catalog."
    assert descriptions == {
        "product_id": "Unique product id.",
        "category": "Product classification.",
    }


def test_extract_table_documentation_handles_missing_job():
    """A None job (for example a non-wait run) yields empty documentation."""
    assert enrich.extract_table_documentation(None) == ("", {})


def test_merge_field_descriptions_preserves_type_and_sets_description():
    """Merging keeps field type/mode and only sets described columns."""
    existing = [
        {"name": "product_id", "type": "INTEGER", "mode": "NULLABLE"},
        {"name": "category", "type": "STRING", "mode": "NULLABLE"},
    ]
    merged = enrich.merge_field_descriptions(existing, {"category": "Classification."})
    by_name = {f["name"]: f for f in merged}
    assert by_name["category"]["description"] == "Classification."
    assert by_name["category"]["type"] == "STRING"
    assert "description" not in by_name["product_id"]


def test_update_mask_reflects_scan_type():
    """The update mask includes the type-specific spec field."""
    profile = enrich.build_data_profile_payload(
        resource="//x", mode="LIGHTWEIGHT", publish=True
    )
    docs = enrich.build_data_documentation_payload(
        resource="//x", generation_scope="ALL", publish=True
    )
    assert "dataProfileSpec" in enrich.update_mask_for_payload(profile)
    assert "dataDocumentationSpec" in enrich.update_mask_for_payload(docs)
