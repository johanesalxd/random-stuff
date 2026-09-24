#!/usr/bin/env python3
"""Business Data Contract & 5-Tier Quality Grade (A-E) Portal Generator and Server.

Bridges Google Cloud Dataplex Knowledge Catalog (Business Glossary, Column
EntryLinks, Data Products, and Data Quality Scorecards) into a single-pane
executive web experience tailored for Data Producers, Platform Stewards, and
Business Consumers:
  1. 3-Layer Internal Handshake Banner (Source Producer <-> Platform Steward <-> Consumers)
     with interactive Consumer Access Handshake modal (DataAsset.accessGroupConfigs).
  2. 5-Tier Quality & SLA Grade Badge (A / B / C / D / E — Nutri-Score / Extended
     Nutri-Grade style) with instant toggle between Curated Contract View
     (Grade A - 100.0%, 9/9 rules) and Raw Landing Table (Grade E - 55.56%, 5/9 rules).
  3. Interactive Column Dictionary & Provenance Filter contrasting 100%
     Deterministic Source Dictionary Inheritance (8 columns) against
     Platform-Derived Steward Authored Columns (2 columns).
  4. Single-Pane Contract Guarantees (refresh-cadence + data-contract-spec) &
     Quarantine (DLQ / Wash-Trade) Forensic Payload Inspector.
"""

from __future__ import annotations

import argparse
import html
import json
import os
import subprocess
import sys
import urllib.parse
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.dataplex_rest import DATAPLEX_BASE_URL, DataplexClient, UrllibTransport
from scripts.provision_catalog import (
    extract_schema_properties,
    extract_target_coordinates,
    load_catalog_configs,
    load_yaml_file,
)
from scripts.run_dataplex_scan import OfflineSimulationEngine, RuleEvaluationResult


def compute_nutri_grade(
    overall_pass_pct: float,
    critical_failures: int,
    thresholds: Dict[str, Any],
) -> Dict[str, Any]:
    """Determines the A-E quality grade from rule pass percentage and critical failures."""
    ordered_grades = ["A", "B", "C", "D", "E"]
    selected = "E"
    for grade in ordered_grades:
        spec = thresholds.get(grade, {})
        min_score = float(spec.get("min_score", 0.0))
        max_crit = int(spec.get("max_critical_failures", 99))
        if overall_pass_pct >= min_score and critical_failures <= max_crit:
            selected = grade
            break

    spec = thresholds.get(selected, {})
    return {
        "grade": selected,
        "score_pct": round(overall_pass_pct, 2),
        "critical_failures": critical_failures,
        "color_hex": str(spec.get("color_hex", "#D92B2B")),
        "label": str(spec.get("label", "Non-Compliant")),
    }


def filter_curated_records(
    records: List[Dict[str, Any]],
    reference_now: Optional[datetime] = None,
) -> List[Dict[str, Any]]:
    """Applies the exact 9-predicate WHERE clause of sql/create_curated_view.sql to a record batch."""
    now = reference_now or datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=2)
    permitted_statuses = {"EXECUTED", "CANCELLED", "AMENDED"}
    curated: List[Dict[str, Any]] = []

    for r in records:
        trade_id = r.get("trade_id")
        inst = r.get("instrument_code")
        price = r.get("price")
        vol = r.get("volume")
        buyer = r.get("buyer_id")
        seller = r.get("seller_id")
        status = r.get("trade_status")
        ts_str = r.get("trade_timestamp")

        if trade_id is None or inst is None or price is None or vol is None:
            continue
        if float(price) <= 0.0 or int(vol) <= 0:
            continue
        if buyer is None or seller is None or str(buyer) == str(seller):
            continue
        if str(status) not in permitted_statuses:
            continue
        if ts_str is None:
            continue
        try:
            ts = datetime.fromisoformat(str(ts_str).replace("Z", "+00:00"))
            if ts < cutoff:
                continue
        except ValueError:
            continue

        row_copy = dict(r)
        row_copy["notional_value"] = round(float(price) * int(vol), 2)
        row_copy["wash_trade_flag"] = False
        curated.append(row_copy)

    return curated


def _summarize_dimensions(
    eval_results: List[RuleEvaluationResult],
) -> List[Dict[str, Any]]:
    """Aggregates per-dimension rule pass counts and percentages from RuleEvaluationResult list."""
    dims_order = ["COMPLETENESS", "VALIDITY", "FRESHNESS", "INTEGRITY"]
    out: List[Dict[str, Any]] = []
    for dim in dims_order:
        dim_rules = [r for r in eval_results if r.dimension == dim]
        total = len(dim_rules)
        passed = sum(1 for r in dim_rules if r.passed)
        score = round(100.0 * passed / total, 2) if total > 0 else 100.0
        out.append(
            {
                "dimension": dim,
                "passed": passed,
                "total": total,
                "score_pct": score,
                "status": "PASS" if passed == total else "FAIL",
            }
        )
    return out


def _convert_eval_results(
    eval_results: List[RuleEvaluationResult],
) -> List[Dict[str, Any]]:
    """Converts RuleEvaluationResult objects into JSON-serializable rule dicts."""
    return [
        {
            "rule_name": r.rule_name,
            "dimension": r.dimension,
            "rule_type": r.rule_type,
            "column": r.column,
            "status": "PASS" if r.passed else "FAIL",
            "passed_records": r.rows_passed,
            "failed_records": r.rows_evaluated - r.rows_passed,
            "pass_rate": round(r.pass_ratio * 100.0, 2),
            "description": r.description,
        }
        for r in eval_results
    ]


