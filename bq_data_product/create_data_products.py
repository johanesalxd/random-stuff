#!/usr/bin/env python3
"""Dataplex Data Product demo: TheLook E-Commerce.

Creates three Dataplex Data Products backed by authorized BigQuery views that
reference the public `bigquery-public-data.thelook_ecommerce` dataset.

Why authorized views?
  The Dataplex Data Products API requires the asset creator to hold
  getIamPolicy and setIamPolicy on every BigQuery resource added as an asset.
  Those permissions cannot be granted on bigquery-public-data tables.
  Creating thin views in the user's own project satisfies this constraint while
  keeping zero data copies — queries still read from the public dataset.

Two-phase setup
  1. setup  — create a BigQuery dataset + authorized views in PROJECT_ID.
  2. create — provision the three Dataplex Data Products pointing at those views.

Cleanup is the reverse:
  cleanup       — delete all three data products, then drop the BQ dataset+views.
  cleanup-scans — delete all thelook-profile-* DataScans (run separately).

Usage:
    uv run create_data_products.py setup          # create BQ dataset + views
    uv run create_data_products.py create         # provision data products
    uv run create_data_products.py profile        # create + trigger 7 profile scans
    uv run create_data_products.py search         # search catalog for data products
    uv run create_data_products.py list           # list data products in scope
    uv run create_data_products.py cleanup        # delete data products + BQ views
    uv run create_data_products.py cleanup-scans  # delete profile scans

Or run multiple phases at once:
    uv run create_data_products.py setup create
"""

import argparse
import logging
import os
import subprocess
import sys
import time

import requests
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Configuration — loaded from .env
# ---------------------------------------------------------------------------

load_dotenv()


def _require_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        print(
            f"ERROR: '{name}' is not set. "
            "Copy .env.example to .env and fill in your project details.",
            file=sys.stderr,
        )
        sys.exit(1)
    return value


PROJECT_ID = _require_env("PROJECT_ID")
PROJECT_NUMBER = _require_env("PROJECT_NUMBER")
LOCATION = os.environ.get("LOCATION", "us").strip()
# DataScan requires a regional endpoint; multi-region "us" is not supported.
SCAN_LOCATION = os.environ.get("SCAN_LOCATION", "us-central1").strip()
OWNER_EMAIL = _require_env("OWNER_EMAIL")

# BigQuery region must match the Dataplex location.
# The public dataset is US multi-region → BQ_LOCATION = "US".
_BQ_LOCATION = LOCATION.upper()  # "us" → "US" for the BQ API

# BigQuery dataset that will hold the authorized views.
_VIEWS_DATASET = "thelook_ecommerce_demo"

# Public source dataset (read-only reference — no data is copied).
_SOURCE_PROJECT = "bigquery-public-data"
_SOURCE_DATASET = "thelook_ecommerce"

# Full resource prefix for views in the user's project.
_VIEW_PREFIX = (
    f"//bigquery.googleapis.com/projects/{PROJECT_ID}/datasets/{_VIEWS_DATASET}/tables"
)

DATAPLEX_BASE = "https://dataplex.googleapis.com/v1"
BQ_BASE = "https://bigquery.googleapis.com/bigquery/v2"

# ---------------------------------------------------------------------------
# View definitions — thin SELECT * wrappers over public tables
# ---------------------------------------------------------------------------

# Tables to expose (all available in bigquery-public-data.thelook_ecommerce).
_TABLES = [
    "orders",
    "order_items",
    "products",
    "inventory_items",
    "distribution_centers",
    "users",
    "events",
]


# SQL template for each authorized view.
def _view_sql(table: str) -> str:
    return f"SELECT * FROM `{_SOURCE_PROJECT}.{_SOURCE_DATASET}.{table}`"


# SQL prefix used in sample queries embedded in documentation.
_SQL = f"`{PROJECT_ID}.{_VIEWS_DATASET}"

# ---------------------------------------------------------------------------
# Data product definitions
# ---------------------------------------------------------------------------

