#!/usr/bin/env python3
"""Idempotent Provisioner for Google Cloud Dataplex OOTB Data Contract Governance.

Provisions and verifies the complete out-of-the-box Dataplex Knowledge Catalog
experience from declarative YAML configurations:
  1. BigQuery Curated Contract View (`equity_trades_curated`) with column-level
     provenance descriptions (`[Inherited: Upstream Source Dictionary]` vs.
     `[Platform-Derived: Steward Authored (AI-Assisted Pattern)]`).
  2. Dataplex Business Glossary (`exchange-source-dictionary`), 3 Categories,
     and 8 canonical Upstream Source Dictionary Terms.
  3. 16 Column-Level `EntryLinks` (`definition` type) binding `Schema.<col>` on
     both `equity_trades` and `equity_trades_curated` to the Business Glossary.
  4. Native Dataplex Data Product (`equity-market-trades`) with Access Groups,
     packaged DataAssets (`equity-trades-curated`, `equity-trades-raw`), and
     Catalog Entry Aspects (`refresh-cadence` + `data-contract-spec`).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.dataplex_rest import (
    DATAPLEX_BASE_URL,
    DataplexClient,
    UrllibTransport,
)

ENTRY_LINK_ID_REGEX = re.compile(r"^[a-z][a-z0-9-]{0,61}[a-z0-9]$")
DEFINITION_LINK_TYPE = (
    "projects/dataplex-types/locations/global/entryLinkTypes/definition"
)


@dataclass(frozen=True)
class PlannedRequest:
    """Represents a single deterministic REST operation in the provisioning plan."""

    step: str
    category: str
    method: str
    create_url: str
    resource_url: str
    body: Dict[str, Any] = field(default_factory=dict)
    update_mask: Optional[str] = None
    is_lro: bool = False


def load_yaml_file(path: Path) -> Dict[str, Any]:
    """Loads a YAML file safely."""
    with open(path, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def load_catalog_configs(
    repo_root: Path = REPO_ROOT,
) -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
    """Loads contract.odcs.yaml, business_glossary.yaml, data_product.yaml, and table_aspect_payload.yaml."""
    contract = load_yaml_file(repo_root / "contract.odcs.yaml")
    glossary_cfg = load_yaml_file(repo_root / "config" / "business_glossary.yaml")
    product_cfg = load_yaml_file(repo_root / "config" / "data_product.yaml")
    aspect_payload = load_yaml_file(repo_root / "config" / "table_aspect_payload.yaml")
    return contract, glossary_cfg, product_cfg, aspect_payload


def extract_target_coordinates(contract: Dict[str, Any]) -> Tuple[str, str, str]:
    """Extracts (dataset_id, table_id, location) from contract.odcs.yaml."""
    server = contract.get("servers", {}).get("production_bigquery", {})
    dataset_id = str(server.get("dataset", "sgx_market_data"))
    table_id = str(server.get("table", "equity_trades"))
    location = str(server.get("location", "asia-southeast1"))
    return dataset_id, table_id, location


def make_entry_link_id(table_variant: str, term_id: str) -> str:
    """Builds a compliant Dataplex entryLinkId matching ^[a-z][a-z0-9-]{0,61}[a-z0-9]$."""
    slug = f"def-{table_variant}-{term_id}".lower().replace("_", "-")
    slug = re.sub(r"[^a-z0-9-]", "-", slug)
    slug = re.sub(r"-+", "-", slug).strip("-")
    if len(slug) > 63:
        slug = slug[:63].rstrip("-")
    if not ENTRY_LINK_ID_REGEX.match(slug):
        raise ValueError(f"Generated invalid entryLinkId: {slug}")
    return slug


def extract_schema_properties(contract: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extracts the list of business column property definitions from contract.odcs.yaml."""
    schema_obj = contract.get("schema", [])
    if isinstance(schema_obj, list) and schema_obj:
        return list(schema_obj[0].get("properties", []))
    if isinstance(schema_obj, dict):
        return list(schema_obj.get("properties", []))
    return []