def build_scorecard_profiles(
    thresholds: Dict[str, Any],
) -> Tuple[
    Dict[str, Any],
    Dict[str, Any],
    List[RuleEvaluationResult],
    List[RuleEvaluationResult],
    List[Dict[str, Any]],
    Dict[str, str],
]:
    """Evaluates both Raw Landing Table (14 rows -> Grade E) and Curated View (10 rows -> Grade A)."""
    spec_path = REPO_ROOT / "config" / "dataplex_dq_spec.yaml"
    sim = OfflineSimulationEngine(
        project_id="demo-project",
        dataset_id="sgx_market_data",
        table_id="equity_trades",
        spec_file=spec_path,
    )
    dq_spec = load_yaml_file(spec_path)
    raw_records, violation_tags = sim.generate_synthetic_dataset()

    # 1. Evaluate Raw Landing Table (all 14 synthetic rows)
    raw_eval_results = sim.evaluate_rules(dq_spec, raw_records)
    raw_sc = sim.build_scorecard(raw_eval_results)
    raw_rules_dicts = _convert_eval_results(raw_eval_results)
    raw_critical_failures = sum(
        1
        for r in raw_rules_dicts
        if r["status"] == "FAIL"
        and r["dimension"] in ("INTEGRITY", "FRESHNESS", "VALIDITY")
    )
    raw_grade = compute_nutri_grade(
        overall_pass_pct=float(raw_sc.overall_score_pct),
        critical_failures=raw_critical_failures,
        thresholds=thresholds,
    )
    raw_profile = {
        "asset_id": "equity-trades-raw",
        "table_fqn": "sgx_market_data.equity_trades",
        "title": "Raw Landing Table (Zero-ETL Stream)",
        "subtitle": "Unfiltered Pub/Sub Storage Write API ingress table (14 evaluated rows: 10 conforming + 4 injected anomalies)",
        "rows_evaluated": len(raw_records),
        "nutri_grade": raw_grade,
        "total_rules": raw_sc.total_rules_evaluated,
        "passed_rules": raw_sc.total_rules_passed,
        "failed_rules": raw_sc.total_rules_failed,
        "dimensions": _summarize_dimensions(raw_eval_results),
        "rules": raw_rules_dicts,
    }

    # 2. Filter records through the Curated Contract View WHERE predicates and evaluate
    curated_records = filter_curated_records(raw_records)
    curated_eval_results = sim.evaluate_rules(dq_spec, curated_records)
    curated_sc = sim.build_scorecard(curated_eval_results)
    curated_rules_dicts = _convert_eval_results(curated_eval_results)
    curated_critical_failures = sum(
        1
        for r in curated_rules_dicts
        if r["status"] == "FAIL"
        and r["dimension"] in ("INTEGRITY", "FRESHNESS", "VALIDITY")
    )
    curated_grade = compute_nutri_grade(
        overall_pass_pct=float(curated_sc.overall_score_pct),
        critical_failures=curated_critical_failures,
        thresholds=thresholds,
    )
    curated_profile = {
        "asset_id": "equity-trades-curated",
        "table_fqn": "sgx_market_data.equity_trades_curated",
        "title": "Curated Contract View (Consumer Certified)",
        "subtitle": f"Contract-enforced analytical view ({len(curated_records)} certified rows passing all 9 predicates + 2 derived columns)",
        "rows_evaluated": len(curated_records),
        "nutri_grade": curated_grade,
        "total_rules": curated_sc.total_rules_evaluated,
        "passed_rules": curated_sc.total_rules_passed,
        "failed_rules": curated_sc.total_rules_failed,
        "dimensions": _summarize_dimensions(curated_eval_results),
        "rules": curated_rules_dicts,
    }

    return (
        raw_profile,
        curated_profile,
        raw_eval_results,
        curated_eval_results,
        raw_records,
        violation_tags,
    )