DATA_PRODUCTS: list[dict] = [
    {
        "id": "thelook-ecommerce-sales",
        "display_name": "E-Commerce Sales",
        "description": (
            "Order lifecycle and line-item details for the TheLook fictitious "
            "online store. Covers order creation, shipping, delivery, and return "
            "events together with per-item revenue and cost breakdown."
        ),
        "assets": [
            {
                "id": "orders",
                "resource": f"{_VIEW_PREFIX}/orders",
                "description": (
                    "Order-level records including status, timestamps, and item count."
                ),
            },
            {
                "id": "order-items",
                "resource": f"{_VIEW_PREFIX}/order_items",
                "description": (
                    "Line-item details with sale price, cost, and return status."
                ),
            },
        ],
        "contract_frequency": "Daily",
        "documentation": (
            "## E-Commerce Sales\n\n"
            "Core transactional data for the TheLook online store. "
            "Use this product to analyse revenue, fulfilment performance, "
            "and return rates.\n\n"
            "### Assets\n\n"
            "| View | Source table | Grain | Rows (approx) |\n"
            "|------|-------------|-------|---------------|\n"
            "| `orders` | `bigquery-public-data.thelook_ecommerce.orders` |"
            " One row per order | 124 k |\n"
            "| `order_items` | `bigquery-public-data.thelook_ecommerce.order_items` |"
            " One row per line item | 181 k |\n\n"
            "### Sample queries\n\n"
            "Open these in BigQuery Studio — no access request needed.\n\n"
            "**Monthly revenue:**\n"
            "```sql\n"
            "SELECT\n"
            "  DATE_TRUNC(created_at, MONTH) AS month,\n"
            "  COUNT(DISTINCT order_id) AS orders,\n"
            "  ROUND(SUM(sale_price), 2) AS revenue\n"
            f"FROM {_SQL}.order_items`\n"
            "WHERE status != 'Cancelled'\n"
            "GROUP BY 1\n"
            "ORDER BY 1;\n"
            "```\n\n"
            "**Return rate by product category:**\n"
            "```sql\n"
            "SELECT\n"
            "  p.category,\n"
            "  ROUND(\n"
            "    COUNTIF(oi.returned_at IS NOT NULL) / COUNT(*), 4\n"
            "  ) AS return_rate\n"
            f"FROM {_SQL}.order_items` oi\n"
            f"JOIN {_SQL}.products` p USING (product_id)\n"
            "GROUP BY 1\n"
            "ORDER BY 2 DESC;\n"
            "```\n"
        ),
    },
    {
        "id": "thelook-product-catalog",
        "display_name": "Product Catalog",
        "description": (
            "Product information, inventory levels, and supply-chain data for "
            "TheLook. Covers the full journey from distribution center stock "
            "through to sold and returned inventory items."
        ),
        "assets": [
            {
                "id": "products",
                "resource": f"{_VIEW_PREFIX}/products",
                "description": (
                    "Master product list with brand, category, department, and cost."
                ),
            },
            {
                "id": "inventory-items",
                "resource": f"{_VIEW_PREFIX}/inventory_items",
                "description": (
                    "Per-unit inventory records tracking sold and outstanding stock."
                ),
            },
            {
                "id": "distribution-centers",
                "resource": f"{_VIEW_PREFIX}/distribution_centers",
                "description": (
                    "Geographic locations of TheLook's fulfillment centers."
                ),
            },
        ],
        "contract_frequency": "Weekly",
        "documentation": (
            "## Product Catalog\n\n"
            "Product master data and supply-chain information for TheLook. "
            "Use this product to analyse inventory health, stock levels, "
            "and distribution center utilisation.\n\n"
            "### Assets\n\n"
            "| View | Source table | Grain |\n"
            "|------|-------------|-------|\n"
            "| `products` | `bigquery-public-data.thelook_ecommerce.products` |"
            " One row per SKU |\n"
            "| `inventory_items` |"
            " `bigquery-public-data.thelook_ecommerce.inventory_items` |"
            " One row per physical unit |\n"
            "| `distribution_centers` |"
            " `bigquery-public-data.thelook_ecommerce.distribution_centers` |"
            " One row per fulfillment center |\n\n"
            "### Sample queries\n\n"
            "**Stock on hand by distribution center:**\n"
            "```sql\n"
            "SELECT\n"
            "  dc.name AS center,\n"
            "  COUNT(*) AS units_in_stock\n"
            f"FROM {_SQL}.inventory_items` ii\n"
            f"JOIN {_SQL}.distribution_centers` dc\n"
            "  ON ii.product_distribution_center_id = dc.id\n"
            "WHERE ii.sold_at IS NULL\n"
            "GROUP BY 1\n"
            "ORDER BY 2 DESC;\n"
            "```\n\n"
            "**Top 10 products by revenue:**\n"
            "```sql\n"
            "SELECT\n"
            "  p.name,\n"
            "  p.brand,\n"
            "  p.category,\n"
            "  ROUND(SUM(oi.sale_price), 2) AS revenue\n"
            f"FROM {_SQL}.order_items` oi\n"
            f"JOIN {_SQL}.products` p USING (product_id)\n"
            "WHERE oi.status NOT IN ('Cancelled', 'Returned')\n"
            "GROUP BY 1, 2, 3\n"
            "ORDER BY 4 DESC\n"
            "LIMIT 10;\n"
            "```\n"
        ),
    },
    {
        "id": "thelook-customer-analytics",
        "display_name": "Customer Analytics",
        "description": (
            "User demographics and website behavioural events for TheLook. "
            "Enables customer segmentation, cohort analysis, funnel analysis, "
            "and traffic-source attribution."
        ),
        "assets": [
            {
                "id": "users",
                "resource": f"{_VIEW_PREFIX}/users",
                "description": (
                    "Registered user profiles with age, gender, "
                    "location, and traffic source."
                ),
            },
            {
                "id": "events",
                "resource": f"{_VIEW_PREFIX}/events",
                "description": (
                    "Clickstream events capturing page views, "
                    "add-to-cart, and purchases."
                ),
            },
        ],
        "contract_frequency": "Daily",
        "documentation": (
            "## Customer Analytics\n\n"
            "User profile and behavioural event data for TheLook. "
            "Use this product to build customer segments, analyse funnels, "
            "and attribute traffic sources to conversions.\n\n"
            "### Assets\n\n"
            "| View | Source table | Grain |\n"
            "|------|-------------|-------|\n"
            "| `users` | `bigquery-public-data.thelook_ecommerce.users` |"
            " One row per registered user |\n"
            "| `events` | `bigquery-public-data.thelook_ecommerce.events` |"
            " One row per website event |\n\n"
            "### Sample queries\n\n"
            "**Users by country:**\n"
            "```sql\n"
            "SELECT\n"
            "  country,\n"
            "  COUNT(*) AS users\n"
            f"FROM {_SQL}.users`\n"
            "GROUP BY 1\n"
            "ORDER BY 2 DESC\n"
            "LIMIT 10;\n"
            "```\n\n"
            "**Event funnel:**\n"
            "```sql\n"
            "SELECT\n"
            "  event_type,\n"
            "  COUNT(*) AS events,\n"
            "  COUNT(DISTINCT user_id) AS unique_users\n"
            f"FROM {_SQL}.events`\n"
            "GROUP BY 1\n"
            "ORDER BY 2 DESC;\n"
            "```\n\n"
            "**New users by traffic source (last 30 days):**\n"
            "```sql\n"
            "SELECT\n"
            "  traffic_source,\n"
            "  COUNT(*) AS new_users\n"
            f"FROM {_SQL}.users`\n"
            "WHERE created_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 DAY)\n"
            "GROUP BY 1\n"
            "ORDER BY 2 DESC;\n"
            "```\n"
        ),
    },
]

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Auth — Application Default Credentials via gcloud
# ---------------------------------------------------------------------------