def render_curated_view_sql(
    contract: Dict[str, Any],
    glossary_cfg: Dict[str, Any],
) -> str:
    """Renders deterministic BigQuery DDL for the curated contract view."""
    dataset_id, table_id, _ = extract_target_coordinates(contract)
    curated_view_id = f"{table_id}_curated"

    terms_by_col = {
        str(t["column_name"]): t for t in glossary_cfg.get("terms", [])
    }
    derived_cols = glossary_cfg.get("derived_columns", [])

    col_defs: List[str] = []
    select_exprs: List[str] = []

    for prop in extract_schema_properties(contract):
        col_name = str(prop["name"])
        term = terms_by_col.get(col_name, {})
        badge = term.get(
            "provenance_badge", "[Inherited: Upstream Source Dictionary]"
        )
        spec_ref = term.get("source_spec_ref", "Upstream Source Dictionary")
        desc = str(term.get("description") or prop.get("description") or "").strip()
        full_desc = f"{badge} ({spec_ref}) {desc}".replace('"', '\\"')
        col_defs.append(f'    {col_name} OPTIONS(description="{full_desc}")')
        select_exprs.append(f"    {col_name}")

    for dcol in derived_cols:
        d_name = str(dcol["column_name"])
        badge = dcol.get(
            "provenance_badge",
            "[Platform-Derived: Steward Authored (AI-Assisted Pattern)]",
        )
        spec_ref = dcol.get("source_spec_ref", "Platform Derived")
        desc = str(dcol.get("description", "")).strip()
        full_desc = f"{badge} ({spec_ref}) {desc}".replace('"', '\\"')
        col_defs.append(f'    {d_name} OPTIONS(description="{full_desc}")')
        sql_expr = str(dcol["sql_expression"])
        select_exprs.append(f"    {sql_expr} AS {d_name}")

    cols_block = ",\n".join(col_defs)
    select_block = ",\n".join(select_exprs)

    sql_lines = [
        "-- =============================================================================",
        "-- Curated Analytical Data Contract View (Grade A Certified)",
        "-- Generated from contract.odcs.yaml + config/business_glossary.yaml",
        "-- Do not edit manually; run: python3 scripts/provision_catalog.py render-sql",
        "-- =============================================================================",
        f"CREATE OR REPLACE VIEW `${{PROJECT_ID}}.{dataset_id}.{curated_view_id}` (",
        cols_block,
        ")",
        "OPTIONS(",
        '    description="Contract-certified Grade-A analytical view enforcing all 9 ODCS data quality rules (including the rolling 2-hour freshness SLA and anti-wash-trading integrity check) plus 2 platform-derived columns (notional_value, wash_trade_flag). Recommended primary asset for business consumers.",',
        '    labels=[("domain", "equities_market"), ("contract_version", "1_0_0"), ("quality_grade", "grade_a"), ("governance_layer", "curated_contract_view")]',
        ")",
        "AS",
        "SELECT",
        select_block,
        f"FROM `${{PROJECT_ID}}.{dataset_id}.{table_id}`",
        "WHERE",
        "    trade_id IS NOT NULL",
        "    AND instrument_code IS NOT NULL",
        "    AND price IS NOT NULL",
        "    AND price > 0",
        "    AND volume IS NOT NULL",
        "    AND volume > 0",
        "    AND buyer_id IS NOT NULL",
        "    AND seller_id IS NOT NULL",
        "    AND buyer_id != seller_id",
        "    AND trade_status IN ('EXECUTED', 'CANCELLED', 'AMENDED')",
        "    AND trade_timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 2 HOUR);",
        "",
    ]
    return "\n".join(sql_lines)


def parse_access_group_principals(raw_pairs: Optional[List[str]]) -> Dict[str, str]:
    """Parses repeatable --access-group-principal group_id=email flags."""
    overrides: Dict[str, str] = {}
    for item in raw_pairs or []:
        if "=" not in item:
            raise ValueError(
                f"Invalid --access-group-principal '{item}'; expected group_id=email"
            )
        k, v = item.split("=", 1)
        overrides[k.strip()] = v.strip()
    return overrides


