"""Run Dataplex scans that enrich BigQuery metadata for data agents.

This script creates and runs Dataplex DataScan resources for the configured
BigQuery dataset and tables. Run it before creating or updating CA API data
agents so Gemini has profile results, table documentation, and dataset insights
available through BigQuery and Knowledge Catalog.

Running the scans is only half the job: by default the generated documentation
is also published back to each table, so it is visible where people actually
look.

- ``publish_documentation_to_table`` sets the Dataplex publish labels, which
  surface the generated descriptions on the BigQuery Studio "Insights" tab.
- ``apply_documentation_to_schema`` writes the generated table overview and
  column descriptions into the table schema itself. This is the programmatic
  equivalent of the console "Save to schema" action, and it requires ``--wait``
  (the descriptions only exist once the documentation job has finished).

The generic Dataplex REST plumbing is kept byte-compatible with
``bq_cross_cloud_lakehouse/agent/scripts/enrich_bigquery_metadata.py`` so the
two stay easy to sync.

Usage::

    uv run python scripts/enrich_bigquery_metadata.py
    uv run python scripts/enrich_bigquery_metadata.py --wait
    uv run python scripts/enrich_bigquery_metadata.py --dry-run
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urlencode

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config.agent_definitions import unique_table_ids  # noqa: E402

load_dotenv(override=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT")
DATASET_ID = os.getenv("BIGQUERY_DATASET_ID")
DATAPLEX_LOCATION = os.getenv("DATAPLEX_LOCATION", os.getenv("BIGQUERY_LOCATION", "us"))
DATAPLEX_SCAN_PREFIX = os.getenv("DATAPLEX_SCAN_PREFIX", "bq-caapi")

DATAPLEX_BASE = "https://dataplex.googleapis.com/v1"
BIGQUERY_BASE = "https://bigquery.googleapis.com/bigquery/v2"
OPERATION_POLL_INTERVAL = 2
SUCCESS_JOB_STATES = {"SUCCEEDED", "SUCCEEDED_WITH_ERRORS"}
TERMINAL_JOB_STATES = {
    "SUCCEEDED",
    "SUCCEEDED_WITH_ERRORS",
    "FAILED",
    "FAILURE",
    "CANCELLED",
    "CANCELED",
}
PROFILE_MODES = {"LIGHTWEIGHT", "STANDARD"}

# BigQuery multi-regions are NOT valid Dataplex locations. Dataplex DataScans
# must live in a single region, even when the BigQuery dataset they scan is in a
# multi-region. Passing "us" yields an opaque 400 "Malformed name", so catch it
# here and say what to do instead.
BIGQUERY_MULTI_REGIONS = {"us", "eu"}
MULTI_REGION_SUGGESTIONS = {"us": "us-central1", "eu": "europe-west1"}


def validate_dataplex_location(location: str) -> None:
    """Reject BigQuery multi-regions, which Dataplex does not accept.

    Args:
        location: The configured Dataplex location.

    Raises:
        ValueError: If the location is a BigQuery multi-region.
    """
    if location.strip().lower() not in BIGQUERY_MULTI_REGIONS:
        return
    suggestion = MULTI_REGION_SUGGESTIONS[location.strip().lower()]
    raise ValueError(
        f"DATAPLEX_LOCATION={location!r} is a BigQuery multi-region, not a "
        f"Dataplex location. Dataplex DataScans must be created in a single "
        f"region even when the BigQuery dataset they scan is multi-region. "
        f"Set DATAPLEX_LOCATION={suggestion!r} (a region inside the "
        f"{location.upper()} multi-region) and re-run."
    )


def get_access_token() -> str:
    """Get an access token via Application Default Credentials.

    Returns:
        Bearer token string.

    Raises:
        RuntimeError: If the token cannot be retrieved.
    """
    result = subprocess.run(
        ["gcloud", "auth", "application-default", "print-access-token"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Failed to get access token: {result.stderr.strip()}")
    return result.stdout.strip()


def request(
    method: str,
    url: str,
    token: str,
    payload: dict | None = None,
) -> dict:
    """Execute an authenticated Dataplex REST request.

    Args:
        method: HTTP method.
        url: Full request URL.
        token: Bearer token.
        payload: Optional JSON payload.

    Returns:
        Parsed JSON response.

    Raises:
        RuntimeError: If curl fails, JSON is invalid, or API returns an error.
    """
    cmd = [
        "curl",
        "-s",
        "-X",
        method,
        "-H",
        f"Authorization: Bearer {token}",
        "-H",
        "Content-Type: application/json",
        "-H",
        f"X-Goog-User-Project: {PROJECT_ID}",
        url,
    ]
    if payload is not None:
        cmd += ["-d", json.dumps(payload)]

    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(f"curl failed: {result.stderr.strip()}")

    try:
        data = json.loads(result.stdout or "{}")
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Invalid JSON response: {result.stdout[:200]}") from e

    if "error" in data:
        raise RuntimeError(
            f"API error {data['error'].get('code')}: {data['error'].get('message')}"
        )
    return data


def bigquery_dataset_resource(project_id: str, dataset_id: str) -> str:
    """Build a BigQuery dataset resource URI for Dataplex scans.

    Args:
        project_id: Google Cloud project ID.
        dataset_id: BigQuery dataset ID.

    Returns:
        Service-qualified dataset resource URI.
    """
    return f"//bigquery.googleapis.com/projects/{project_id}/datasets/{dataset_id}"


def bigquery_table_resource(project_id: str, dataset_id: str, table_id: str) -> str:
    """Build a BigQuery table resource URI for Dataplex scans.

    Args:
        project_id: Google Cloud project ID.
        dataset_id: BigQuery dataset ID.
        table_id: BigQuery table ID.

    Returns:
        Service-qualified table resource URI.
    """
    return (
        f"//bigquery.googleapis.com/projects/{project_id}/datasets/{dataset_id}"
        f"/tables/{table_id}"
    )


def normalize_results_table(value: str | None) -> str | None:
    """Normalize a BigQuery results table setting to a resource URI.

    Args:
        value: None, a service-qualified URI, or project.dataset.table.

    Returns:
        Normalized service-qualified table URI, or None.

    Raises:
        ValueError: If the value is not in a supported format.
    """
    if not value:
        return None
    if value.startswith("//bigquery.googleapis.com/"):
        return value

    parts = value.split(".")
    if len(parts) != 3:
        raise ValueError(
            "Profile results table must be a BigQuery resource URI or "
            "project.dataset.table."
        )
    project_id, dataset_id, table_id = parts
    return bigquery_table_resource(project_id, dataset_id, table_id)


def scan_id(kind: str, dataset_id: str, table_id: str | None = None) -> str:
    """Build a deterministic Dataplex scan ID.

    Args:
        kind: Logical scan kind.
        dataset_id: BigQuery dataset ID.
        table_id: Optional BigQuery table ID.

    Returns:
        Dataplex-compatible scan ID.
    """
    parts = [DATAPLEX_SCAN_PREFIX, kind, dataset_id]
    if table_id:
        parts.append(table_id)
    raw = "-".join(parts).lower()
    slug = re.sub(r"[^a-z0-9-]", "-", raw)
    slug = re.sub(r"-+", "-", slug).strip("-")
    if not slug or not slug[0].isalpha():
        slug = f"scan-{slug}"
    if len(slug) <= 63:
        return slug
    digest = hashlib.sha1(slug.encode("utf-8")).hexdigest()[:8]
    return f"{slug[:54].rstrip('-')}-{digest}"


def build_data_documentation_payload(
    resource: str,
    generation_scope: str | None,
    publish: bool,
) -> dict:
    """Build a Dataplex data documentation scan payload.

    Args:
        resource: BigQuery dataset or table resource URI.
        generation_scope: Dataplex DataDocumentationSpec generation scope for
            table scans. Pass ``None`` for dataset-level scans, which do not
            support generation scopes.
        publish: Whether to publish results to Dataplex Catalog.

    Returns:
        DataScan create payload.
    """
    spec: dict = {"catalogPublishingEnabled": publish}
    if generation_scope:
        spec["generationScopes"] = [generation_scope]
    return {
        "data": {"resource": resource},
        "executionSpec": {"trigger": {"onDemand": {}}},
        "type": "DATA_DOCUMENTATION",
        "dataDocumentationSpec": spec,
    }


def build_data_profile_payload(
    resource: str,
    mode: str,
    publish: bool,
    sampling_percent: float | None = None,
    export_results_table: str | None = None,
) -> dict:
    """Build a Dataplex data profile scan payload.

    Args:
        resource: BigQuery table resource URI.
        mode: Data profile execution mode.
        publish: Whether to publish profile results to Dataplex Catalog.
        sampling_percent: Optional sampling percentage for STANDARD mode.
        export_results_table: Optional BigQuery table resource for exported profile
            results.

    Returns:
        DataScan create payload.

    Raises:
        ValueError: If a LIGHTWEIGHT scan includes unsupported standard settings.
    """
    data_profile_spec: dict = {
        "mode": mode,
        "catalogPublishingEnabled": publish,
    }
    if sampling_percent is not None:
        if mode == "LIGHTWEIGHT":
            raise ValueError("sampling_percent is not supported in LIGHTWEIGHT mode.")
        data_profile_spec["samplingPercent"] = sampling_percent
    if export_results_table:
        data_profile_spec["postScanActions"] = {
            "bigqueryExport": {"resultsTable": export_results_table}
        }

    return {
        "data": {"resource": resource},
        "executionSpec": {"trigger": {"onDemand": {}}},
        "type": "DATA_PROFILE",
        "dataProfileSpec": data_profile_spec,
    }


def data_scans_url() -> str:
    """Return the Dataplex dataScans collection URL."""
    return (
        f"{DATAPLEX_BASE}/projects/{PROJECT_ID}/locations/{DATAPLEX_LOCATION}/dataScans"
    )


def data_scan_resource_name(scan_name: str) -> str:
    """Return the relative Dataplex DataScan resource name."""
    return f"projects/{PROJECT_ID}/locations/{DATAPLEX_LOCATION}/dataScans/{scan_name}"


def operation_url(operation_name: str) -> str:
    """Build a Dataplex long-running operation URL.

    Args:
        operation_name: Relative or absolute operation name from a Dataplex API
            response.

    Returns:
        Operation GET URL.
    """
    if operation_name.startswith("https://"):
        return operation_name
    return f"{DATAPLEX_BASE}/{operation_name}"


def wait_for_operation(operation: dict, token: str) -> dict:
    """Wait for a Dataplex create/update operation to finish.

    This waits only for the lightweight DataScan resource mutation, not for the
    metadata scan job itself.

    Args:
        operation: Long-running operation response.
        token: Bearer token.

    Returns:
        Final operation response.

    Raises:
        RuntimeError: If the operation reports an error.
    """
    operation_name = operation.get("name")
    if not operation_name:
        return operation

    data = operation
    while True:
        if data.get("error"):
            error = data["error"]
            raise RuntimeError(
                f"Dataplex operation {operation_name} failed: "
                f"{error.get('message', error)}"
            )
        if data.get("done"):
            return data

        logger.info("Waiting for Dataplex operation: %s", operation_name)
        time.sleep(OPERATION_POLL_INTERVAL)
        data = request("GET", operation_url(operation_name), token)


def update_mask_for_payload(payload: dict) -> str:
    """Build a DataScan patch update mask for the payload.

    Args:
        payload: DataScan payload.

    Returns:
        Comma-separated update mask.
    """
    fields = ["data", "executionSpec"]
    if "dataDocumentationSpec" in payload:
        fields.append("dataDocumentationSpec")
    if "dataProfileSpec" in payload:
        fields.append("dataProfileSpec")
    return ",".join(fields)


def upsert_scan(
    scan_name: str,
    payload: dict,
    token: str,
    dry_run: bool,
) -> None:
    """Create or update a Dataplex scan and wait for that mutation.

    Args:
        scan_name: Dataplex data scan ID.
        payload: DataScan create/update payload.
        token: Bearer token.
        dry_run: Whether to log payloads without calling Dataplex.
    """
    if dry_run:
        logger.info(
            "Dry-run upsert scan %s:\n%s",
            scan_name,
            json.dumps(payload, indent=2),
        )
        return

    url = f"{data_scans_url()}?dataScanId={scan_name}"
    try:
        operation = request("POST", url, token, payload)
        wait_for_operation(operation, token)
        logger.info("Created Dataplex scan: %s", scan_name)
    except RuntimeError as e:
        if "already exists" in str(e).lower() or "already_exists" in str(e).lower():
            update_payload = {**payload, "name": data_scan_resource_name(scan_name)}
            query = urlencode({"updateMask": update_mask_for_payload(payload)})
            operation = request(
                "PATCH",
                f"{data_scans_url()}/{scan_name}?{query}",
                token,
                update_payload,
            )
            wait_for_operation(operation, token)
            logger.info("Updated Dataplex scan: %s", scan_name)
            return
        raise


def run_scan(scan_name: str, token: str, dry_run: bool) -> str | None:
    """Run an on-demand Dataplex scan.

    Args:
        scan_name: Dataplex data scan ID.
        token: Bearer token.
        dry_run: Whether to skip the API call.

    Returns:
        DataScanJob ID, or None in dry-run mode.
    """
    if dry_run:
        logger.info("Dry-run run scan: %s", scan_name)
        return None

    data = request("POST", f"{data_scans_url()}/{scan_name}:run", token)
    job_name = data.get("job", {}).get("name") or data.get("name", "")
    job_id = job_name.split("/")[-1] if job_name else ""
    logger.info("Started Dataplex scan: %s job=%s", scan_name, job_id)
    return job_id or None


def wait_for_scan_job(
    scan_name: str,
    job_id: str,
    token: str,
    poll_interval: int,
) -> dict:
    """Poll a Dataplex scan job until it reaches a terminal state.

    Args:
        scan_name: Dataplex data scan ID.
        job_id: DataScanJob ID.
        token: Bearer token.
        poll_interval: Seconds between polling attempts.

    Returns:
        Final job response.

    Raises:
        RuntimeError: If the scan finishes in a failure state.
    """
    url = f"{data_scans_url()}/{scan_name}/jobs/{job_id}?view=FULL"
    while True:
        data = request("GET", url, token)
        state = data.get("state") or data.get("status", {}).get("state") or "UNKNOWN"
        logger.info(
            "Dataplex scan status: %s job=%s state=%s",
            scan_name,
            job_id,
            state,
        )
        if state in TERMINAL_JOB_STATES:
            if state not in SUCCESS_JOB_STATES:
                raise RuntimeError(
                    f"Dataplex scan {scan_name} job {job_id} finished with {state}."
                )
            if state == "SUCCEEDED_WITH_ERRORS":
                logger.warning(
                    "Dataplex scan %s job=%s succeeded with errors.",
                    scan_name,
                    job_id,
                )
            return data
        time.sleep(poll_interval)


def create_and_run_scan(
    scan_name: str,
    payload: dict,
    token: str,
    wait: bool,
    poll_interval: int,
    dry_run: bool,
) -> dict | None:
    """Create, run, and optionally wait for a Dataplex scan.

    Args:
        scan_name: Dataplex data scan ID.
        payload: DataScan create payload.
        token: Bearer token.
        wait: Whether to poll job completion.
        poll_interval: Seconds between polling attempts.
        dry_run: Whether to skip API calls.

    Returns:
        Final job response if wait is enabled, otherwise None.
    """
    upsert_scan(scan_name, payload, token, dry_run)
    job_id = run_scan(scan_name, token, dry_run)
    if wait and job_id:
        return wait_for_scan_job(scan_name, job_id, token, poll_interval)
    return None


def count_non_partitioned_tables(dataset_id: str, token: str) -> int:
    """Count non-partitioned base tables in a dataset.

    Dataset-level data documentation requires at least two of these. Checking up
    front turns an opaque Dataplex 400 into a clear, cheap skip.

    Args:
        dataset_id: BigQuery dataset ID.
        token: Bearer token.

    Returns:
        Number of non-partitioned tables, or -1 if the check could not run.
    """
    url = f"{BIGQUERY_BASE}/projects/{PROJECT_ID}/datasets/{dataset_id}/tables"
    try:
        listing = request("GET", url, token)
    except RuntimeError as e:
        logger.debug("Could not list tables in %s: %s", dataset_id, e)
        return -1

    count = 0
    for table in listing.get("tables", []):
        if table.get("type") not in (None, "TABLE"):
            continue
        if table.get("timePartitioning") or table.get("rangePartitioning"):
            continue
        count += 1
    return count


def documentation_labels(scan_name: str) -> dict[str, str]:
    """Build the labels that publish documentation results to a BigQuery table.

    Attaching these labels surfaces the generated table/column descriptions on
    the BigQuery Studio "Insights" tab.

    Args:
        scan_name: The data documentation scan ID whose results to publish.

    Returns:
        Label key/value pairs to set on the table.
    """
    return {
        "dataplex-data-documentation-published-scan": scan_name,
        "dataplex-data-documentation-published-project": PROJECT_ID,
        "dataplex-data-documentation-published-location": DATAPLEX_LOCATION,
    }


def publish_documentation_to_table(
    dataset_id: str,
    table_id: str,
    scan_name: str,
    token: str,
    dry_run: bool,
) -> None:
    """Publish documentation scan results back to a BigQuery table.

    This patches the table's labels so the generated descriptions surface on the
    BigQuery Studio "Insights" tab.

    Args:
        dataset_id: BigQuery dataset ID.
        table_id: BigQuery table ID.
        scan_name: The data documentation scan ID whose results to publish.
        token: Bearer token.
        dry_run: Whether to skip the API call.
    """
    labels = documentation_labels(scan_name)
    if dry_run:
        logger.info(
            "Dry-run publish documentation to table %s.%s labels=%s",
            dataset_id,
            table_id,
            labels,
        )
        return

    url = (
        f"{BIGQUERY_BASE}/projects/{PROJECT_ID}/datasets/{dataset_id}/tables/{table_id}"
    )
    request("PATCH", url, token, {"labels": labels})
    logger.info(
        "Published documentation to table %s.%s (visible on the Insights tab).",
        dataset_id,
        table_id,
    )


def extract_table_documentation(job: dict | None) -> tuple[str, dict[str, str]]:
    """Extract the generated overview and column descriptions from a docs job.

    Args:
        job: A completed DATA_DOCUMENTATION scan job (``view=FULL``), or None
            (for example when the run did not ``--wait``).

    Returns:
        A ``(table_overview, {column_name: description})`` tuple; empty when the
        result is unavailable.
    """
    if not job:
        return "", {}
    table_result = job.get("dataDocumentationResult", {}).get("tableResult", {})
    overview = table_result.get("overview", "") or ""
    fields = table_result.get("schema", {}).get("fields", []) or []
    descriptions = {
        field_["name"]: field_.get("description", "")
        for field_ in fields
        if field_.get("name") and field_.get("description")
    }
    return overview, descriptions


def merge_field_descriptions(
    existing_fields: list[dict],
    descriptions: dict[str, str],
) -> list[dict]:
    """Return schema fields with generated descriptions merged in.

    Existing field attributes are preserved; ``description`` is set only for
    fields present in the descriptions map.

    Args:
        existing_fields: Current table schema fields (from ``tables.get``).
        descriptions: Column name to generated description.

    Returns:
        A new list of schema field dicts.
    """
    merged: list[dict] = []
    for field_ in existing_fields:
        new_field = dict(field_)
        desc = descriptions.get(new_field.get("name", ""))
        if desc:
            new_field["description"] = desc
        merged.append(new_field)
    return merged


def get_table(dataset_id: str, table_id: str, token: str) -> dict:
    """Fetch a BigQuery table resource.

    Args:
        dataset_id: BigQuery dataset ID.
        table_id: BigQuery table ID.
        token: Bearer token.

    Returns:
        The table resource JSON.
    """
    url = (
        f"{BIGQUERY_BASE}/projects/{PROJECT_ID}/datasets/{dataset_id}/tables/{table_id}"
    )
    return request("GET", url, token)


def apply_documentation_to_schema(
    dataset_id: str,
    table_id: str,
    overview: str,
    descriptions: dict[str, str],
    token: str,
    dry_run: bool,
) -> None:
    """Write generated table/column descriptions into the table schema.

    This is the programmatic equivalent of the console "Save to schema" action,
    so descriptions appear in the table's schema and are picked up as agent
    context.

    Args:
        dataset_id: BigQuery dataset ID.
        table_id: BigQuery table ID.
        overview: Generated table overview to set as the table description.
        descriptions: Column name to generated description.
        token: Bearer token.
        dry_run: Whether to skip the API call.
    """
    if not overview and not descriptions:
        logger.info(
            "No generated descriptions to write for %s.%s (run with --wait to "
            "capture and save them to the schema).",
            dataset_id,
            table_id,
        )
        return
    if dry_run:
        logger.info(
            "Dry-run write descriptions to %s.%s schema (%d columns).",
            dataset_id,
            table_id,
            len(descriptions),
        )
        return

    table = get_table(dataset_id, table_id, token)
    fields = table.get("schema", {}).get("fields", []) or []
    patch: dict = {"schema": {"fields": merge_field_descriptions(fields, descriptions)}}
    if overview:
        patch["description"] = overview
    url = (
        f"{BIGQUERY_BASE}/projects/{PROJECT_ID}/datasets/{dataset_id}/tables/{table_id}"
    )
    request("PATCH", url, token, patch)
    logger.info(
        "Wrote overview + %d column descriptions into %s.%s schema.",
        len(descriptions),
        dataset_id,
        table_id,
    )


def log_view_links(dataset_id: str, table_ids: list[str]) -> None:
    """Log where to view the generated metadata for the enriched tables.

    Args:
        dataset_id: BigQuery dataset ID.
        table_ids: Table IDs that were enriched.
    """
    logger.info("View generated metadata:")
    for table_id in table_ids:
        logger.info(
            "  BigQuery Studio Insights: https://console.cloud.google.com/bigquery"
            "?project=%s&ws=!1m5!1m4!4m3!1s%s!2s%s!3s%s",
            PROJECT_ID,
            PROJECT_ID,
            dataset_id,
            table_id,
        )
    logger.info(
        "  Knowledge Catalog search: "
        "https://console.cloud.google.com/dataplex/search?project=%s",
        PROJECT_ID,
    )


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments.

    Returns:
        Parsed arguments.
    """
    parser = argparse.ArgumentParser(
        description="Run Dataplex profile and documentation scans for CA API agents."
    )
    env_profile_mode = os.getenv("DATA_PROFILE_MODE", "STANDARD").upper()
    if env_profile_mode not in PROFILE_MODES:
        raise ValueError(
            f"DATA_PROFILE_MODE must be LIGHTWEIGHT or STANDARD: {env_profile_mode}"
        )

    parser.add_argument(
        "--dataset",
        default=None,
        help=(
            "BigQuery dataset to enrich. Overrides BIGQUERY_DATASET_ID. Needed "
            "because .env is loaded with override=True, so a shell variable "
            "cannot win against it."
        ),
    )
    parser.add_argument(
        "--tables",
        nargs="+",
        default=unique_table_ids(),
        help="BigQuery tables to enrich. Defaults to all configured agent tables.",
    )
    parser.add_argument(
        "--generation-scope",
        choices=(
            "ALL",
            "TABLE_AND_COLUMN_DESCRIPTIONS",
            "SQL_QUERIES",
            "BUSINESS_GLOSSARY_TERM_ASSOCIATIONS",
        ),
        default="ALL",
        help="Data documentation generation scope for table scans.",
    )
    parser.add_argument(
        "--profile-mode",
        choices=("LIGHTWEIGHT", "STANDARD"),
        default=env_profile_mode,
        help="Dataplex data profile mode.",
    )
    parser.add_argument(
        "--sampling-percent",
        type=float,
        default=(
            float(os.getenv("DATA_PROFILE_SAMPLING_PERCENT"))
            if os.getenv("DATA_PROFILE_SAMPLING_PERCENT")
            else None
        ),
        help="Sampling percentage for STANDARD profile scans.",
    )
    parser.add_argument(
        "--profile-results-table",
        default=os.getenv("DATA_PROFILE_RESULTS_TABLE"),
        help="Optional profile export table as URI or project.dataset.table.",
    )
    parser.add_argument(
        "--skip-profile",
        action="store_true",
        help="Skip table-level data profile scans.",
    )
    parser.add_argument(
        "--skip-table-docs",
        action="store_true",
        help="Skip table-level data documentation scans.",
    )
    parser.add_argument(
        "--skip-dataset-docs",
        action="store_true",
        help="Skip dataset-level data documentation scan.",
    )
    parser.add_argument(
        "--no-publish",
        action="store_true",
        help="Do not publish scan results to Knowledge Catalog or back to the table.",
    )
    parser.add_argument(
        "--skip-schema-write-back",
        action="store_true",
        help="Publish to Knowledge Catalog but do not write generated descriptions "
        "into the table schema. Requires --wait to have any effect either way.",
    )
    parser.add_argument(
        "--wait",
        action="store_true",
        help="Wait for each Dataplex scan job to finish.",
    )
    parser.add_argument(
        "--poll-interval",
        type=int,
        default=5,
        help=(
            "Seconds between Dataplex job polling attempts. Profile jobs finish "
            "in about 5s and documentation jobs in about 60s, so a large "
            "interval spends most of the wall clock asleep."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Log Dataplex payloads without creating or running scans.",
    )
    return parser.parse_args()


def enrich_table(
    table_id: str,
    args: argparse.Namespace,
    token: str,
    sampling_percent: float | None,
    export_results_table: str | None,
    publish: bool,
) -> None:
    """Run profile + documentation scans for one table and publish the results.

    Args:
        table_id: BigQuery table ID.
        args: Parsed CLI arguments.
        token: Bearer token.
        sampling_percent: Resolved sampling percentage (STANDARD mode).
        export_results_table: Optional profile export table URI.
        publish: Whether to publish results.
    """
    table_resource = bigquery_table_resource(PROJECT_ID, DATASET_ID, table_id)

    if not args.skip_profile:
        name = scan_id("profile", DATASET_ID, table_id)
        payload = build_data_profile_payload(
            resource=table_resource,
            mode=args.profile_mode,
            publish=publish,
            sampling_percent=sampling_percent,
            export_results_table=export_results_table,
        )
        create_and_run_scan(
            name, payload, token, args.wait, args.poll_interval, args.dry_run
        )

    if args.skip_table_docs:
        return

    name = scan_id("table-docs", DATASET_ID, table_id)
    payload = build_data_documentation_payload(
        resource=table_resource,
        generation_scope=args.generation_scope,
        publish=publish,
    )
    job = create_and_run_scan(
        name, payload, token, args.wait, args.poll_interval, args.dry_run
    )
    if not publish:
        return

    # Publish to Knowledge Catalog / the Insights tab (labels) ...
    publish_documentation_to_table(DATASET_ID, table_id, name, token, args.dry_run)
    # ... and write the generated descriptions into the table schema.
    if not args.skip_schema_write_back:
        overview, descriptions = extract_table_documentation(job)
        apply_documentation_to_schema(
            DATASET_ID, table_id, overview, descriptions, token, args.dry_run
        )


def main() -> None:
    """Create and run Dataplex metadata enrichment scans."""
    global DATASET_ID

    if not PROJECT_ID:
        raise ValueError("GOOGLE_CLOUD_PROJECT must be set.")
    validate_dataplex_location(DATAPLEX_LOCATION)

    args = parse_args()
    if args.dataset:
        DATASET_ID = args.dataset
    if not DATASET_ID:
        raise ValueError("Set BIGQUERY_DATASET_ID or pass --dataset.")
    export_results_table = normalize_results_table(args.profile_results_table)
    sampling_percent = args.sampling_percent
    if args.profile_mode == "STANDARD" and sampling_percent is None:
        sampling_percent = 10.0
    token = "" if args.dry_run else get_access_token()
    publish = not args.no_publish

    tables = list(args.tables)
    logger.info(
        "Enriching %d tables (project=%s, dataset=%s, location=%s).",
        len(tables),
        PROJECT_ID,
        DATASET_ID,
        DATAPLEX_LOCATION,
    )
    if publish and not args.skip_schema_write_back and not args.wait:
        logger.warning(
            "Schema write-back needs --wait: without it the documentation job "
            "has not finished, so no descriptions are available to save."
        )

    skip_dataset_docs = args.skip_dataset_docs
    if not skip_dataset_docs and not args.dry_run:
        table_count = count_non_partitioned_tables(DATASET_ID, token)
        if 0 <= table_count < 2:
            logger.info(
                "Skipping dataset-level documentation for %s: it has %d "
                "non-partitioned table(s) and Dataplex requires at least 2.",
                DATASET_ID,
                table_count,
            )
            skip_dataset_docs = True

    if not skip_dataset_docs:
        name = scan_id("dataset-docs", DATASET_ID)
        payload = build_data_documentation_payload(
            resource=bigquery_dataset_resource(PROJECT_ID, DATASET_ID),
            generation_scope=None,
            publish=publish,
        )
        try:
            create_and_run_scan(
                name, payload, token, args.wait, args.poll_interval, args.dry_run
            )
        except RuntimeError as e:
            # Dataset-level documentation needs at least 2 non-partitioned
            # tables. That is a Dataplex limitation, not a configuration error,
            # and it must not block the table-level scans that actually carry
            # the column descriptions.
            if "at least 2 non-partitioned tables" not in str(e):
                raise
            logger.warning(
                "Skipping dataset-level documentation for %s: Dataplex requires "
                "at least 2 non-partitioned tables in the dataset. Table-level "
                "profile and documentation scans continue normally.",
                DATASET_ID,
            )

    for table_id in tables:
        enrich_table(
            table_id, args, token, sampling_percent, export_results_table, publish
        )

    if not args.dry_run:
        log_view_links(DATASET_ID, tables)
    logger.info("Metadata enrichment finished.")


if __name__ == "__main__":
    main()