def _get_access_token() -> str:
    """Return a short-lived ADC token.

    Run `gcloud auth application-default login` once before using this script.
    """
    try:
        result = subprocess.run(
            ["gcloud", "auth", "print-access-token"],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as exc:
        logger.error(
            "Failed to obtain an ADC token. "
            "Run `gcloud auth application-default login` and try again.\n%s",
            exc.stderr.strip(),
        )
        sys.exit(1)


def _headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {_get_access_token()}",
        "Content-Type": "application/json",
    }


# ---------------------------------------------------------------------------
# LRO (Long-Running Operation) polling
# ---------------------------------------------------------------------------


def _wait_for_lro(operation_name: str, timeout_s: int = 120) -> dict:
    """Poll a Dataplex LRO until done; return the response body."""
    url = f"{DATAPLEX_BASE}/{operation_name}"
    deadline = time.monotonic() + timeout_s
    interval = 3

    logger.info("  Waiting for operation %s ...", operation_name.split("/")[-1])
    while time.monotonic() < deadline:
        resp = requests.get(url, headers=_headers(), timeout=30)
        resp.raise_for_status()
        body = resp.json()
        if body.get("done"):
            if "error" in body:
                raise RuntimeError(f"Operation failed: {body['error']}")
            return body.get("response", {})
        time.sleep(interval)
        interval = min(interval * 2, 15)

    raise TimeoutError(
        f"Operation {operation_name} did not complete within {timeout_s}s"
    )


