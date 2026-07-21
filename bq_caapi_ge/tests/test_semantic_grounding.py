"""Tests for catalog grounding adapters."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

pytest.importorskip("google.adk")
pytest.importorskip("google.cloud.dataplex_v1")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from semantic.grounding import (  # noqa: E402
    GroundingError,
    disabled_grounding,
    load_adk_bigquery_catalog_adc,
)


def test_disabled_grounding_returns_explicit_status():
    """Tests disabled grounding is visible to the workflow."""
    result = disabled_grounding()

    assert result.status == "disabled"
    assert result.mode == "disabled"
    assert result.assets == ()


def test_load_adk_bigquery_catalog_adc_compacts_assets():
    """Tests ADK catalog search results are compacted for intent selection."""
    calls = {}

    def fake_search_catalog(**kwargs):
        calls.update(kwargs)
        return {
            "status": "SUCCESS",
            "results": [
                {
                    "display_name": "orders",
                    "linked_resource": "//bigquery.googleapis.com/projects/p/datasets/d/tables/orders",
                    "description": "Order lifecycle table.",
                    "entry_type": "bigquery-table",
                }
            ],
        }

    result = load_adk_bigquery_catalog_adc(
        question="Completed orders by country",
        project="project-a",
        location="us",
        dataset_id="thelook_ecommerce",
        page_size=3,
        credentials=object(),
        search_catalog_tool=fake_search_catalog,
    )

    assert calls["prompt"] == "Completed orders by country"
    assert calls["project_id"] == "project-a"
    assert calls["location"] == "us"
    assert calls["page_size"] == 3
    assert calls["dataset_ids_filter"] == ["thelook_ecommerce"]
    assert result.status == "success"
    assert result.mode == "adk_bigquery_adc"
    assert result.assets[0]["display_name"] == "orders"


def test_load_adk_bigquery_catalog_adc_requires_project():
    """Tests catalog grounding requires an explicit project."""
    with pytest.raises(GroundingError, match="GOOGLE_CLOUD_PROJECT"):
        load_adk_bigquery_catalog_adc(
            question="Completed orders",
            project=None,
            credentials=object(),
            search_catalog_tool=lambda **_: {"status": "SUCCESS"},
        )


def test_load_adk_bigquery_catalog_adc_raises_tool_errors():
    """Tests catalog tool failures surface as grounding errors."""
    with pytest.raises(GroundingError, match="permission denied"):
        load_adk_bigquery_catalog_adc(
            question="Completed orders",
            project="project-a",
            credentials=object(),
            search_catalog_tool=lambda **_: {
                "status": "ERROR",
                "error_details": "permission denied",
            },
        )


def test_load_adk_bigquery_catalog_adc_wraps_tool_exceptions():
    """Tests unexpected catalog helper failures become grounding errors."""

    def fail_search(**_kwargs):
        raise RuntimeError("credentials unavailable")

    with pytest.raises(GroundingError, match="credentials unavailable"):
        load_adk_bigquery_catalog_adc(
            question="Completed orders",
            project="project-a",
            credentials=object(),
            search_catalog_tool=fail_search,
        )


@pytest.mark.parametrize(
    "response",
    [
        None,
        {"status": "SUCCESS", "results": None},
        {"status": "SUCCESS", "results": ["not-an-asset"]},
        {"status": "SUCCESS", "results": [{"display_name": {"bad": "value"}}]},
    ],
)
def test_load_adk_bigquery_catalog_adc_rejects_malformed_results(response):
    """Tests malformed catalog results become grounding errors."""
    with pytest.raises(GroundingError, match="malformed|must be a string"):
        load_adk_bigquery_catalog_adc(
            question="Completed orders",
            project="project-a",
            credentials=object(),
            search_catalog_tool=lambda **_: response,
        )


@pytest.mark.parametrize("page_size", [0, 1001])
def test_load_adk_bigquery_catalog_adc_rejects_unbounded_page_size(page_size):
    """Tests catalog result limits remain bounded."""
    with pytest.raises(GroundingError, match="between 1 and 1000"):
        load_adk_bigquery_catalog_adc(
            question="Completed orders",
            project="project-a",
            page_size=page_size,
            credentials=object(),
            search_catalog_tool=lambda **_: {"status": "SUCCESS"},
        )


def test_load_adk_bigquery_catalog_adc_rejects_excess_results():
    """Tests catalog helpers cannot exceed the requested page size."""
    with pytest.raises(GroundingError, match="too many results"):
        load_adk_bigquery_catalog_adc(
            question="Completed orders",
            project="project-a",
            page_size=1,
            credentials=object(),
            search_catalog_tool=lambda **_: {
                "status": "SUCCESS",
                "results": [{}, {}],
            },
        )
