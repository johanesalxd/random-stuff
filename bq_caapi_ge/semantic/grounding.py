"""Catalog retrieval adapters for future semantic intent grounding."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class GroundingError(RuntimeError):
    """Raised when catalog metadata cannot be loaded."""


@dataclass(frozen=True)
class GroundingResult:
    """Compact catalog retrieval metadata for future intent grounding."""

    status: str
    mode: str
    assets: tuple[dict[str, str], ...] = ()
    error: str | None = None


def disabled_grounding() -> GroundingResult:
    """Returns an explicit disabled catalog retrieval result."""
    return GroundingResult(
        status="disabled",
        mode="disabled",
    )


def load_adk_bigquery_catalog_adc(
    *,
    question: str,
    project: str | None,
    location: str | None = None,
    dataset_id: str | None = None,
    page_size: int = 5,
    credentials: Any | None = None,
    search_catalog_tool: Any | None = None,
) -> GroundingResult:
    """Loads catalog metadata with lower-level ADK BigQuery helpers and ADC.

    Args:
        question: User question used as the catalog search prompt.
        project: Google Cloud project that scopes catalog search.
        location: Optional Dataplex/BigQuery location.
        dataset_id: Optional BigQuery dataset filter.
        page_size: Maximum catalog results to include.
        credentials: Optional Google credentials, primarily for tests.
        search_catalog_tool: Optional search_catalog-compatible callable for tests.

    Returns:
        Compact catalog retrieval result with asset summaries.

    Raises:
        GroundingError: If configuration is invalid or catalog search fails.
    """
    if not project:
        raise GroundingError("GOOGLE_CLOUD_PROJECT must be set for catalog retrieval")
    if isinstance(page_size, bool) or not 1 <= page_size <= 1000:
        raise GroundingError("catalog page_size must be between 1 and 1000")

    try:
        import google.auth
        from google.adk.integrations.bigquery import search_tool
        from google.adk.integrations.bigquery.bigquery_credentials import (
            BIGQUERY_SCOPES,
        )
        from google.adk.integrations.bigquery.config import (
            BigQueryToolConfig,
            WriteMode,
        )

        search_credentials = (
            credentials or google.auth.default(scopes=BIGQUERY_SCOPES)[0]
        )
        settings = BigQueryToolConfig(
            write_mode=WriteMode.BLOCKED,
            application_name="bq-caapi-certified-analytics",
            compute_project_id=project,
            location=location,
        )
        search_catalog = search_catalog_tool or search_tool.search_catalog
        result = search_catalog(
            prompt=question,
            project_id=project,
            credentials=search_credentials,
            settings=settings,
            location=location,
            page_size=page_size,
            dataset_ids_filter=[dataset_id] if dataset_id else None,
            types_filter=None,
        )
        if not isinstance(result, dict):
            raise GroundingError("catalog retrieval returned a malformed response")
        if result.get("status") != "SUCCESS":
            error_details = result.get(
                "error_details", "unknown catalog retrieval error"
            )
            raise GroundingError(f"catalog retrieval failed: {error_details}")
        raw_assets = result.get("results", [])
        if not isinstance(raw_assets, list):
            raise GroundingError("catalog retrieval returned malformed results")
        if len(raw_assets) > page_size:
            raise GroundingError("catalog retrieval returned too many results")
        assets = tuple(_compact_asset(asset) for asset in raw_assets)
        return GroundingResult(
            status="success",
            mode="adk_bigquery_adc",
            assets=assets,
        )
    except GroundingError:
        raise
    except Exception as error:
        raise GroundingError(f"catalog retrieval failed: {error}") from error


def _compact_asset(asset: dict[str, Any]) -> dict[str, str]:
    if not isinstance(asset, dict):
        raise GroundingError("catalog retrieval returned a malformed asset")
    return {
        "display_name": _optional_string(asset, "display_name"),
        "linked_resource": _optional_string(asset, "linked_resource"),
        "description": _optional_string(asset, "description"),
        "entry_type": _optional_string(asset, "entry_type"),
    }


def _optional_string(asset: dict[str, Any], key: str) -> str:
    value = asset.get(key)
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    raise GroundingError(f"catalog asset field {key} must be a string")