# ---------------------------------------------------------------------------
# BigQuery helpers (REST API)
# ---------------------------------------------------------------------------


def _bq_dataset_url() -> str:
    return f"{BQ_BASE}/projects/{PROJECT_ID}/datasets/{_VIEWS_DATASET}"


def _create_bq_dataset() -> None:
    """Create the views dataset in the user's project. Idempotent on 409."""
    logger.info(
        "Creating BigQuery dataset '%s.%s' (location: %s) ...",
        PROJECT_ID,
        _VIEWS_DATASET,
        _BQ_LOCATION,
    )
    payload = {
        "datasetReference": {
            "projectId": PROJECT_ID,
            "datasetId": _VIEWS_DATASET,
        },
        "location": _BQ_LOCATION,
        "description": (
            "Authorized views over bigquery-public-data.thelook_ecommerce "
            "for the Dataplex Data Product demo."
        ),
    }
    resp = requests.post(
        f"{BQ_BASE}/projects/{PROJECT_ID}/datasets",
        headers=_headers(),
        json=payload,
        timeout=30,
    )
    if resp.status_code == 409:
        logger.warning("  Dataset already exists — skipping creation.")
        return
    resp.raise_for_status()
    logger.info("  Dataset created.")


def _create_bq_view(table: str) -> None:
    """Create an authorized view in the views dataset. Idempotent (insert-or-update)."""
    logger.info("  Creating view '%s' ...", table)
    payload = {
        "tableReference": {
            "projectId": PROJECT_ID,
            "datasetId": _VIEWS_DATASET,
            "tableId": table,
        },
        "view": {"query": _view_sql(table), "useLegacySql": False},
        "description": (
            f"Authorized view over `{_SOURCE_PROJECT}.{_SOURCE_DATASET}.{table}`."
        ),
    }
    # Try insert; if already exists (409), patch instead.
    resp = requests.post(
        f"{BQ_BASE}/projects/{PROJECT_ID}/datasets/{_VIEWS_DATASET}/tables",
        headers=_headers(),
        json=payload,
        timeout=30,
    )
    if resp.status_code == 409:
        logger.warning("  View '%s' already exists — skipping.", table)
        return
    resp.raise_for_status()
    logger.info("  View '%s' created.", table)


def _delete_bq_dataset() -> None:
    """Delete the views dataset and all its contents."""
    logger.info("Deleting BigQuery dataset '%s.%s' ...", PROJECT_ID, _VIEWS_DATASET)
    resp = requests.delete(
        _bq_dataset_url(),
        headers=_headers(),
        params={"deleteContents": "true"},
        timeout=30,
    )
    if resp.status_code == 404:
        logger.warning("  Dataset not found — skipping.")
        return
    resp.raise_for_status()
    logger.info("  Dataset deleted.")


# ---------------------------------------------------------------------------
# Dataplex URL builders
# ---------------------------------------------------------------------------


def _products_url() -> str:
    return f"{DATAPLEX_BASE}/projects/{PROJECT_ID}/locations/{LOCATION}/dataProducts"


def _product_url(pid: str) -> str:
    return f"{_products_url()}/{pid}"


def _assets_url(pid: str) -> str:
    return f"{_product_url(pid)}/dataAssets"