def build_provisioning_plan(
    project_id: str,
    project_number: str,
    location: str,
    dataset_id: str,
    table_id: str,
    glossary_cfg: Dict[str, Any],
    product_cfg: Dict[str, Any],
    aspect_payload: Dict[str, Any],
    owner_email: str = "platform-steward@example.com",
    access_group_principals: Optional[Dict[str, str]] = None,
    bind_asset_iam: bool = False,
    include_data_product: bool = True,
) -> List[PlannedRequest]:
    """Builds the ordered list of REST requests to converge Dataplex Catalog state."""
    plan: List[PlannedRequest] = []
    principal_overrides = access_group_principals or {}

    g_info = glossary_cfg["glossary"]
    glossary_id = str(g_info["id"])
    parent_loc = f"projects/{project_id}/locations/{location}"
    glossary_name = f"{parent_loc}/glossaries/{glossary_id}"

    # 1. Business Glossary (LRO)
    plan.append(
        PlannedRequest(
            step="1.glossary",
            category="glossary",
            method="POST",
            create_url=f"{DATAPLEX_BASE_URL}/{parent_loc}/glossaries?glossaryId={glossary_id}",
            resource_url=f"{DATAPLEX_BASE_URL}/{glossary_name}",
            body={
                "displayName": g_info["display_name"],
                "description": g_info["description"],
                "labels": g_info.get("labels", {}),
            },
            update_mask="displayName,description,labels",
            is_lro=True,
        )
    )

    # 2. Glossary Categories
    for cat in glossary_cfg.get("categories", []):
        cat_id = str(cat["id"])
        cat_name = f"{glossary_name}/categories/{cat_id}"
        plan.append(
            PlannedRequest(
                step=f"2.category.{cat_id}",
                category="category",
                method="POST",
                create_url=f"{DATAPLEX_BASE_URL}/{glossary_name}/categories?categoryId={cat_id}",
                resource_url=f"{DATAPLEX_BASE_URL}/{cat_name}",
                body={
                    "parent": glossary_name,
                    "displayName": cat["display_name"],
                    "description": cat["description"],
                },
                update_mask="displayName,description",
                is_lro=False,
            )
        )

    # 3. Glossary Terms (8 canonical upstream source dictionary fields)
    for term in glossary_cfg.get("terms", []):
        term_id = str(term["id"])
        cat_id = str(term["category_id"])
        cat_parent = f"{glossary_name}/categories/{cat_id}"
        term_name = f"{glossary_name}/terms/{term_id}"
        full_desc = (
            f"{term.get('provenance_badge', '')} "
            f"({term.get('source_spec_ref', '')}) — {term['description']}"
        ).strip()
        plan.append(
            PlannedRequest(
                step=f"3.term.{term_id}",
                category="term",
                method="POST",
                create_url=f"{DATAPLEX_BASE_URL}/{glossary_name}/terms?termId={term_id}",
                resource_url=f"{DATAPLEX_BASE_URL}/{term_name}",
                body={
                    "parent": cat_parent,
                    "displayName": term["display_name"],
                    "description": full_desc,
                },
                update_mask="displayName,description",
                is_lro=False,
            )
        )

    # 4. Column-Level EntryLinks (8 on raw table + 8 on curated view = 16 links)
    bq_entry_group = (
        f"projects/{project_number}/locations/{location}/entryGroups/@bigquery"
    )
    table_variants = [
        ("raw", table_id),
        ("curated", f"{table_id}_curated"),
    ]
    for variant_label, target_table_name in table_variants:
        bq_entry_name = (
            f"{bq_entry_group}/entries/bigquery.googleapis.com/"
            f"projects/{project_id}/datasets/{dataset_id}/tables/{target_table_name}"
        )
        for term in glossary_cfg.get("terms", []):
            term_id = str(term["id"])
            col_name = str(term["column_name"])
            link_id = make_entry_link_id(variant_label, term_id)
            term_entry_name = (
                f"projects/{project_number}/locations/{location}/entryGroups/@dataplex/"
                f"entries/projects/{project_number}/locations/{location}/"
                f"glossaries/{glossary_id}/terms/{term_id}"
            )
            link_url = f"{DATAPLEX_BASE_URL}/{bq_entry_group}/entryLinks/{link_id}"
            create_link_url = (
                f"{DATAPLEX_BASE_URL}/{bq_entry_group}/entryLinks?entryLinkId={link_id}"
            )
            plan.append(
                PlannedRequest(
                    step=f"4.entry_link.{link_id}",
                    category="entry_link",
                    method="POST",
                    create_url=create_link_url,
                    resource_url=link_url,
                    body={
                        "entryLinkType": DEFINITION_LINK_TYPE,
                        "entryReferences": [
                            {
                                "name": bq_entry_name,
                                "path": f"Schema.{col_name}",
                                "type": "SOURCE",
                            },
                            {
                                "name": term_entry_name,
                                "type": "TARGET",
                            },
                        ],
                    },
                    update_mask=None,
                    is_lro=False,
                )
            )

    # 5. Attach data-contract-spec aspect to Curated View entry in @bigquery
    aspect_key = f"{project_number}.{location}.data-contract-spec"
    aspect_type_res = (
        f"projects/{project_number}/locations/{location}/aspectTypes/data-contract-spec"
    )
    curated_entry_url = (
        f"{DATAPLEX_BASE_URL}/projects/{project_id}/locations/{location}/"
        f"entryGroups/@bigquery/entries/bigquery.googleapis.com/"
        f"projects/{project_id}/datasets/{dataset_id}/tables/{table_id}_curated"
    )
    raw_aspect_data = (
        aspect_payload.get(
            f"{project_id}.{location}.data-contract-spec",
            next(iter(aspect_payload.values()), {}),
        ).get("data", {})
        if isinstance(aspect_payload, dict)
        else {}
    )
    plan.append(
        PlannedRequest(
            step="5.curated_view_aspect",
            category="entry_aspect",
            method="PATCH",
            create_url=f"{curated_entry_url}?updateMask=aspects",
            resource_url=curated_entry_url,
            body={
                "aspects": {
                    aspect_key: {
                        "aspectType": aspect_type_res,
                        "data": dict(raw_aspect_data),
                    }
                }
            },
            update_mask="aspects",
            is_lro=False,
        )
    )

    if not include_data_product:
        return plan

    # 6. Dataplex Data Product (LRO)
    dp_info = product_cfg["data_product"]
    dp_id = str(dp_info["id"])
    dp_name = f"{parent_loc}/dataProducts/{dp_id}"

    access_groups_map: Dict[str, Any] = {}
    for ag_key, ag_val in product_cfg.get("access_groups", {}).items():
        default_group = str(
            ag_val.get("default_principal_group", f"{ag_val['id']}@example.com")
        )
        principal_email = principal_overrides.get(ag_key, default_group)
        access_groups_map[ag_key] = {
            "id": ag_val["id"],
            "displayName": ag_val["display_name"],
            "description": ag_val.get("description", ""),
            "principal": {"googleGroup": principal_email},
        }

    plan.append(
        PlannedRequest(
            step=f"6.data_product.{dp_id}",
            category="data_product",
            method="POST",
            create_url=f"{DATAPLEX_BASE_URL}/{parent_loc}/dataProducts?dataProductId={dp_id}",
            resource_url=f"{DATAPLEX_BASE_URL}/{dp_name}",
            body={
                "displayName": dp_info["display_name"],
                "description": dp_info["description"],
                "labels": dp_info.get("labels", {}),
                "ownerEmails": [owner_email],
                "accessGroups": access_groups_map,
            },
            update_mask="displayName,description,labels,ownerEmails,accessGroups",
            is_lro=True,
        )
    )

    # 7. Data Product Packaged DataAssets (LRO)
    for asset in product_cfg.get("assets", []):
        asset_id = str(asset["id"])
        suffix = str(asset.get("table_suffix", ""))
        target_tbl = f"{table_id}{suffix}"
        asset_name = f"{dp_name}/dataAssets/{asset_id}"
        bq_resource = (
            f"//bigquery.googleapis.com/projects/{project_id}/"
            f"datasets/{dataset_id}/tables/{target_tbl}"
        )
        asset_body: Dict[str, Any] = {
            "resource": bq_resource,
            "labels": {
                "layer": str(asset.get("layer", "curated")),
                "target_grade": str(asset.get("target_grade", "A")).lower(),
            },
        }
        asset_mask = "labels"
        if bind_asset_iam and asset.get("access_group_roles"):
            ag_configs: Dict[str, Any] = {}
            for grp_id, roles in asset.get("access_group_roles", {}).items():
                ag_configs[str(grp_id)] = {"iamRoles": list(roles)}
            asset_body["accessGroupConfigs"] = ag_configs
            asset_mask = "labels,accessGroupConfigs"

        plan.append(
            PlannedRequest(
                step=f"7.data_asset.{asset_id}",
                category="data_asset",
                method="POST",
                create_url=f"{DATAPLEX_BASE_URL}/{dp_name}/dataAssets?dataAssetId={asset_id}",
                resource_url=f"{DATAPLEX_BASE_URL}/{asset_name}",
                body=asset_body,
                update_mask=asset_mask,
                is_lro=True,
            )
        )

    # 8. Data Product Catalog Entry Aspects (refresh-cadence + data-contract-spec)
    dp_entry_url = (
        f"{DATAPLEX_BASE_URL}/projects/{project_id}/locations/{location}/"
        f"entryGroups/@dataplex/entries/projects/{project_number}/"
        f"locations/{location}/dataProducts/{dp_id}"
    )
    rc_cfg = product_cfg.get("refresh_cadence_aspect", {})
    rc_key = str(rc_cfg.get("aspect_key", "dataplex-types.global.refresh-cadence"))
    rc_type = str(
        rc_cfg.get(
            "aspect_type",
            "projects/dataplex-types/locations/global/aspectTypes/refresh-cadence",
        )
    )
    rc_data = rc_cfg.get(
        "data",
        {
            "frequency": "Daily",
            "refreshTime": "09:00 SGT",
            "thresholdInMinutes": 120,
            "cronSchedule": "0 */2 * * *",
        },
    )
    plan.append(
        PlannedRequest(
            step="8.data_product_entry_aspects",
            category="entry_aspect",
            method="PATCH",
            create_url=f"{dp_entry_url}?updateMask=aspects",
            resource_url=dp_entry_url,
            body={
                "aspects": {
                    rc_key: {
                        "aspectType": rc_type,
                        "data": dict(rc_data),
                    },
                    aspect_key: {
                        "aspectType": aspect_type_res,
                        "data": dict(raw_aspect_data),
                    },
                }
            },
            update_mask="aspects",
            is_lro=False,
        )
    )

    return plan