def _compute_column_rule_stats(
    col_name: str,
    raw_eval_results: List[RuleEvaluationResult],
    curated_eval_results: List[RuleEvaluationResult],
    raw_records: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Derives per-column pass percentages and failure diagnostics directly from evaluation results."""

    def match_rules(
        results: List[RuleEvaluationResult],
    ) -> List[RuleEvaluationResult]:
        matched = [r for r in results if r.column == col_name]
        if col_name in ("buyer_id", "seller_id"):
            matched.extend(
                [r for r in results if r.dimension == "INTEGRITY" and not r.column]
            )
        return matched

    raw_matched = match_rules(raw_eval_results)
    cur_matched = match_rules(curated_eval_results)

    raw_pct = (
        round(
            100.0 * sum(1 for r in raw_matched if r.passed) / len(raw_matched), 1
        )
        if raw_matched
        else 100.0
    )
    cur_pct = (
        round(
            100.0 * sum(1 for r in cur_matched if r.passed) / len(cur_matched), 1
        )
        if cur_matched
        else 100.0
    )

    detail = "PASS (All column rules satisfied)"
    if raw_pct < 100.0:
        if col_name == "price":
            bad = next(
                (r for r in raw_records if float(r.get("price", 1)) <= 0), {}
            )
            detail = f"FAIL (Negative price {bad.get('price')} in {bad.get('trade_id')})"
        elif col_name == "volume":
            bad = next(
                (r for r in raw_records if int(r.get("volume", 1)) <= 0), {}
            )
            detail = f"FAIL (Zero volume {bad.get('volume')} in {bad.get('trade_id')})"
        elif col_name in ("buyer_id", "seller_id"):
            bad = next(
                (
                    r
                    for r in raw_records
                    if r.get("buyer_id") == r.get("seller_id")
                ),
                {},
            )
            detail = f"FAIL (Wash trade self-match {bad.get('buyer_id')} in {bad.get('trade_id')})"
        elif col_name == "trade_timestamp":
            bad = next(
                (
                    r
                    for r in raw_records
                    if "FRESHNESS" in str(r.get("trade_id", ""))
                ),
                {},
            )
            detail = f"FAIL (Stale >2h SLA timestamp in {bad.get('trade_id')})"

    return {
        "raw_score_pct": raw_pct,
        "curated_score_pct": cur_pct,
        "raw_status_detail": detail,
    }


def build_column_dictionary_rows(
    contract: Dict[str, Any],
    glossary_cfg: Dict[str, Any],
    location: str,
    raw_eval_results: List[RuleEvaluationResult],
    curated_eval_results: List[RuleEvaluationResult],
    raw_records: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Constructs the unified 10-column dictionary (8 Inherited Source + 2 Platform-Derived)."""
    glossary_id = str(
        glossary_cfg.get("glossary", {}).get("id", "exchange-source-dictionary")
    )
    terms_by_col = {
        str(t["column_name"]): t for t in glossary_cfg.get("terms", [])
    }
    rows: List[Dict[str, Any]] = []

    for prop in extract_schema_properties(contract):
        col_name = str(prop["name"])
        term = terms_by_col.get(col_name, {})
        term_id = str(term.get("id", col_name.replace("_", "-")))
        stats = _compute_column_rule_stats(
            col_name, raw_eval_results, curated_eval_results, raw_records
        )
        rows.append(
            {
                "column_name": col_name,
                "business_name": str(prop.get("businessName", col_name)),
                "physical_type": str(prop.get("physicalType", "STRING")),
                "required": bool(prop.get("required", False)),
                "provenance_category": "inherited",
                "provenance_badge": str(
                    term.get(
                        "provenance_badge",
                        "[Inherited: Upstream Source Dictionary]",
                    )
                ),
                "governance_owner": "Upstream Source Producer (Matching Engine)",
                "source_spec_ref": str(
                    term.get("source_spec_ref", "Upstream Source Dictionary")
                ),
                "glossary_term_id": term_id,
                "glossary_term_path": f"locations/{location}/glossaries/{glossary_id}/terms/{term_id}",
                "entry_link_raw": f"def-raw-{term_id}",
                "entry_link_curated": f"def-curated-{term_id}",
                "sql_expression": col_name,
                "description": str(
                    term.get("description") or prop.get("description") or ""
                ),
                "dq_rules": list(term.get("dq_rules", [])),
                "raw_score_pct": stats["raw_score_pct"],
                "curated_score_pct": stats["curated_score_pct"],
                "raw_status_detail": stats["raw_status_detail"],
            }
        )

    for dcol in glossary_cfg.get("derived_columns", []):
        d_name = str(dcol["column_name"])
        rows.append(
            {
                "column_name": d_name,
                "business_name": d_name.replace("_", " ").title(),
                "physical_type": str(dcol.get("data_type", "NUMERIC")),
                "required": False,
                "provenance_category": "ai_enriched",
                "provenance_badge": str(
                    dcol.get(
                        "provenance_badge",
                        "[Platform-Derived: Steward Authored (AI-Assisted Pattern)]",
                    )
                ),
                "governance_owner": "Platform Data Steward (Curated Warehouse Layer)",
                "source_spec_ref": str(
                    dcol.get("source_spec_ref", "Curated View Expression")
                ),
                "glossary_term_id": None,
                "glossary_term_path": "Curated View Expression (Steward Approved)",
                "entry_link_raw": None,
                "entry_link_curated": None,
                "sql_expression": str(dcol.get("sql_expression", d_name)),
                "description": str(dcol.get("description", "")),
                "dq_rules": list(dcol.get("dq_rules", [])),
                "raw_score_pct": None,
                "curated_score_pct": 100.0,
                "raw_status_detail": "Curated View Only",
            }
        )

    return rows


def build_quarantine_samples(
    raw_records: List[Dict[str, Any]],
    violation_tags: Dict[str, str],
) -> List[Dict[str, Any]]:
    """Builds Gate 1 / Gate 2 / Gate 3 quarantine records grounded in the synthetic dataset."""
    viol_rows = [
        r for r in raw_records if str(r.get("trade_id", "")) in violation_tags
    ]
    wash_row = next(
        (
            r
            for r in viol_rows
            if (
                r.get("buyer_id") is not None
                and r.get("buyer_id") == r.get("seller_id")
            )
            or "WASH" in str(r.get("trade_id", ""))
        ),
        viol_rows[-1] if viol_rows else {},
    )
    neg_row = next(
        (
            r
            for r in viol_rows
            if float(r.get("price", 0) or 0) <= 0.0
            or "PRICE" in str(r.get("trade_id", ""))
        ),
        viol_rows[0] if viol_rows else {},
    )

    return [
        {
            "gate": "Gate 1 — Pub/Sub Wire Schema Enforcement",
            "disposition": "HTTP 400 INVALID_ARGUMENT (Blocked at Ingress)",
            "rule_triggered": "Avro Schema Contract (schemas/trade_event_v1.avsc)",
            "trade_id": "TR-MALFORMED-WIRE-001",
            "instrument_code": "D05.SI",
            "summary": "Upstream publisher attempted to send string 'INVALID_PRICE' for numeric field `price` and omitted required `buyer_id`. Blocked before reaching BigQuery.",
            "payload_json": json.dumps(
                {
                    "trade_id": "TR-MALFORMED-WIRE-001",
                    "instrument_code": "D05.SI",
                    "price": "INVALID_PRICE_STRING",
                    "volume": 1000,
                },
                indent=2,
            ),
        },
        {
            "gate": "Gate 2 — BigQuery Direct Subscription DLQ Routing",
            "disposition": "Routed to Dead-Letter Topic (sgx-equity-trades-dlq-topic)",
            "rule_triggered": "BigQuery Storage Write API Type / Constraint Mismatch",
            "trade_id": "TR-DLQ-OVERFLOW-002",
            "instrument_code": "Z74.SI",
            "summary": "Unparseable timestamp format (`NOT_A_UTC_TIMESTAMP`) rejected by BigQuery table schema and preserved in DLQ with zero data loss.",
            "payload_json": json.dumps(
                {
                    "trade_id": "TR-DLQ-OVERFLOW-002",
                    "instrument_code": "Z74.SI",
                    "price": 31.25,
                    "volume": 500,
                    "buyer_id": "BROKER_UOB_01",
                    "seller_id": "BROKER_DBS_02",
                    "trade_timestamp": "NOT_A_UTC_TIMESTAMP",
                    "trade_status": "EXECUTED",
                },
                indent=2,
            ),
        },
        {
            "gate": "Gate 3 — Dataplex Auto DQ & Curated View Filter",
            "disposition": "Excluded from Curated Contract View (Flagged in Raw Table)",
            "rule_triggered": "Anti-Wash Trading & Validity Rules (buyer_id != seller_id, price > 0)",
            "trade_id": str(wash_row.get("trade_id", "TR-VIOL-WASH-004")),
            "instrument_code": str(wash_row.get("instrument_code", "Z74.SI")),
            "summary": (
                f"Injected synthetic anomalies `{wash_row.get('trade_id')}` "
                f"(self-trade `{wash_row.get('buyer_id')}`) and `{neg_row.get('trade_id')}` "
                f"(negative price `{neg_row.get('price')}`) fail raw DataScan (55.56% Grade E) "
                "and are filtered out of `equity_trades_curated` (100.0% Grade A)."
            ),
            "payload_json": json.dumps(
                {
                    "wash_trade_anomaly": {
                        "trade_id": wash_row.get("trade_id"),
                        "instrument_code": wash_row.get("instrument_code"),
                        "price": wash_row.get("price"),
                        "volume": wash_row.get("volume"),
                        "buyer_id": wash_row.get("buyer_id"),
                        "seller_id": wash_row.get("seller_id"),
                    },
                    "negative_price_anomaly": {
                        "trade_id": neg_row.get("trade_id"),
                        "instrument_code": neg_row.get("instrument_code"),
                        "price": neg_row.get("price"),
                        "volume": neg_row.get("volume"),
                    },
                },
                indent=2,
            ),
        },
    ]


def _probe_live_bigquery_dq(
    project_id: str, dataset_id: str
) -> Optional[Dict[str, Any]]:
    """Queries BigQuery v_dq_rule_summary when running in --live mode."""
    sql = (
        f"SELECT total_rules_evaluated, total_rules_passed, total_rules_failed, "
        f"overall_score_pct, executive_rag_status "
        f"FROM `{project_id}.{dataset_id}.v_dq_rule_summary` LIMIT 1"
    )
    try:
        res = subprocess.run(
            [
                "bq",
                "query",
                f"--project_id={project_id}",
                "--use_legacy_sql=false",
                "--format=json",
            ],
            input=sql,
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
        if res.returncode == 0 and res.stdout.strip():
            idx = res.stdout.find("[")
            if idx != -1:
                rows = json.loads(res.stdout[idx:])
                if rows:
                    return dict(rows[0])
    except Exception:
        pass
    return None


def build_snapshot(
    source: str = "offline",
    project_id: str = "",
    as_of: str = "2026-09-24T09:00:00Z",
) -> Dict[str, Any]:
    """Builds the complete JSON-serializable snapshot driving the Business Contract Portal."""
    contract, glossary_cfg, product_cfg, aspect_payload = load_catalog_configs(
        REPO_ROOT
    )
    dataset_id, table_id, location = extract_target_coordinates(contract)
    thresholds = product_cfg.get("nutri_grade_thresholds", {})

    (
        raw_profile,
        curated_profile,
        raw_eval_results,
        curated_eval_results,
        raw_records,
        violation_tags,
    ) = build_scorecard_profiles(thresholds)

    columns = build_column_dictionary_rows(
        contract=contract,
        glossary_cfg=glossary_cfg,
        location=location,
        raw_eval_results=raw_eval_results,
        curated_eval_results=curated_eval_results,
        raw_records=raw_records,
    )

    raw_aspect = (
        next(iter(aspect_payload.values()), {}).get("data", {})
        if isinstance(aspect_payload, dict) and aspect_payload
        else {}
    )
    rc_data = product_cfg.get("refresh_cadence_aspect", {}).get("data", {})

    live_status: Dict[str, Any] = {
        "mode": "offline",
        "banner_text": (
            "OFFLINE SIMULATION MODE — Scores computed deterministically from 14-row synthetic batch (10 conforming + 4 injected SLA violations)"
        ),
        "glossary_verified": False,
        "data_product_verified": False,
        "entry_links_count": 16,
        "bigquery_dq_summary": None,
    }

    if source == "live" and project_id:
        try:
            client = DataplexClient(transport=UrllibTransport(quota_project=project_id))
            g_id = glossary_cfg["glossary"]["id"]
            dp_id = product_cfg["data_product"]["id"]
            g_obj = client.get_or_none(
                f"{DATAPLEX_BASE_URL}/projects/{project_id}/locations/{location}/glossaries/{g_id}"
            )
            dp_obj = client.get_or_none(
                f"{DATAPLEX_BASE_URL}/projects/{project_id}/locations/{location}/dataProducts/{dp_id}"
            )
            live_status["glossary_verified"] = g_obj is not None
            live_status["data_product_verified"] = dp_obj is not None
            bq_dq = _probe_live_bigquery_dq(project_id, dataset_id)
            live_status["bigquery_dq_summary"] = bq_dq
            if (
                live_status["glossary_verified"]
                and live_status["data_product_verified"]
                and bq_dq is not None
            ):
                live_score = float(bq_dq.get("overall_score_pct", raw_profile["nutri_grade"]["score_pct"]))
                live_passed = int(bq_dq.get("total_rules_passed", raw_profile["passed_rules"]))
                live_total = int(bq_dq.get("total_rules_evaluated", raw_profile["total_rules"]))
                live_failed = int(bq_dq.get("total_rules_failed", raw_profile["failed_rules"]))
                raw_profile["passed_rules"] = live_passed
                raw_profile["total_rules"] = live_total
                raw_profile["failed_rules"] = live_failed
                raw_profile["nutri_grade"] = compute_nutri_grade(
                    overall_pass_pct=live_score,
                    critical_failures=live_failed,
                    thresholds=thresholds,
                )
                live_status["mode"] = "live"
                live_status["banner_text"] = (
                    f"LIVE GCP TELEMETRY MODE — Dataplex Catalog & BigQuery DQ verified in project '{project_id}' ({location})"
                )
            elif live_status["glossary_verified"] or live_status["data_product_verified"]:
                live_status["mode"] = "hybrid"
                live_status["banner_text"] = (
                    f"LIVE CATALOG METADATA + DETERMINISTIC SCORECARD SIMULATION — Catalog verified in '{project_id}' ({location}); DQ scorecard uses 14-row reference batch"
                )
            else:
                live_status["mode"] = "offline"
                live_status["banner_text"] = (
                    f"OFFLINE FALLBACK MODE — Live probe to '{project_id}' ({location}) unavailable; showing 14-row deterministic simulation"
                )
        except Exception:
            live_status["mode"] = "offline"

    inherited_count = sum(
        1 for c in columns if c["provenance_category"] == "inherited"
    )
    ai_enriched_count = sum(
        1 for c in columns if c["provenance_category"] == "ai_enriched"
    )

    return {
        "as_of": as_of,
        "live_status": live_status,
        "contract_metadata": {
            "id": str(contract.get("id", "urn:datacontract:exchange:equity_trades")),
            "api_version": str(contract.get("apiVersion", "3.0.0")),
            "version": str(contract.get("version", "1.0.0")),
            "status": str(contract.get("status", "active")),
            "domain": str(contract.get("domain", "equities_market")),
            "location": location,
            "dataset": dataset_id,
            "raw_table": table_id,
            "curated_view": f"{table_id}_curated",
            "regulatory_standard": str(
                raw_aspect.get("regulatory_standard", "MAS TRM Section 8")
            ),
            "criticality_tier": str(
                raw_aspect.get("criticality_tier", "TIER_1_CRITICAL")
            ),
            "freshness_sla_hours": int(raw_aspect.get("freshness_sla_hours", 2)),
            "refresh_cadence": {
                "frequency": str(rc_data.get("frequency", "Daily")),
                "refreshTime": str(rc_data.get("refreshTime", "09:00 SGT")),
            },
        },
        "data_product": product_cfg.get("data_product", {}),
        "access_groups": product_cfg.get("access_groups", {}),
        "handshake": product_cfg.get("handshake", {}),
        "nutri_grade_thresholds": thresholds,
        "profiles": {
            "curated": curated_profile,
            "raw": raw_profile,
        },
        "column_counts": {
            "all": len(columns),
            "inherited": inherited_count,
            "ai_enriched": ai_enriched_count,
        },
        "columns": columns,
        "quarantine_samples": build_quarantine_samples(raw_records, violation_tags),
    }


def safe_json_for_html_script(data: Dict[str, Any]) -> str:
    """Serializes JSON safely for embedding in <script type='application/json'>."""
    raw = json.dumps(data, indent=2, sort_keys=True)
    return (
        raw.replace("&", "\\u0026")
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("\u2028", "\\u2028")
        .replace("\u2029", "\\u2029")
    )


def render_portal_html(snapshot: Dict[str, Any]) -> str:
    """Renders the standalone single-pane Business Data Contract & Quality Grade Portal HTML."""
    embedded_json = safe_json_for_html_script(snapshot)
    dp_title = html.escape(
        str(
            snapshot.get("data_product", {}).get(
                "display_name", "Equities Market Execution Trades"
            )
        )
    )
    meta = snapshot.get("contract_metadata", {})
    contract_id = html.escape(str(meta.get("id", "")))
    api_ver = html.escape(str(meta.get("api_version", "3.0.0")))
    fresh_h = int(meta.get("freshness_sla_hours", 2))
    rc = meta.get("refresh_cadence", {})
    rc_label = html.escape(
        f"Dataplex Cadence Aspect: {rc.get('frequency', 'Daily')} ({rc.get('refreshTime', '09:00 SGT')}) • ODCS Freshness SLA: <= {fresh_h}h"
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{dp_title} — Business Data Contract &amp; Quality Grade Portal</title>
  <style>
    :root {{
      --bg: #f4f6f9;
      --card: #ffffff;
      --ink: #111827;
      --muted: #4b5563;
      --border: #e5e7eb;
      --navy: #0f2942;
      --blue: #1a73e8;
      --teal: #0d9488;
      --purple: #6d28d9;
      --grade-a: #007a33;
      --grade-b: #58a618;
      --grade-c: #f2a900;
      --grade-d: #e86c00;
      --grade-e: #d92b2b;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Oxygen, sans-serif;
      background: var(--bg);
      color: var(--ink);
      line-height: 1.45;
    }}
    .mode-banner {{
      background: #fef3c7;
      color: #92400e;
      border-bottom: 1px solid #fde68a;
      padding: 8px 32px;
      font-size: 12px;
      font-weight: 700;
      display: flex;
      justify-content: space-between;
      align-items: center;
    }}
    .mode-banner.live {{
      background: #dcfce7;
      color: #166534;
      border-bottom-color: #bbf7d0;
    }}
    header.topbar {{
      background: linear-gradient(135deg, #0b2239 0%, #153e63 100%);
      color: #ffffff;
      padding: 20px 32px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      flex-wrap: wrap;
      gap: 16px;
      border-bottom: 3px solid #1a73e8;
    }}
    .topbar-left h1 {{
      margin: 0 0 6px 0;
      font-size: 22px;
      font-weight: 700;
      letter-spacing: -0.01em;
    }}
    .topbar-meta {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      font-size: 12px;
      color: #dbeafe;
    }}
    .pill {{
      display: inline-flex;
      align-items: center;
      padding: 3px 10px;
      border-radius: 999px;
      font-size: 11px;
      font-weight: 600;
      background: rgba(255,255,255,0.14);
      color: #ffffff;
    }}
    .btn-primary {{
      background: #1a73e8;
      color: #ffffff;
      border: none;
      padding: 10px 18px;
      border-radius: 6px;
      font-weight: 600;
      font-size: 13px;
      cursor: pointer;
      transition: background 0.15s;
    }}
    .btn-primary:hover {{ background: #1557b0; }}
    main.container {{
      max-width: 1360px;
      margin: 24px auto;
      padding: 0 24px 48px;
      display: flex;
      flex-direction: column;
      gap: 22px;
    }}
    .card {{
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 20px 24px;
      box-shadow: 0 1px 3px rgba(0,0,0,0.04);
    }}
    .section-title {{
      margin: 0 0 14px 0;
      font-size: 16px;
      font-weight: 700;
      color: var(--navy);
      display: flex;
      justify-content: space-between;
      align-items: center;
      flex-wrap: wrap;
      gap: 12px;
    }}
    .handshake-grid {{
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 16px;
    }}
    @media (max-width: 960px) {{
      .handshake-grid {{ grid-template-columns: 1fr; }}
    }}
    .layer-box {{
      border: 1px solid var(--border);
      border-top: 4px solid var(--blue);
      border-radius: 8px;
      padding: 14px 16px;
      background: #f9fafb;
    }}
    .layer-box.steward {{ border-top-color: var(--teal); }}
    .layer-box.consumer {{ border-top-color: var(--purple); }}
    .layer-role {{
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      font-weight: 700;
      color: var(--muted);
      margin-bottom: 4px;
    }}
    .layer-team {{
      font-size: 14px;
      font-weight: 700;
      color: var(--ink);
      margin-bottom: 8px;
    }}
    .layer-list {{
      margin: 0;
      padding-left: 18px;
      font-size: 12.5px;
      color: var(--muted);
    }}
    .layer-list li {{ margin-bottom: 4px; }}
    .nutri-row {{
      display: grid;
      grid-template-columns: 400px 1fr;
      gap: 24px;
      align-items: center;
    }}
    @media (max-width: 960px) {{
      .nutri-row {{ grid-template-columns: 1fr; }}
    }}
    .nutri-badge-panel {{
      border: 2px solid var(--border);
      border-radius: 12px;
      padding: 18px;
      text-align: center;
      background: #ffffff;
    }}
    .nutri-strip {{
      display: flex;
      justify-content: center;
      gap: 6px;
      margin: 12px 0;
    }}
    .nutri-letter {{
      width: 46px;
      height: 46px;
      border-radius: 8px;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 20px;
      font-weight: 800;
      color: #ffffff;
      opacity: 0.28;
      transform: scale(0.92);
      transition: all 0.2s;
    }}
    .nutri-letter.active {{
      opacity: 1;
      transform: scale(1.14);
      box-shadow: 0 4px 12px rgba(0,0,0,0.22);
      border: 2px solid #111827;
    }}
    .nutri-A {{ background: var(--grade-a); }}
    .nutri-B {{ background: var(--grade-b); }}
    .nutri-C {{ background: var(--grade-c); }}
    .nutri-D {{ background: var(--grade-d); }}
    .nutri-E {{ background: var(--grade-e); }}
    .toggle-group {{
      display: inline-flex;
      border: 1px solid var(--border);
      border-radius: 8px;
      overflow: hidden;
      background: #f3f4f6;
    }}
    .toggle-btn {{
      border: none;
      background: transparent;
      padding: 8px 14px;
      font-size: 12.5px;
      font-weight: 600;
      cursor: pointer;
      color: var(--muted);
    }}
    .toggle-btn.active {{
      background: var(--navy);
      color: #ffffff;
    }}
    .dim-grid {{
      display: grid;
      grid-template-columns: repeat(2, 1fr);
      gap: 12px;
    }}
    .dim-card {{
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 12px 14px;
      background: #f9fafb;
    }}
    .dim-header {{
      display: flex;
      justify-content: space-between;
      font-size: 12.5px;
      font-weight: 700;
      margin-bottom: 6px;
    }}
    .progress-track {{
      height: 8px;
      background: #e5e7eb;
      border-radius: 999px;
      overflow: hidden;
    }}
    .progress-fill {{
      height: 100%;
      border-radius: 999px;
      transition: width 0.25s;
    }}
    .filter-bar {{
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
    }}
    .filter-pill {{
      border: 1px solid var(--border);
      background: #f9fafb;
      padding: 6px 13px;
      border-radius: 999px;
      font-size: 12px;
      font-weight: 600;
      cursor: pointer;
      color: var(--muted);
    }}
    .filter-pill.active {{
      background: var(--blue);
      color: #ffffff;
      border-color: var(--blue);
    }}
    table.contract-table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 12.5px;
    }}
    table.contract-table th, table.contract-table td {{
      padding: 10px 12px;
      border-bottom: 1px solid var(--border);
      text-align: left;
      vertical-align: top;
    }}
    table.contract-table th {{
      background: #f9fafb;
      font-weight: 700;
      color: var(--navy);
      font-size: 11.5px;
      text-transform: uppercase;
    }}
    .badge-inherited {{
      display: inline-block;
      padding: 3px 8px;
      border-radius: 4px;
      font-size: 11px;
      font-weight: 700;
      background: #ccfbf1;
      color: #115e59;
      border: 1px solid #99f6e4;
    }}
    .badge-ai {{
      display: inline-block;
      padding: 3px 8px;
      border-radius: 4px;
      font-size: 11px;
      font-weight: 700;
      background: #ede9fe;
      color: #5b21b6;
      border: 1px solid #ddd6fe;
    }}
    .quarantine-grid {{
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 14px;
    }}
    @media (max-width: 960px) {{
      .quarantine-grid {{ grid-template-columns: 1fr; }}
    }}
    .q-box {{
      border: 1px solid #fecaca;
      background: #fff5f5;
      border-radius: 8px;
      padding: 12px 14px;
    }}
    .q-box pre {{
      margin: 8px 0 0;
      padding: 8px;
      background: #111827;
      color: #f9fafb;
      border-radius: 6px;
      font-size: 11px;
      overflow-x: auto;
    }}
    .modal-backdrop {{
      display: none;
      position: fixed;
      inset: 0;
      background: rgba(17,24,39,0.6);
      align-items: center;
      justify-content: center;
      z-index: 1000;
    }}
    .modal-backdrop.open {{ display: flex; }}
    .modal-card {{
      background: #ffffff;
      border-radius: 10px;
      max-width: 600px;
      width: 92%;
      padding: 22px 24px;
      box-shadow: 0 10px 25px rgba(0,0,0,0.2);
    }}
    .modal-card pre {{
      background: #111827;
      color: #e5e7eb;
      padding: 10px;
      border-radius: 6px;
      font-size: 11.5px;
      overflow-x: auto;
    }}
  </style>
</head>
<body>
  <div id="mode-status-banner" class="mode-banner"></div>
  <header class="topbar">
    <div class="topbar-left">
      <h1>{dp_title}</h1>
      <div class="topbar-meta">
        <span class="pill">Contract ID: {contract_id}</span>
        <span class="pill">ODCS v{api_ver}</span>
        <span class="pill">Dataplex Business Glossary + 16 Column EntryLinks</span>
        <span class="pill">{rc_label}</span>
      </div>
    </div>
    <div>
      <button id="open-access-modal-btn" class="btn-primary" type="button">
        Consumer Access Handshake (DataAsset IAM Spec)
      </button>
    </div>
  </header>

  <main class="container">
    <!-- 1. 3-Layer Internal Warehouse Handshake -->
    <section class="card">
      <div class="section-title">
        <span>1. Three-Layer Internal Warehouse Data Contract Handshake</span>
        <span style="font-size:12px;color:var(--muted);">Producer &harr; Platform Steward &harr; Approved Business Consumers</span>
      </div>
      <div id="handshake-container" class="handshake-grid"></div>
    </section>

    <!-- 2. 5-Tier A-E Quality & SLA Scorecard -->
    <section class="card">
      <div class="section-title">
        <span>2. Contract Quality Grade (A&ndash;E Nutri-Score / 5-Tier SLA Scale)</span>
        <div class="toggle-group" role="tablist" aria-label="Asset Layer Switcher">
          <button id="btn-layer-curated" class="toggle-btn active" type="button"></button>
          <button id="btn-layer-raw" class="toggle-btn" type="button"></button>
        </div>
      </div>
      <div class="nutri-row">
        <div class="nutri-badge-panel">
          <div id="active-asset-title" style="font-weight:700;font-size:14px;color:var(--navy);"></div>
          <div id="active-asset-fqn" style="font-family:monospace;font-size:12px;color:var(--muted);margin-top:2px;"></div>
          <div class="nutri-strip">
            <div id="grade-pill-A" class="nutri-letter nutri-A">A</div>
            <div id="grade-pill-B" class="nutri-letter nutri-B">B</div>
            <div id="grade-pill-C" class="nutri-letter nutri-C">C</div>
            <div id="grade-pill-D" class="nutri-letter nutri-D">D</div>
            <div id="grade-pill-E" class="nutri-letter nutri-E">E</div>
          </div>
          <div id="active-grade-score" style="font-size:22px;font-weight:800;"></div>
          <div id="active-grade-label" style="font-size:12.5px;font-weight:600;color:var(--muted);"></div>
          <div style="font-size:11px;color:var(--muted);margin-top:6px;">
            Note: 5-tier A&ndash;E scale extends Singapore HPB 4-grade (A&ndash;D) Nutri-Grade to distinguish 6/9 (D) vs &le;5/9 (E) rule breaches.
          </div>
        </div>
        <div>
          <div id="dimensions-container" class="dim-grid"></div>
        </div>
      </div>
    </section>

    <!-- 3. Column Dictionary & Provenance Filter -->
    <section class="card">
      <div class="section-title">
        <span>3. Column Dictionary &amp; Provenance Explorer (Dataplex Business Glossary EntryLinks)</span>
        <div class="filter-bar">
          <button id="filter-all" class="filter-pill active" type="button"></button>
          <button id="filter-inherited" class="filter-pill" type="button"></button>
          <button id="filter-ai" class="filter-pill" type="button"></button>
        </div>
      </div>
      <div style="overflow-x:auto;">
        <table class="contract-table">
          <thead>
            <tr>
              <th>Column &amp; Type</th>
              <th>Provenance &amp; Governance Layer</th>
              <th>Dataplex Business Glossary Term / Expression</th>
              <th>Business Definition</th>
              <th>Evaluated Layer DQ Status</th>
            </tr>
          </thead>
          <tbody id="column-table-body"></tbody>
        </table>
      </div>
    </section>

    <!-- 4. 3-Gate Defense-in-Depth & Quarantine (DLQ) Forensics -->
    <section class="card">
      <div class="section-title">
        <span>4. Three-Gate Defense-in-Depth &amp; Quarantine (DLQ) Payload Inspector</span>
        <span style="font-size:12px;color:var(--muted);">Zero Data Loss &bull; Deterministic Quarantine &bull; MAS TRM Section 8 Audit Trail</span>
      </div>
      <div id="quarantine-container" class="quarantine-grid"></div>
    </section>
  </main>

  <!-- Consumer Access Handshake Modal -->
  <div id="access-modal" class="modal-backdrop" role="dialog" aria-modal="true">
    <div class="modal-card">
      <h3 style="margin-top:0;color:var(--navy);">Consumer Access Handshake — Dataplex DataProduct &amp; DataAsset IAM</h3>
      <p style="font-size:13px;color:var(--muted);">
        Inspect the Dataplex <code>DataProduct.accessGroups</code> and <code>DataAsset.accessGroupConfigs</code> binding granting read access (<code>roles/bigquery.dataViewer</code>) on the Grade-A Curated Contract View:
      </p>
      <label style="display:block;font-size:12px;font-weight:700;margin-bottom:4px;">Consumer Access Group</label>
      <select id="access-group-select" style="width:100%;padding:8px;border-radius:6px;border:1px solid var(--border);margin-bottom:12px;">
        <option value="market-surveillance">market-surveillance — Market Surveillance &amp; Regulatory Compliance</option>
        <option value="clearing-risk">clearing-risk — Clearing House &amp; Settlement Risk</option>
      </select>
      <label style="display:block;font-size:12px;font-weight:700;margin-bottom:4px;">Dataplex DataAsset IAM Binding &amp; Access Request Specification</label>
      <pre id="access-payload-preview"></pre>
      <div style="display:flex;justify-content:flex-end;gap:10px;margin-top:14px;">
        <button id="close-access-modal-btn" class="filter-pill" type="button">Close</button>
      </div>
    </div>
  </div>

  <script id="contract-snapshot-data" type="application/json">
{embedded_json}
  </script>
  <script>
    (function() {{
      const snapshotEl = document.getElementById("contract-snapshot-data");
      const snapshot = JSON.parse(snapshotEl.textContent);
      let currentLayer = "curated";
      let currentFilter = "all";

      function initDynamicChrome() {{
        const ls = snapshot.live_status || {{}};
        const banner = document.getElementById("mode-status-banner");
        banner.textContent = ls.banner_text || "OFFLINE SIMULATION MODE";
        if (ls.mode === "live") {{
          banner.classList.add("live");
        }}

        const cProf = snapshot.profiles.curated;
        const rProf = snapshot.profiles.raw;
        document.getElementById("btn-layer-curated").textContent =
          "Curated Contract View (Grade " + cProf.nutri_grade.grade + " — " +
          cProf.nutri_grade.score_pct.toFixed(1) + "% • " + cProf.passed_rules + "/" + cProf.total_rules + " Rules)";
        document.getElementById("btn-layer-raw").textContent =
          "Raw Landing Table (Grade " + rProf.nutri_grade.grade + " — " +
          rProf.nutri_grade.score_pct.toFixed(1) + "% • " + rProf.passed_rules + "/" + rProf.total_rules + " Rules)";

        const cc = snapshot.column_counts || {{}};
        document.getElementById("filter-all").textContent = "All Columns (" + (cc.all || 0) + ")";
        document.getElementById("filter-inherited").textContent = "Inherited: Source Dictionary (" + (cc.inherited || 0) + ")";
        document.getElementById("filter-ai").textContent = "Platform-Derived: Steward Authored (" + (cc.ai_enriched || 0) + ")";
      }}

      function renderHandshake() {{
        const container = document.getElementById("handshake-container");
        container.textContent = "";
        const hs = snapshot.handshake || {{}};
        const l1 = hs.layer_1_producer || {{}};
        const l2 = hs.layer_2_steward || {{}};
        const l3 = hs.layer_3_consumers || {{}};

        const layers = [
          {{ cls: "layer-box", role: l1.role || "Layer 1", team: l1.team || "", items: l1.responsibilities || [] }},
          {{ cls: "layer-box steward", role: l2.role || "Layer 2", team: l2.team || "", items: l2.responsibilities || [] }},
          {{
            cls: "layer-box consumer",
            role: l3.role || "Layer 3",
            team: "Approved Downstream Business Teams",
            items: (l3.teams || []).map(t => t.display_name + " — " + t.purpose + " (" + t.sla_tier + ")")
          }}
        ];

        layers.forEach(l => {{
          const box = document.createElement("div");
          box.className = l.cls;
          const r = document.createElement("div");
          r.className = "layer-role";
          r.textContent = l.role;
          const t = document.createElement("div");
          t.className = "layer-team";
          t.textContent = l.team;
          const ul = document.createElement("ul");
          ul.className = "layer-list";
          l.items.forEach(itemText => {{
            const li = document.createElement("li");
            li.textContent = itemText;
            ul.appendChild(li);
          }});
          box.appendChild(r);
          box.appendChild(t);
          box.appendChild(ul);
          container.appendChild(box);
        }});
      }}

      function renderScorecard() {{
        const prof = snapshot.profiles[currentLayer];
        const ng = prof.nutri_grade;
        document.getElementById("active-asset-title").textContent = prof.title;
        document.getElementById("active-asset-fqn").textContent =
          prof.table_fqn + " (" + prof.rows_evaluated + " evaluated rows)";
        document.getElementById("active-grade-score").textContent =
          "Grade " + ng.grade + " — " + ng.score_pct.toFixed(2) + "% (" + prof.passed_rules + "/" + prof.total_rules + " Rules Passed)";
        document.getElementById("active-grade-score").style.color = ng.color_hex;
        document.getElementById("active-grade-label").textContent = ng.label;

        ["A", "B", "C", "D", "E"].forEach(letter => {{
          const el = document.getElementById("grade-pill-" + letter);
          if (letter === ng.grade) {{
            el.classList.add("active");
          }} else {{
            el.classList.remove("active");
          }}
        }});

        const dimContainer = document.getElementById("dimensions-container");
        dimContainer.textContent = "";
        (prof.dimensions || []).forEach(d => {{
          const card = document.createElement("div");
          card.className = "dim-card";
          const hdr = document.createElement("div");
          hdr.className = "dim-header";
          const nameSpan = document.createElement("span");
          nameSpan.textContent = d.dimension;
          const valSpan = document.createElement("span");
          valSpan.textContent = d.score_pct.toFixed(1) + "% (" + d.passed + "/" + d.total + ")";
          valSpan.style.color = d.status === "PASS" ? "#007a33" : "#d92b2b";
          hdr.appendChild(nameSpan);
          hdr.appendChild(valSpan);

          const track = document.createElement("div");
          track.className = "progress-track";
          const fill = document.createElement("div");
          fill.className = "progress-fill";
          fill.style.width = Math.max(4, d.score_pct) + "%";
          fill.style.background = d.status === "PASS" ? "#007a33" : "#d92b2b";
          track.appendChild(fill);

          card.appendChild(hdr);
          card.appendChild(track);
          dimContainer.appendChild(card);
        }});
      }}

      function renderColumns() {{
        const tbody = document.getElementById("column-table-body");
        tbody.textContent = "";
        const activeGrade = snapshot.profiles[currentLayer].nutri_grade.grade;
        const cols = (snapshot.columns || []).filter(c => {{
          if (currentFilter === "all") return true;
          return c.provenance_category === currentFilter;
        }});

        cols.forEach(c => {{
          const tr = document.createElement("tr");

          const td1 = document.createElement("td");
          const strong = document.createElement("strong");
          strong.style.fontFamily = "monospace";
          strong.textContent = c.column_name;
          const typeDiv = document.createElement("div");
          typeDiv.style.fontSize = "11px";
          typeDiv.style.color = "#4b5563";
          typeDiv.textContent = c.physical_type + (c.required ? " • REQUIRED" : " • DERIVED");
          td1.appendChild(strong);
          td1.appendChild(typeDiv);

          const td2 = document.createElement("td");
          const badge = document.createElement("span");
          badge.className = c.provenance_category === "inherited" ? "badge-inherited" : "badge-ai";
          badge.textContent = c.provenance_badge;
          const ownerDiv = document.createElement("div");
          ownerDiv.style.fontSize = "11px";
          ownerDiv.style.color = "#4b5563";
          ownerDiv.style.marginTop = "4px";
          ownerDiv.textContent = c.governance_owner;
          td2.appendChild(badge);
          td2.appendChild(ownerDiv);

          const td3 = document.createElement("td");
          const refStrong = document.createElement("div");
          refStrong.style.fontWeight = "600";
          refStrong.textContent = c.source_spec_ref;
          const pathCode = document.createElement("div");
          pathCode.style.fontFamily = "monospace";
          pathCode.style.fontSize = "11px";
          pathCode.style.color = "#1a73e8";
          pathCode.textContent = c.glossary_term_id
            ? "Term: " + c.glossary_term_path + " (" + c.entry_link_curated + ")"
            : "SQL: " + c.sql_expression;
          td3.appendChild(refStrong);
          td3.appendChild(pathCode);

          const td4 = document.createElement("td");
          td4.textContent = c.description;

          const td5 = document.createElement("td");
          const statusSpan = document.createElement("span");
          statusSpan.style.fontWeight = "700";
          if (currentLayer === "curated") {{
            const curPct = c.curated_score_pct !== null ? c.curated_score_pct : 100.0;
            const curWord = curPct >= 100.0 ? "PASS" : "WARN";
            statusSpan.style.color = curPct >= 100.0 ? "#007a33" : "#d92b2b";
            statusSpan.textContent = curPct.toFixed(1) + "% " + curWord + " (Grade " + activeGrade + " Evaluated)";
          }} else {{
            if (c.raw_score_pct === null) {{
              statusSpan.style.color = "#6b7280";
              statusSpan.textContent = "N/A (Computed in Curated View)";
            }} else if (c.raw_score_pct < 100) {{
              statusSpan.style.color = "#d92b2b";
              statusSpan.textContent = c.raw_score_pct.toFixed(0) + "% — " + c.raw_status_detail;
            }} else {{
              statusSpan.style.color = "#007a33";
              statusSpan.textContent = "100.0% PASS";
            }}
          }}
          td5.appendChild(statusSpan);

          tr.appendChild(td1);
          tr.appendChild(td2);
          tr.appendChild(td3);
          tr.appendChild(td4);
          tr.appendChild(td5);
          tbody.appendChild(tr);
        }});
      }}

      function renderQuarantine() {{
        const qContainer = document.getElementById("quarantine-container");
        qContainer.textContent = "";
        (snapshot.quarantine_samples || []).forEach(q => {{
          const box = document.createElement("div");
          box.className = "q-box";
          const g = document.createElement("div");
          g.style.fontWeight = "700";
          g.style.fontSize = "13px";
          g.style.color = "#991b1b";
          g.textContent = q.gate;
          const disp = document.createElement("div");
          disp.style.fontSize = "11.5px";
          disp.style.fontWeight = "600";
          disp.style.marginTop = "2px";
          disp.textContent = q.disposition;
          const desc = document.createElement("p");
          desc.style.fontSize = "12px";
          desc.style.margin = "6px 0";
          desc.textContent = q.summary;
          const pre = document.createElement("pre");
          pre.textContent = q.payload_json;
          box.appendChild(g);
          box.appendChild(disp);
          box.appendChild(desc);
          box.appendChild(pre);
          qContainer.appendChild(box);
        }});
      }}

      function updateAccessModalPayload() {{
        const grp = document.getElementById("access-group-select").value;
        const meta = snapshot.contract_metadata || {{}};
        const dpId = (snapshot.data_product || {{}}).id || "equity-market-trades";
        const agSpec = (snapshot.access_groups || {{}})[grp] || {{}};
        const payload = {{
          dataProductResource: "projects/<PROJECT_NUMBER>/locations/" + meta.location + "/dataProducts/" + dpId,
          dataAssetResource: "projects/<PROJECT_NUMBER>/locations/" + meta.location + "/dataProducts/" + dpId + "/dataAssets/equity-trades-curated",
          linkedBigQueryResource: "//bigquery.googleapis.com/projects/<PROJECT_ID>/datasets/" + meta.dataset + "/tables/" + meta.curated_view,
          accessGroupConfig: {{
            accessGroupId: grp,
            principalGoogleGroup: agSpec.default_principal_group || (grp + "-consumers@example.com"),
            iamRoles: agSpec.iam_roles || ["roles/bigquery.dataViewer"]
          }}
        }};
        document.getElementById("access-payload-preview").textContent = JSON.stringify(payload, null, 2);
      }}

      document.getElementById("btn-layer-curated").addEventListener("click", function() {{
        currentLayer = "curated";
        this.classList.add("active");
        document.getElementById("btn-layer-raw").classList.remove("active");
        renderScorecard();
        renderColumns();
      }});
      document.getElementById("btn-layer-raw").addEventListener("click", function() {{
        currentLayer = "raw";
        this.classList.add("active");
        document.getElementById("btn-layer-curated").classList.remove("active");
        renderScorecard();
        renderColumns();
      }});

      const filterMap = {{
        "filter-all": "all",
        "filter-inherited": "inherited",
        "filter-ai": "ai_enriched"
      }};
      Object.keys(filterMap).forEach(btnId => {{
        document.getElementById(btnId).addEventListener("click", function() {{
          currentFilter = filterMap[btnId];
          Object.keys(filterMap).forEach(id => document.getElementById(id).classList.remove("active"));
          this.classList.add("active");
          renderColumns();
        }});
      }});

      document.getElementById("open-access-modal-btn").addEventListener("click", function() {{
        updateAccessModalPayload();
        document.getElementById("access-modal").classList.add("open");
      }});
      document.getElementById("close-access-modal-btn").addEventListener("click", function() {{
        document.getElementById("access-modal").classList.remove("open");
      }});
      document.getElementById("access-group-select").addEventListener("change", updateAccessModalPayload);

      initDynamicChrome();
      renderHandshake();
      renderScorecard();
      renderColumns();
      renderQuarantine();
    }})();
  </script>
</body>
</html>
"""


def is_valid_loopback_host(host_header: str) -> bool:
    """Strictly validates Host header hostname against DNS-rebinding prefix bypasses.

    Requires an explicit loopback hostname ('127.0.0.1', 'localhost', or '::1').
    """
    if not host_header or not host_header.strip():
        return False
    parsed = urllib.parse.urlsplit(f"//{host_header.strip()}")
    hostname = (parsed.hostname or "").lower()
    return hostname in {"127.0.0.1", "localhost", "::1"}


def create_http_handler(
    snapshot: Dict[str, Any], enable_access_requests: bool = False
) -> type[BaseHTTPRequestHandler]:
    """Creates a request handler class bound to the portal snapshot and security rules."""
    rendered_html_bytes = render_portal_html(snapshot).encode("utf-8")
    snapshot_bytes = json.dumps(snapshot, indent=2, sort_keys=True).encode("utf-8")

    class PortalHandler(BaseHTTPRequestHandler):
        def _validate_host(self) -> bool:
            host = self.headers.get("Host", "")
            if not is_valid_loopback_host(host):
                self.send_response(403)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"error": "Forbidden Host header"}')
                return False
            return True

        def do_GET(self) -> None:  # noqa: N802
            if not self._validate_host():
                return
            if self.path in ("/", "/index.html"):
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(rendered_html_bytes)))
                self.end_headers()
                self.wfile.write(rendered_html_bytes)
                return
            if self.path == "/api/snapshot":
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(snapshot_bytes)))
                self.end_headers()
                self.wfile.write(snapshot_bytes)
                return
            self.send_response(404)
            self.end_headers()

        def do_POST(self) -> None:  # noqa: N802
            if not self._validate_host():
                return
            if self.path == "/api/request-access":
                if not enable_access_requests:
                    self.send_response(403)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(
                        b'{"error": "Access request mutations disabled unless --enable-access-requests is set."}'
                    )
                    return
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(
                    b'{"status": "SIMULATED_OK", "message": "Access request recorded in dry-run handshake log."}'
                )
                return
            self.send_response(404)
            self.end_headers()

        def log_message(self, format: str, *args: Any) -> None:
            return

    return PortalHandler


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Export or serve the Business Data Contract & Quality Grade (A-E) Portal."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_exp = sub.add_parser("export", help="Export static HTML portal/index.html")
    p_exp.add_argument(
        "--out",
        default=str(REPO_ROOT / "portal" / "index.html"),
        help="Output HTML file path",
    )
    p_exp.add_argument(
        "--check",
        action="store_true",
        help="Verify that the exported HTML file matches current configs without writing",
    )
    p_exp.add_argument(
        "--live",
        action="store_true",
        help="Enrich snapshot with live Dataplex Catalog status",
    )
    p_exp.add_argument("--project-id", default=os.environ.get("PROJECT_ID", ""))

    p_srv = sub.add_parser("serve", help="Run local 127.0.0.1 HTTP portal server")
    p_srv.add_argument("--port", type=int, default=8765, help="Local TCP port")
    p_srv.add_argument(
        "--live",
        action="store_true",
        help="Enrich snapshot with live Dataplex Catalog status",
    )
    p_srv.add_argument("--project-id", default=os.environ.get("PROJECT_ID", ""))
    p_srv.add_argument(
        "--enable-access-requests",
        action="store_true",
        help="Enable POST /api/request-access endpoint",
    )

    args = parser.parse_args(argv)
    source = "live" if getattr(args, "live", False) else "offline"
    project_id = getattr(args, "project_id", "")
    snapshot = build_snapshot(source=source, project_id=project_id)

    if args.command == "export":
        rendered = render_portal_html(snapshot)
        out_path = Path(args.out)
        if args.check:
            if not out_path.exists():
                print(f"[DRIFT] Missing {out_path}", file=sys.stderr)
                return 1
            if out_path.read_text(encoding="utf-8") != rendered:
                print(
                    f"[DRIFT] {out_path} is out of sync with contract/catalog configs.",
                    file=sys.stderr,
                )
                return 1
            print(f"[OK] {out_path} is in sync.")
            return 0
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(rendered, encoding="utf-8")
        print(f"[OK] Exported Business Data Contract Portal to {out_path}")
        return 0

    if args.command == "serve":
        handler_cls = create_http_handler(
            snapshot=snapshot,
            enable_access_requests=bool(args.enable_access_requests),
        )
        server = ThreadingHTTPServer(("127.0.0.1", args.port), handler_cls)
        print(
            f"[PORTAL] Serving Business Data Contract & Quality Grade Portal at http://127.0.0.1:{args.port}"
        )
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            server.server_close()
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