def _asset_url(pid: str, aid: str) -> str:
    return f"{_assets_url(pid)}/{aid}"


def _entry_url(pid: str) -> str:
    """Entry URL for attaching aspects (documentation, contract).

    Uses PROJECT_NUMBER (numeric), not PROJECT_ID (string).
    Ref: https://cloud.google.com/dataplex/docs/create-data-products#add-a-contract
    """
    entry_id = f"projects/{PROJECT_NUMBER}/locations/{LOCATION}/dataProducts/{pid}"
    return (
        f"{DATAPLEX_BASE}/projects/{PROJECT_ID}/locations/{LOCATION}"
        f"/entryGroups/@dataplex/entries/{entry_id}"
    )


# ---------------------------------------------------------------------------
# Dataplex create helpers
# ---------------------------------------------------------------------------


def _create_data_product(product: dict) -> None:
    """POST /dataProducts. Idempotent on 409."""
    logger.info(
        "Creating data product '%s' (%s) ...",
        product["display_name"],
        product["id"],
    )
    payload = {
        "display_name": product["display_name"],
        "description": product["description"],
        "owner_emails": [OWNER_EMAIL],
        "labels": {
            "domain": "ecommerce",
            "team": "data-platform",
            "source": "bigquery-public-data",
        },
    }
    resp = requests.post(
        _products_url(),
        headers=_headers(),
        params={"data_product_id": product["id"]},
        json=payload,
        timeout=30,
    )
    if resp.status_code == 409:
        logger.warning("  Already exists — skipping creation.")
        return
    resp.raise_for_status()
    _wait_for_lro(resp.json()["name"])
    logger.info("  Created.")


def _add_asset(pid: str, asset: dict) -> None:
    """POST /dataAssets. Idempotent on 409."""
    table_name = asset["resource"].split("/")[-1]
    logger.info("  Adding asset '%s' (view: %s) ...", asset["id"], table_name)
    resp = requests.post(
        _assets_url(pid),
        headers=_headers(),
        params={"data_asset_id": asset["id"]},
        json={"resource": asset["resource"]},
        timeout=30,
    )
    if resp.status_code == 409:
        logger.warning("  Asset '%s' already exists — skipping.", asset["id"])
        return
    resp.raise_for_status()
    _wait_for_lro(resp.json()["name"])
    logger.info("  Asset '%s' added.", asset["id"])


def _add_documentation(pid: str, content: str) -> None:
    """Attach rich-text docs via the 'overview' system aspect.

    Ref: https://cloud.google.com/dataplex/docs/create-data-products#add-documentation
    """
    logger.info("  Attaching documentation ...")
    _overview_type = "projects/dataplex-types/locations/global/aspectTypes/overview"
    payload = {
        "aspects": {
            "dataplex-types.global.overview": {
                "aspectType": _overview_type,
                "data": {
                    "content": content,
                    "links": [
                        {
                            "url": (
                                "https://console.cloud.google.com/bigquery"
                                "?p=bigquery-public-data&d=thelook_ecommerce"
                            ),
                            "title": "Source dataset in BigQuery",
                        },
                    ],
                },
            }
        }
    }
    resp = requests.patch(
        _entry_url(pid),
        headers=_headers(),
        params={"updateMask": "aspects"},
        json=payload,
        timeout=30,
    )
    resp.raise_for_status()
    logger.info("  Documentation attached.")


def _add_contract(pid: str, frequency: str) -> None:
    """Attach a refresh-cadence contract via the system aspect.

    Ref: https://cloud.google.com/dataplex/docs/create-data-products#add-a-contract
    """
    logger.info("  Attaching refresh-cadence contract (%s) ...", frequency)
    _cadence_type = (
        "projects/dataplex-types/locations/global/aspectTypes/refresh-cadence"
    )
    payload = {
        "aspects": {
            "dataplex-types.global.refresh-cadence": {
                "aspectType": _cadence_type,
                "data": {
                    "frequency": frequency,
                },
            }
        }
    }
    resp = requests.patch(
        _entry_url(pid),
        headers=_headers(),
        params={"updateMask": "aspects"},
        json=payload,
        timeout=30,
    )
    resp.raise_for_status()
    logger.info("  Contract attached.")