def deploy_curated_view_bigquery(
    project_id: str, sql_path: Path, dry_run: bool = False
) -> None:
    """Executes sql/create_curated_view.sql in BigQuery with ${PROJECT_ID} substituted."""
    raw_sql = sql_path.read_text(encoding="utf-8")
    rendered_sql = raw_sql.replace("${PROJECT_ID}", project_id)
    if dry_run:
        print(f"  [DRY-RUN] Would execute BigQuery DDL from {sql_path.name}")
        return
    print(f"  >> Creating/Updating BigQuery Curated View via {sql_path.name}...")
    res = subprocess.run(
        [
            "bq",
            "query",
            f"--project_id={project_id}",
            "--use_legacy_sql=false",
        ],
        input=rendered_sql,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    if res.returncode != 0:
        raise RuntimeError(
            f"BigQuery curated view DDL failed (exit {res.returncode}): {res.stderr or res.stdout}"
        )
    print("     ✓ BigQuery Curated View (`equity_trades_curated`) deployed.")


def wait_for_bigquery_entry(
    client: DataplexClient,
    project_id: str,
    location: str,
    dataset_id: str,
    table_name: str,
    max_attempts: int = 12,
) -> bool:
    """Polls Dataplex Catalog until the @bigquery entry for table_name is indexed."""
    entry_url = (
        f"{DATAPLEX_BASE_URL}/projects/{project_id}/locations/{location}/"
        f"entryGroups/@bigquery/entries/bigquery.googleapis.com/"
        f"projects/{project_id}/datasets/{dataset_id}/tables/{table_name}"
    )
    for attempt in range(1, max_attempts + 1):
        found = client.get_or_none(entry_url)
        if found is not None:
            return True
        print(
            f"     [Wait {attempt}/{max_attempts}] Waiting for Dataplex Catalog to index {table_name}..."
        )
        client.sleep_fn(3.0)
    return False


def _normalize_dataplex_uri(
    uri: str, project_id: str = "", own_project_prefix: str = ""
) -> str:
    """Normalizes known Dataplex projectNumber prefixes to project_id / dataplex-types without stripping foreign projects."""
    raw = str(uri or "").strip()
    if raw.startswith("projects/655216118709/locations/"):
        raw = "projects/dataplex-types/locations/" + raw.split("/locations/", 1)[1]
    if (
        project_id
        and own_project_prefix
        and own_project_prefix.startswith("projects/")
        and raw.startswith(own_project_prefix + "/locations/")
    ):
        raw = f"projects/{project_id}/locations/" + raw.split("/locations/", 1)[1]
    return raw


def _entry_link_matches(
    existing: Dict[str, Any], desired: Dict[str, Any], project_id: str = ""
) -> bool:
    """Checks whether an existing EntryLink matches the desired type and references."""
    own_prefix = ""
    ex_name = str(existing.get("name", ""))
    if ex_name.startswith("projects/") and "/locations/" in ex_name:
        own_prefix = ex_name.split("/locations/", 1)[0]

    if _normalize_dataplex_uri(
        existing.get("entryLinkType", ""), project_id, own_prefix
    ) != _normalize_dataplex_uri(
        desired.get("entryLinkType", ""), project_id, own_prefix
    ):
        return False
    ex_refs = existing.get("entryReferences", [])
    des_refs = desired.get("entryReferences", [])
    if len(ex_refs) != len(des_refs):
        return False
    for e_ref, d_ref in zip(ex_refs, des_refs):
        if (
            _normalize_dataplex_uri(e_ref.get("name", ""), project_id, own_prefix)
            != _normalize_dataplex_uri(d_ref.get("name", ""), project_id, own_prefix)
            or e_ref.get("path", "") != d_ref.get("path", "")
            or e_ref.get("type") != d_ref.get("type")
        ):
            return False
    return True


def execute_apply(
    client: DataplexClient,
    plan: List[PlannedRequest],
    project_id: str,
    location: str,
    dataset_id: str,
    table_id: str,
) -> Dict[str, int]:
    """Executes the provisioning plan idempotently against Dataplex REST APIs."""
    counts: Dict[str, int] = {"created_or_updated": 0, "skipped_or_existing": 0}

    # Ensure both raw table and curated view entries are indexed before creating EntryLinks
    for tbl_name in (table_id, f"{table_id}_curated"):
        if not wait_for_bigquery_entry(
            client, project_id, location, dataset_id, tbl_name
        ):
            raise RuntimeError(
                f"Dataplex Catalog entry for BigQuery table '{dataset_id}.{tbl_name}' was not indexed within timeout."
            )

    for item in plan:
        print(f"  >> [{item.step}] Converging {item.category}...")
        if item.category == "entry_link":
            existing = client.get_or_none(item.resource_url)
            if existing is not None:
                if _entry_link_matches(existing, item.body, project_id=project_id):
                    counts["skipped_or_existing"] += 1
                    print(f"     ✓ EntryLink already in sync ({item.step}).")
                    continue
                print(
                    f"     [DRIFT] Recreating drifted EntryLink ({item.step})..."
                )
                client.delete_if_exists(item.resource_url, is_lro=False)

            resp = client.request_with_retry(
                "POST",
                item.create_url,
                body=item.body,
                allow_statuses=(200, 201, 409),
            )
            if resp.status_code == 409:
                counts["skipped_or_existing"] += 1
            else:
                counts["created_or_updated"] += 1
            print(f"     ✓ EntryLink bound ({item.step}).")
        elif item.category == "entry_aspect":
            client.request_with_retry(
                "PATCH",
                item.create_url,
                body=item.body,
                allow_statuses=(200, 201),
            )
            counts["created_or_updated"] += 1
            print(f"     ✓ Catalog Entry Aspects attached ({item.step}).")
        else:
            client.create_or_update(
                create_url=item.create_url,
                resource_url=item.resource_url,
                body=item.body,
                update_mask=item.update_mask,
                is_lro=item.is_lro,
            )
            counts["created_or_updated"] += 1
            print(f"     ✓ Converged {item.category} ({item.step}).")

    return counts


def execute_teardown(
    client: DataplexClient, plan: List[PlannedRequest]
) -> Dict[str, int]:
    """Deletes catalog resources in strict reverse dependency order."""
    deleted = 0
    for item in reversed(plan):
        if item.category == "entry_aspect":
            if item.step == "5.curated_view_aspect":
                # Detach aspect from the curated view entry if the view still exists
                aspect_keys = list(item.body.get("aspects", {}).keys())
                if aspect_keys and client.get_or_none(item.resource_url) is not None:
                    empty_aspects = {k: None for k in aspect_keys}
                    client.request_with_retry(
                        "PATCH",
                        f"{item.resource_url}?updateMask=aspects&deleteMissingAspects=true",
                        body={"aspects": empty_aspects},
                        allow_statuses=(200, 201, 400, 404),
                    )
            continue

        print(f"  >> [Teardown {item.step}] Deleting {item.category}...")
        if client.delete_if_exists(item.resource_url, is_lro=item.is_lro):
            deleted += 1
            print(f"     ✓ Deleted {item.step}")
        else:
            print(f"     - Already absent ({item.step})")
    return {"deleted": deleted}


def resolve_default_owner_email() -> str:
    """Resolves active gcloud account email or returns a safe placeholder."""
    try:
        res = subprocess.run(
            ["gcloud", "config", "get-value", "account"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        acct = res.stdout.strip()
        if acct and "@" in acct:
            return acct
    except Exception:
        pass
    return "platform-steward@example.com"


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Provision & verify OOTB Dataplex Business Glossary, EntryLinks, and Data Product."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # render-sql
    p_sql = sub.add_parser(
        "render-sql", help="Render or drift-check sql/create_curated_view.sql"
    )
    p_sql.add_argument(
        "--check",
        action="store_true",
        help="Exit non-zero if sql/create_curated_view.sql is out of sync",
    )

    # apply
    p_apply = sub.add_parser(
        "apply", help="Provision Curated View, Glossary, EntryLinks, and Data Product"
    )
    p_apply.add_argument(
        "--project-id",
        default=os.environ.get("PROJECT_ID", ""),
        help="Google Cloud Project ID",
    )
    p_apply.add_argument(
        "--project-number",
        default="",
        help="Google Cloud Project Number (resolved automatically in live mode)",
    )
    p_apply.add_argument("--location", default="", help="Override GCP location")
    p_apply.add_argument(
        "--owner-email",
        default="",
        help="Data Product owner email (defaults to active gcloud account)",
    )
    p_apply.add_argument(
        "--access-group-principal",
        action="append",
        default=[],
        help="Override access group principal email (format: group_id=group@domain)",
    )
    p_apply.add_argument(
        "--bind-asset-iam",
        action="store_true",
        help="Attach accessGroupConfigs IAM role bindings to DataAssets (requires valid Cloud Identity groups)",
    )
    p_apply.add_argument(
        "--skip-data-product",
        action="store_true",
        help="Skip DataProduct and DataAsset provisioning",
    )
    p_apply.add_argument(
        "--skip-bigquery-view",
        action="store_true",
        help="Skip executing sql/create_curated_view.sql in BigQuery",
    )
    p_apply.add_argument(
        "--dry-run",
        action="store_true",
        help="Print deterministic REST plan without making network calls",
    )
    p_apply.add_argument("--verbose", action="store_true", help="Verbose HTTP logging")

    # teardown
    p_td = sub.add_parser(
        "teardown", help="Delete EntryLinks, Data Product, and Business Glossary"
    )
    p_td.add_argument(
        "--project-id",
        default=os.environ.get("PROJECT_ID", ""),
        help="Google Cloud Project ID",
    )
    p_td.add_argument("--project-number", default="", help="Project Number")
    p_td.add_argument("--location", default="", help="Override GCP location")
    p_td.add_argument(
        "--dry-run",
        action="store_true",
        help="Print teardown plan without network calls",
    )
    p_td.add_argument("--verbose", action="store_true", help="Verbose HTTP logging")

    args = parser.parse_args(argv)
    contract, glossary_cfg, product_cfg, aspect_payload = load_catalog_configs(
        REPO_ROOT
    )
    dataset_id, table_id, default_loc = extract_target_coordinates(contract)

    if args.command == "render-sql":
        rendered = render_curated_view_sql(contract, glossary_cfg)
        sql_path = REPO_ROOT / "sql" / "create_curated_view.sql"
        if args.check:
            if not sql_path.exists():
                print(f"[DRIFT] Missing {sql_path}", file=sys.stderr)
                return 1
            current = sql_path.read_text(encoding="utf-8")
            if current != rendered:
                print(
                    f"[DRIFT] {sql_path.name} is out of sync with contract/glossary configs.",
                    file=sys.stderr,
                )
                return 1
            print(f"[OK] {sql_path.name} is in sync.")
            return 0
        sql_path.write_text(rendered, encoding="utf-8")
        print(f"[OK] Wrote {sql_path}")
        return 0

    location = getattr(args, "location", "") or default_loc
    project_id = getattr(args, "project_id", "") or "placeholder-project-id"
    dry_run = bool(getattr(args, "dry_run", False))
    ag_principals = parse_access_group_principals(
        getattr(args, "access_group_principal", [])
    )
    bind_iam = bool(getattr(args, "bind_asset_iam", False))

    if dry_run:
        pnum = getattr(args, "project_number", "") or "000000000000"
        owner = getattr(args, "owner_email", "") or "platform-steward@example.com"
        plan = build_provisioning_plan(
            project_id=project_id,
            project_number=pnum,
            location=location,
            dataset_id=dataset_id,
            table_id=table_id,
            glossary_cfg=glossary_cfg,
            product_cfg=product_cfg,
            aspect_payload=aspect_payload,
            owner_email=owner,
            access_group_principals=ag_principals,
            bind_asset_iam=bind_iam,
            include_data_product=not getattr(args, "skip_data_product", False),
        )
        print(
            f"[DRY-RUN] Generated {len(plan)} deterministic REST operations for project='{project_id}' ({location}):"
        )
        for idx, item in enumerate(plan, 1):
            print(
                f"  {idx:02d}. [{item.step}] {item.method} {item.create_url} (LRO={item.is_lro})"
            )
        return 0

    if not project_id or project_id == "placeholder-project-id":
        print("[ERROR] --project-id is required for live execution.", file=sys.stderr)
        return 1

    transport = UrllibTransport(quota_project=project_id)
    client = DataplexClient(transport=transport, verbose=bool(args.verbose))
    pnum = getattr(args, "project_number", "") or client.resolve_project_number(
        project_id
    )
    owner = getattr(args, "owner_email", "") or resolve_default_owner_email()

    plan = build_provisioning_plan(
        project_id=project_id,
        project_number=pnum,
        location=location,
        dataset_id=dataset_id,
        table_id=table_id,
        glossary_cfg=glossary_cfg,
        product_cfg=product_cfg,
        aspect_payload=aspect_payload,
        owner_email=owner,
        access_group_principals=ag_principals,
        bind_asset_iam=bind_iam,
        include_data_product=not getattr(args, "skip_data_product", False),
    )

    if args.command == "apply":
        sql_path = REPO_ROOT / "sql" / "create_curated_view.sql"
        if not sql_path.exists():
            sql_path.write_text(
                render_curated_view_sql(contract, glossary_cfg), encoding="utf-8"
            )
        if not getattr(args, "skip_bigquery_view", False):
            deploy_curated_view_bigquery(project_id, sql_path, dry_run=False)

        counts = execute_apply(
            client=client,
            plan=plan,
            project_id=project_id,
            location=location,
            dataset_id=dataset_id,
            table_id=table_id,
        )
        print(
            f"[SUCCESS] Dataplex OOTB Catalog Provisioning Complete: {json.dumps(counts)}"
        )
        return 0

    if args.command == "teardown":
        counts = execute_teardown(client=client, plan=plan)
        print(f"[SUCCESS] Dataplex OOTB Catalog Teardown Complete: {json.dumps(counts)}")
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