def _add_contacts(pid: str) -> None:
    """Attach a contacts aspect with ownership and stewardship roles.

    Ref: https://cloud.google.com/dataplex/docs/enrich-entries-metadata
    """
    logger.info("  Attaching contacts ...")
    _contacts_type = "projects/dataplex-types/locations/global/aspectTypes/contacts"
    payload = {
        "aspects": {
            "dataplex-types.global.contacts": {
                "aspectType": _contacts_type,
                "data": {
                    "identities": [
                        {
                            "role": "owner",
                            "name": "Data Platform Team",
                            "id": OWNER_EMAIL,
                        },
                        {
                            "role": "steward",
                            "name": "Data Steward",
                            "id": OWNER_EMAIL,
                        },
                    ]
                },
            }
        }
    }
    resp = requests.patch(
        _entry_url(pid),
        headers=_headers(),
        params={"updateMask": "aspects"},
        json=payload,
        timeout=30,
    )
    resp.raise_for_status()
    logger.info("  Contract attached.")


# ---------------------------------------------------------------------------
# DataScan helpers (data profile)
# ---------------------------------------------------------------------------
# DataScan helpers (data profile)
# ---------------------------------------------------------------------------

_SCAN_PREFIX = "thelook-profile"


def _scan_url(scan_id: str | None = None) -> str:
    base = f"{DATAPLEX_BASE}/projects/{PROJECT_ID}/locations/{SCAN_LOCATION}/dataScans"
    return f"{base}/{scan_id}" if scan_id else base


def _create_data_scan(table: str) -> str:
    """Create a DATA_PROFILE DataScan for a view. Returns the scan ID."""
    scan_id = f"{_SCAN_PREFIX}-{table.replace('_', '-')}"
    resource = (
        f"//bigquery.googleapis.com/projects/{PROJECT_ID}"
        f"/datasets/{_VIEWS_DATASET}/tables/{table}"
    )
    logger.info("  Creating DataScan '%s' ...", scan_id)
    payload = {
        "type": "DATA_PROFILE",
        "data": {"resource": resource},
        "dataProfileSpec": {},
    }
    resp = requests.post(
        _scan_url(),
        headers=_headers(),
        params={"data_scan_id": scan_id},
        json=payload,
        timeout=30,
    )
    if resp.status_code == 409:
        logger.warning("  DataScan '%s' already exists — skipping creation.", scan_id)
        return scan_id
    resp.raise_for_status()
    # DataScan create returns an LRO
    _wait_for_lro(resp.json()["name"])
    logger.info("  DataScan '%s' created.", scan_id)
    return scan_id


def _trigger_data_scan(scan_id: str) -> None:
    """Trigger a one-time DataScan run."""
    logger.info("  Triggering scan run for '%s' ...", scan_id)
    resp = requests.post(
        f"{_scan_url(scan_id)}:run",
        headers=_headers(),
        json={},
        timeout=30,
    )
    resp.raise_for_status()
    logger.info("  Scan run triggered.")


def _list_scan_ids() -> list[str]:
    """Return DataScan IDs in SCAN_LOCATION whose name starts with _SCAN_PREFIX."""
    resp = requests.get(_scan_url(), headers=_headers(), timeout=30)
    if resp.status_code == 404:
        return []
    resp.raise_for_status()
    return [
        s["name"].split("/")[-1]
        for s in resp.json().get("dataScans", [])
        if s["name"].split("/")[-1].startswith(_SCAN_PREFIX)
    ]


def _delete_data_scan(scan_id: str) -> None:
    logger.info("  Deleting DataScan '%s' ...", scan_id)
    resp = requests.delete(_scan_url(scan_id), headers=_headers(), timeout=30)
    if resp.status_code == 404:
        logger.warning("  DataScan '%s' not found — skipping.", scan_id)
        return
    resp.raise_for_status()
    _wait_for_lro(resp.json()["name"])
    logger.info("  Deleted.")


# ---------------------------------------------------------------------------
# Dataplex delete helpers
# ---------------------------------------------------------------------------


def _list_asset_ids(pid: str) -> list[str]:
    resp = requests.get(_assets_url(pid), headers=_headers(), timeout=30)
    if resp.status_code == 404:
        return []
    resp.raise_for_status()
    return [a["name"].split("/")[-1] for a in resp.json().get("dataAssets", [])]


def _delete_asset(pid: str, aid: str) -> None:
    logger.info("  Removing asset '%s' ...", aid)
    resp = requests.delete(_asset_url(pid, aid), headers=_headers(), timeout=30)
    if resp.status_code == 404:
        return
    resp.raise_for_status()
    _wait_for_lro(resp.json()["name"])


def _delete_data_product(pid: str) -> None:
    """Delete all assets then the product.

    The API does not support cascading delete — assets must be removed first.
    Ref: https://cloud.google.com/dataplex/docs/reference/rest/v1/projects.locations.dataProducts/delete
    """
    logger.info("Deleting data product '%s' ...", pid)
    for aid in _list_asset_ids(pid):
        _delete_asset(pid, aid)
    resp = requests.delete(_product_url(pid), headers=_headers(), timeout=30)
    if resp.status_code == 404:
        logger.warning("  '%s' not found — skipping.", pid)
        return
    resp.raise_for_status()
    _wait_for_lro(resp.json()["name"])
    logger.info("  Deleted.")


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


def cmd_setup() -> None:
    """Phase 1: create the BigQuery dataset and authorized views."""
    logger.info(
        "Setting up BigQuery views in '%s.%s' ...",
        PROJECT_ID,
        _VIEWS_DATASET,
    )
    _create_bq_dataset()
    for table in _TABLES:
        _create_bq_view(table)
    logger.info("")
    logger.info("Setup complete. Views are ready in BigQuery Studio:")
    logger.info(
        "  https://console.cloud.google.com/bigquery"
        "?project=%s&ws=!1m4!1m3!3m2!1s%s!2s%s",
        PROJECT_ID,
        PROJECT_ID,
        _VIEWS_DATASET,
    )


def cmd_create() -> None:
    """Phase 2: provision all three Dataplex Data Products."""
    logger.info(
        "Creating %d data products in project '%s' (location: %s) ...",
        len(DATA_PRODUCTS),
        PROJECT_ID,
        LOCATION,
    )

    for product in DATA_PRODUCTS:
        logger.info("")
        logger.info("=== %s ===", product["display_name"])
        _create_data_product(product)
        for asset in product["assets"]:
            _add_asset(product["id"], asset)
        _add_documentation(product["id"], product["documentation"])
        _add_contract(product["id"], product["contract_frequency"])

    logger.info("")
    logger.info("All data products created successfully.")
    logger.info(
        "Note: re-running 'create' will skip existing products and assets "
        "but always re-applies aspects (documentation, contract) — this is expected."
    )
    logger.info(
        "Explore in Dataplex Universal Catalog:\n"
        "  https://console.cloud.google.com/dataplex/govern/data-products"
        "?project=%s",
        PROJECT_ID,
    )
    logger.info(
        "Query views in BigQuery Studio:\n"
        "  https://console.cloud.google.com/bigquery?project=%s",
        PROJECT_ID,
    )


def cmd_list() -> None:
    """List all data products in the configured project/location."""
    resp = requests.get(_products_url(), headers=_headers(), timeout=30)
    resp.raise_for_status()
    products = resp.json().get("dataProducts", [])

    if not products:
        logger.info(
            "No data products found in project '%s' (location: %s).",
            PROJECT_ID,
            LOCATION,
        )
        return

    logger.info(
        "Found %d data product(s) in project '%s' (location: %s):",
        len(products),
        PROJECT_ID,
        LOCATION,
    )
    for p in products:
        pid = p.get("name", "").split("/")[-1]
        display = p.get("displayName", "")
        state = p.get("state", "—")
        logger.info("  %-40s  %-12s  %s", display, state, pid)


def cmd_cleanup() -> None:
    """Delete all data products, then the BigQuery dataset and views."""
    logger.info("Starting cleanup ...")

    logger.info("")
    logger.info("-- Phase 1: delete Dataplex Data Products --")
    for product in DATA_PRODUCTS:
        _delete_data_product(product["id"])

    logger.info("")
    logger.info("-- Phase 2: delete BigQuery dataset and views --")
    _delete_bq_dataset()

    logger.info("")
    logger.info("Cleanup complete.")


def cmd_profile() -> None:
    """Create and trigger one DATA_PROFILE DataScan per view (async).

    Scans run in the background — check the Dataplex console for results.
    DataScans are created at SCAN_LOCATION (default: us-central1) rather than
    LOCATION because the DataScan API does not support multi-region endpoints.
    """
    logger.info(
        "Creating %d data profile scans in project '%s' (location: %s) ...",
        len(_TABLES),
        PROJECT_ID,
        SCAN_LOCATION,
    )
    scan_ids: list[str] = []
    for table in _TABLES:
        scan_id = _create_data_scan(table)
        scan_ids.append(scan_id)

    logger.info("")
    logger.info("Triggering scan runs ...")
    for scan_id in scan_ids:
        _trigger_data_scan(scan_id)

    logger.info("")
    logger.info(
        "All scans triggered. Results appear asynchronously — check the console:"
    )
    logger.info(
        "  https://console.cloud.google.com/dataplex/govern/data-scans?project=%s",
        PROJECT_ID,
    )


def cmd_search() -> None:
    """Search the Dataplex catalog for data products (consumer discovery demo)."""
    logger.info(
        "Searching Dataplex catalog for data products in project '%s' ...",
        PROJECT_ID,
    )
    url = f"{DATAPLEX_BASE}/projects/{PROJECT_ID}/locations/global:searchEntries"
    payload = {"query": "(type=(DATA_PRODUCT))", "pageSize": 10}
    resp = requests.post(url, headers=_headers(), json=payload, timeout=30)
    resp.raise_for_status()
    results = resp.json().get("results", [])

    if not results:
        logger.info("No data products found in the catalog.")
        return

    logger.info("Found %d result(s):", len(results))
    for r in results:
        entry = r.get("dataplexEntry", {})
        name = entry.get("name", "")
        pid = name.split("/")[-1]
        display = entry.get("displayName", pid)
        description = entry.get("description", "")
        logger.info("  %-40s  %s", display, pid)
        if description:
            logger.info("    %s", description[:100])


def cmd_cleanup_scans() -> None:
    """Delete all thelook-profile-* DataScans."""
    logger.info(
        "Cleaning up DataScans in project '%s' (location: %s) ...",
        PROJECT_ID,
        SCAN_LOCATION,
    )
    scan_ids = _list_scan_ids()
    if not scan_ids:
        logger.info("  No matching DataScans found.")
        return
    for scan_id in scan_ids:
        _delete_data_scan(scan_id)
    logger.info("Scan cleanup complete.")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Dataplex Data Product demo — TheLook E-Commerce",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    sub = parser.add_subparsers(dest="commands", metavar="COMMAND")
    sub.add_parser("setup", help="Create BQ dataset + authorized views")
    sub.add_parser("create", help="Provision all three data products")
    sub.add_parser("profile", help="Create + trigger 7 data profile scans (async)")
    sub.add_parser("search", help="Search catalog for data products")
    sub.add_parser("list", help="List data products in project/location")
    sub.add_parser("cleanup", help="Delete data products and BQ views")
    sub.add_parser("cleanup-scans", help="Delete all thelook-profile-* DataScans")

    # Support one or more commands: e.g. `setup create`
    args, remaining = parser.parse_known_args()

    command_map = {
        "setup": cmd_setup,
        "create": cmd_create,
        "profile": cmd_profile,
        "search": cmd_search,
        "list": cmd_list,
        "cleanup": cmd_cleanup,
        "cleanup-scans": cmd_cleanup_scans,
    }

    all_commands: list[str] = []
    if args.commands:
        all_commands.append(args.commands)
    all_commands.extend(remaining)

    if not all_commands:
        parser.print_help()
        sys.exit(1)

    unknown = [c for c in all_commands if c not in command_map]
    if unknown:
        parser.error(f"Unknown command(s): {', '.join(unknown)}")

    for cmd in all_commands:
        command_map[cmd]()


if __name__ == "__main__":
    main()
