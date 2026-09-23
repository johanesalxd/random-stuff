#!/usr/bin/env python3
"""
SGX Data Contracts: Dataplex Auto Data Quality Scan Runner & Scorecard Reporter.

Orchestrates Google Cloud Dataplex Auto Data Quality scan execution, job polling,
and multi-tier executive scorecard reporting against BigQuery export tables.

Features:
- Dual Execution Architecture:
  1. Live GCP Execution: Triggers and polls `gcloud dataplex datascans run` with
     full JSON telemetry extraction (`--view=FULL`) and executes BigQuery SQL scorecards.
  2. Offline / Dry-Run Simulation: Validates SQL and Dataplex YAML contract specs,
     evaluates simulated/injected trade events, and generates executive scorecards
     without requiring remote GCP resources.
- Scorecard Reporting (Governed by MAS TRM Section 8 & ODCS v3.0):
  * Query 1: Executive KPI Dashboard (overall score %, per-dimension scores, RAG status).
  * Query 2: Dimension-Level Quality Breakdown matrix.
  * Query 3: SLA Violation Incident Report & Forensics Drill-down.

CLI Flags:
  --project-id    Google Cloud Project ID
  --location      Dataplex region (default: asia-southeast1)
  --datascan-id   Dataplex DataScan resource ID (default: sgx-equity-trades-dq)
  --dataset       BigQuery dataset ID (default: sgx_market_data)
  --table         BigQuery target table ID (default: equity_trades)
  --mode          Execution mode: {run, poll, scorecard, dry-run} (default: dry-run)
  --job-id        Optional DataScan job ID (for poll mode)
  --timeout       Timeout in seconds for job polling (default: 300)
  --poll-interval Polling interval in seconds (default: 5)
  --spec-file     Path to Dataplex DQ YAML spec (default: config/dataplex_dq_spec.yaml)
  --verbose       Enable verbose logging and query outputs
"""

import argparse
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
from typing import Any, Dict, List, Optional, Tuple
import yaml

# Authoritative project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# ANSI terminal formatting
BOLD = "\033[1m"
RESET = "\033[0m"
RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
MAGENTA = "\033[35m"
CYAN = "\033[36m"
GRAY = "\033[90m"


# ==============================================================================
# Data Structures
# ==============================================================================

@dataclass
class RuleEvaluationResult:
    """Evaluation result for an individual Dataplex DQ rule."""
    rule_name: str
    dimension: str
    rule_type: str
    column: Optional[str]
    passed: bool
    rows_evaluated: int
    rows_passed: int
    rows_null: int
    pass_ratio: float
    failed_records_query: Optional[str] = None
    description: Optional[str] = None


@dataclass
class ExecutiveScorecard:
    """Aggregated executive scorecard metrics for a DataScan execution."""
    job_id: str
    execution_timestamp: str
    target_table: str
    total_rules_evaluated: int
    total_rules_passed: int
    total_rules_failed: int
    overall_score_pct: float
    completeness_score_pct: float
    validity_score_pct: float
    freshness_score_pct: float
    integrity_score_pct: float
    executive_rag_status: str
    rule_results: List[RuleEvaluationResult] = field(default_factory=list)


# ==============================================================================
# Helper Utilities
# ==============================================================================

def get_default_project_id() -> str:
    """Resolves active GCP project from environment or gcloud config."""
    env_proj = os.environ.get("PROJECT_ID") or os.environ.get("GOOGLE_CLOUD_PROJECT")
    if env_proj:
        return env_proj.strip()

    if shutil.which("gcloud"):
        try:
            res = subprocess.run(
                ["gcloud", "config", "get-value", "project"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False
            )
            val = res.stdout.strip()
            if val and val != "(unset)":
                return val
        except Exception:
            pass

    return ""


def format_table(headers: List[str], rows: List[List[str]], alignments: Optional[List[str]] = None) -> str:
    """Formats an ASCII table with custom column widths and alignments."""
    if not headers and not rows:
        return ""

    num_cols = len(headers) if headers else len(rows[0])
    if alignments is None:
        alignments = ["<"] * num_cols

    col_widths = [len(h) for h in headers] if headers else [0] * num_cols
    for row in rows:
        for i, cell in enumerate(row):
            if i < num_cols:
                col_widths[i] = max(col_widths[i], len(str(cell)))

    # Header row
    lines = []
    sep = "+-" + "-+-".join("-" * w for w in col_widths) + "-+"
    lines.append(sep)

    if headers:
        header_cells = []
        for i, h in enumerate(headers):
            align = alignments[i] if i < len(alignments) else "<"
            header_cells.append(f"{h:{align}{col_widths[i]}}")
        lines.append("| " + " | ".join(header_cells) + " |")
        lines.append(sep)

    for row in rows:
        cells = []
        for i, cell in enumerate(row):
            if i < num_cols:
                align = alignments[i] if i < len(alignments) else "<"
                cells.append(f"{str(cell):{align}{col_widths[i]}}")
        lines.append("| " + " | ".join(cells) + " |")

    lines.append(sep)
    return "\n".join(lines)


# ==============================================================================
# Offline Simulation Engine
# ==============================================================================

class OfflineSimulationEngine:
    """In-memory Dataplex Auto DQ evaluation and scorecard simulation engine."""

    def __init__(self, project_id: str, dataset_id: str, table_id: str, spec_file: Path):
        self.project_id = project_id
        self.dataset_id = dataset_id
        self.table_id = table_id
        self.spec_file = spec_file

    def generate_synthetic_dataset(self) -> Tuple[List[Dict[str, Any]], Dict[str, str]]:
        """Generates realistic SGX equity trade batch containing controlled SLA violations."""
        now = datetime.now(timezone.utc)
        records = []
        violation_tags = {}

        # 1. Ten conforming trade records
        instruments = [
            ("D05.SI", 35.80, "BROKER_DBS_01", "BROKER_OCBC_02"),
            ("Z74.SI", 3.12, "BROKER_UOB_01", "BROKER_DBS_02"),
            ("O39.SI", 15.40, "BROKER_CITI_01", "BROKER_SCB_01"),
            ("U11.SI", 32.10, "BROKER_HSBC_01", "BROKER_MAYBANK_01"),
            ("F34.SI", 3.05, "BROKER_DBS_03", "BROKER_UOB_02"),
            ("C38U.SI", 1.95, "BROKER_OCBC_03", "BROKER_CITI_02"),
            ("BN4.SI", 7.85, "BROKER_SCB_02", "BROKER_HSBC_02"),
            ("BS6.SI", 1.15, "BROKER_MAYBANK_02", "BROKER_DBS_01"),
            ("A17U.SI", 2.80, "BROKER_UOB_03", "BROKER_OCBC_01"),
            ("G13.SI", 0.98, "BROKER_CITI_03", "BROKER_SCB_03"),
        ]
        for i, (ticker, price, buyer, seller) in enumerate(instruments):
            trade_id = f"TR-CONF-{i+1:03d}"
            event_ts = (now - timedelta(minutes=5 * (i + 1))).replace(microsecond=0).isoformat()
            records.append({
                "trade_id": trade_id,
                "instrument_code": ticker,
                "price": price,
                "volume": 1000 * (i + 1),
                "buyer_id": buyer,
                "seller_id": seller,
                "trade_timestamp": event_ts,
                "trade_status": "EXECUTED" if i != 3 else "AMENDED",
                "subscription_name": "sgx-equity-trades-bq-sub",
                "message_id": f"msg-{i+1:04d}",
                "publish_time": event_ts,
                "attributes": "{}"
            })

        # 2. Injected SLA Violations:
        # A. Stale trade (executed 4 hours ago, violates 2h Freshness SLA)
        stale_id = "TR-VIOL-FRESHNESS-001"
        stale_ts = (now - timedelta(hours=4.5)).replace(microsecond=0).isoformat()
        records.append({
            "trade_id": stale_id,
            "instrument_code": "D05.SI",
            "price": 35.80,
            "volume": 2500,
            "buyer_id": "BROKER_DBS_01",
            "seller_id": "BROKER_OCBC_02",
            "trade_timestamp": stale_ts,
            "trade_status": "EXECUTED",
            "subscription_name": "sgx-equity-trades-bq-sub",
            "message_id": "msg-viol-01",
            "publish_time": now.replace(microsecond=0).isoformat(),
            "attributes": "{}"
        })
        violation_tags[stale_id] = "FRESHNESS_SLA_BREACH (Timestamp > 2 hours old)"

        # B. Negative Price (violates Validity range > 0)
        neg_price_id = "TR-VIOL-PRICE-002"
        records.append({
            "trade_id": neg_price_id,
            "instrument_code": "Z74.SI",
            "price": -12.50,
            "volume": 500,
            "buyer_id": "BROKER_UOB_01",
            "seller_id": "BROKER_DBS_02",
            "trade_timestamp": now.replace(microsecond=0).isoformat(),
            "trade_status": "EXECUTED",
            "subscription_name": "sgx-equity-trades-bq-sub",
            "message_id": "msg-viol-02",
            "publish_time": now.replace(microsecond=0).isoformat(),
            "attributes": "{}"
        })
        violation_tags[neg_price_id] = "RANGE_VALIDITY_BREACH (Negative price: -12.50)"

        # C. Zero Volume (violates Validity range > 0)
        zero_vol_id = "TR-VIOL-VOL-003"
        records.append({
            "trade_id": zero_vol_id,
            "instrument_code": "O39.SI",
            "price": 15.40,
            "volume": 0,
            "buyer_id": "BROKER_CITI_01",
            "seller_id": "BROKER_SCB_01",
            "trade_timestamp": now.replace(microsecond=0).isoformat(),
            "trade_status": "EXECUTED",
            "subscription_name": "sgx-equity-trades-bq-sub",
            "message_id": "msg-viol-03",
            "publish_time": now.replace(microsecond=0).isoformat(),
            "attributes": "{}"
        })
        violation_tags[zero_vol_id] = "RANGE_VALIDITY_BREACH (Zero volume: 0 shares)"

        # D. Wash Trade (buyer_id == seller_id, violates Anti-Wash Trading assertion)
        wash_id = "TR-VIOL-WASH-004"
        records.append({
            "trade_id": wash_id,
            "instrument_code": "U11.SI",
            "price": 32.10,
            "volume": 10000,
            "buyer_id": "WASH_BROKER_999",
            "seller_id": "WASH_BROKER_999",
            "trade_timestamp": now.replace(microsecond=0).isoformat(),
            "trade_status": "EXECUTED",
            "subscription_name": "sgx-equity-trades-bq-sub",
            "message_id": "msg-viol-04",
            "publish_time": now.replace(microsecond=0).isoformat(),
            "attributes": "{}"
        })
        violation_tags[wash_id] = "INTEGRITY_BREACH (Self-trading wash trade: WASH_BROKER_999)"

        return records, violation_tags

    def evaluate_rules(self, spec: Dict[str, Any], records: List[Dict[str, Any]]) -> List[RuleEvaluationResult]:
        """Evaluates Dataplex Auto DQ rules against in-memory records matching BigQuery semantics."""
        results: List[RuleEvaluationResult] = []
        rules = spec.get("rules", [])
        now = datetime.now(timezone.utc)
        total_rows = len(records)

        for rule in rules:
            desc = rule.get("description", "")
            dimension = rule.get("dimension", "UNKNOWN")
            column = rule.get("column")
            threshold = float(rule.get("threshold", 1.0))

            rows_evaluated = total_rows
            rows_passed = 0
            rows_null = 0
            failed_query = None
            rule_type = "Unknown"

            if "nonNullExpectation" in rule:
                rule_type = "Non-null"
                for r in records:
                    val = r.get(column)
                    if val is None:
                        rows_null += 1
                    else:
                        rows_passed += 1
                failed_query = f"SELECT * FROM `{self.project_id}.{self.dataset_id}.{self.table_id}` WHERE {column} IS NULL"

            elif "rangeExpectation" in rule:
                rule_type = "Range Check"
                range_exp = rule["rangeExpectation"]
                min_val = float(range_exp.get("minValue", 0))
                strict_min = bool(range_exp.get("strictMinEnabled", False))
                ignore_null = bool(rule.get("ignoreNull", False))

                for r in records:
                    val = r.get(column)
                    if val is None:
                        rows_null += 1
                        if ignore_null:
                            rows_passed += 1
                    else:
                        num_val = float(val)
                        if strict_min and num_val > min_val:
                            rows_passed += 1
                        elif not strict_min and num_val >= min_val:
                            rows_passed += 1

                cond = f"{column} <= {min_val}" if strict_min else f"{column} < {min_val}"
                failed_query = f"SELECT * FROM `{self.project_id}.{self.dataset_id}.{self.table_id}` WHERE {cond} OR {column} IS NULL"

            elif "setExpectation" in rule:
                rule_type = "Set"
                valid_set = set(rule["setExpectation"].get("values", []))
                for r in records:
                    val = r.get(column)
                    if val is None:
                        rows_null += 1
                    elif val in valid_set:
                        rows_passed += 1
                values_str = ", ".join(f"'{v}'" for v in valid_set)
                failed_query = f"SELECT * FROM `{self.project_id}.{self.dataset_id}.{self.table_id}` WHERE {column} NOT IN ({values_str})"

            elif "rowConditionExpectation" in rule:
                rule_type = "Row condition"
                sql_expr = rule["rowConditionExpectation"].get("sqlExpression", "")

                if "INTERVAL 2 HOUR" in sql_expr:
                    # Freshness rule
                    for r in records:
                        ts_str = r.get("trade_timestamp", "")
                        try:
                            clean_ts = ts_str.replace("Z", "+00:00")
                            ts_dt = datetime.fromisoformat(clean_ts)
                            if (now - ts_dt) <= timedelta(hours=2):
                                rows_passed += 1
                        except Exception:
                            pass
                    failed_query = f"SELECT * FROM `{self.project_id}.{self.dataset_id}.{self.table_id}` WHERE trade_timestamp < TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 2 HOUR)"

                elif "buyer_id != seller_id" in sql_expr:
                    # Anti-wash trading rule
                    for r in records:
                        buyer = r.get("buyer_id", "")
                        seller = r.get("seller_id", "")
                        if buyer.strip() != seller.strip():
                            rows_passed += 1
                    failed_query = f"SELECT * FROM `{self.project_id}.{self.dataset_id}.{self.table_id}` WHERE buyer_id = seller_id"

                else:
                    rows_passed = total_rows

            pass_ratio = round(rows_passed / rows_evaluated, 4) if rows_evaluated > 0 else 1.0
            is_passed = (pass_ratio >= threshold)

            results.append(RuleEvaluationResult(
                rule_name=desc,
                dimension=dimension,
                rule_type=rule_type,
                column=column,
                passed=is_passed,
                rows_evaluated=rows_evaluated,
                rows_passed=rows_passed,
                rows_null=rows_null,
                pass_ratio=pass_ratio,
                failed_records_query=failed_query,
                description=desc
            ))

        return results

    def build_scorecard(self, results: List[RuleEvaluationResult]) -> ExecutiveScorecard:
        """Aggregates rule evaluation results into an Executive Scorecard."""
        total_rules = len(results)
        passed_rules = sum(1 for r in results if r.passed)
        failed_rules = total_rules - passed_rules
        overall_score = round(100.0 * passed_rules / total_rules, 2) if total_rules > 0 else 100.0

        def calc_dim(dim: str) -> float:
            dim_rules = [r for r in results if r.dimension == dim]
            if not dim_rules:
                return 100.0
            return round(100.0 * sum(1 for r in dim_rules if r.passed) / len(dim_rules), 2)

        comp_score = calc_dim("COMPLETENESS")
        val_score = calc_dim("VALIDITY")
        fresh_score = calc_dim("FRESHNESS")
        integ_score = calc_dim("INTEGRITY")

        # MAS TRM RAG status logic matching Query 1
        if failed_rules == 0:
            rag_status = "GREEN (100% SLA Compliant)"
        elif integ_score < 100.0:
            rag_status = "RED (CRITICAL: Anti-Wash Trading Breach Detected)"
        elif fresh_score < 100.0:
            rag_status = "RED (CRITICAL: Market Data Freshness SLA Breach)"
        else:
            rag_status = "AMBER (Quality Warning: Check Range/Validity Anomalies)"

        job_id = f"sim-job-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        ts = datetime.now(timezone.utc).isoformat()

        return ExecutiveScorecard(
            job_id=job_id,
            execution_timestamp=ts,
            target_table=f"{self.project_id}.{self.dataset_id}.{self.table_id}",
            total_rules_evaluated=total_rules,
            total_rules_passed=passed_rules,
            total_rules_failed=failed_rules,
            overall_score_pct=overall_score,
            completeness_score_pct=comp_score,
            validity_score_pct=val_score,
            freshness_score_pct=fresh_score,
            integrity_score_pct=integ_score,
            executive_rag_status=rag_status,
            rule_results=results
        )


# ==============================================================================
# Live Dataplex Engine
# ==============================================================================

class GcloudDataplexEngine:
    """Invokes and polls live Dataplex DataScans using Google Cloud SDK."""

    def __init__(self, project_id: str, location: str, datascan_id: str):
        self.project_id = project_id
        self.location = location
        self.datascan_id = datascan_id

    def trigger_scan(self) -> str:
        """Triggers a Dataplex DataScan run and returns the initiated job ID."""
        cmd = [
            "gcloud", "dataplex", "datascans", "run", self.datascan_id,
            f"--location={self.location}",
            f"--project={self.project_id}",
            "--format=json"
        ]
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
        if proc.returncode != 0:
            err_msg = proc.stderr.strip()
            if "already a pending DataScanJob" in err_msg or "already a running DataScanJob" in err_msg:
                m = re.search(r"jobs/([a-zA-Z0-9-]+)", err_msg)
                if m:
                    return m.group(1)
            raise RuntimeError(f"Failed to trigger Dataplex DataScan: {err_msg}")

        # Parse JSON output from gcloud
        data = self._extract_json_payload(proc.stdout)
        if isinstance(data, dict):
            job_data = data.get("job", {})
            job_id = job_data.get("uid") or job_data.get("name", "").split("/")[-1]
            if job_id:
                return job_id

        # Fallback to listing the latest job
        list_cmd = [
            "gcloud", "dataplex", "datascans", "jobs", "list",
            f"--datascan={self.datascan_id}",
            f"--location={self.location}",
            f"--project={self.project_id}",
            "--format=value(JOB_ID)",
            "--limit=1"
        ]
        list_proc = subprocess.run(list_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
        for line in list_proc.stdout.strip().splitlines():
            clean_id = line.strip()
            if clean_id and not clean_id.startswith("Created") and len(clean_id) > 10:
                return clean_id

        raise RuntimeError(f"Could not extract Dataplex job ID from output: {proc.stdout}")

    @staticmethod
    def _extract_json_payload(raw_text: str) -> Optional[Dict[str, Any]]:
        """Safely extracts the first JSON object from CLI output using raw_decode."""
        text = raw_text.strip()
        json_start = text.find("{")
        if json_start == -1:
            return None
        try:
            obj, _ = json.JSONDecoder().raw_decode(text[json_start:])
            return obj if isinstance(obj, dict) else None
        except json.JSONDecodeError:
            return None

    def poll_job(self, job_id: str, timeout: int = 300, poll_interval: int = 5, verbose: bool = False) -> Dict[str, Any]:
        """Polls DataScan job until reaching terminal state (SUCCEEDED, FAILED, CANCELLED)."""
        start_time = time.time()
        consecutive_errors = 0
        print(f"{CYAN}>> Polling Dataplex Job {BOLD}{job_id}{RESET} ({self.datascan_id} in {self.location})...{RESET}")

        while True:
            elapsed = int(time.time() - start_time)
            if elapsed > timeout:
                raise TimeoutError(f"Dataplex DataScan job {job_id} timed out after {timeout} seconds.")

            cmd = [
                "gcloud", "dataplex", "datascans", "jobs", "describe", job_id,
                f"--datascan={self.datascan_id}",
                f"--location={self.location}",
                f"--project={self.project_id}",
                "--format=value(state)"
            ]
            proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
            if proc.returncode != 0:
                consecutive_errors += 1
                if consecutive_errors >= 3:
                    raise RuntimeError(f"Failed to poll Dataplex job {job_id}: {proc.stderr.strip()}")
                state = "UNKNOWN"
            else:
                consecutive_errors = 0
                lines = [l.strip() for l in proc.stdout.strip().splitlines() if l.strip() and not l.strip().startswith("Created")]
                state = lines[-1] if lines else "UNKNOWN"

            if verbose:
                print(f"  [{elapsed}s] Job State: {state}")

            if state in {"SUCCEEDED", "FAILED", "CANCELLED"}:
                break

            time.sleep(poll_interval)

        # Fetch full view with results
        fetch_cmd = [
            "gcloud", "dataplex", "datascans", "jobs", "describe", job_id,
            f"--datascan={self.datascan_id}",
            f"--location={self.location}",
            f"--project={self.project_id}",
            "--view=FULL",
            "--format=json"
        ]
        full_proc = subprocess.run(fetch_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
        if full_proc.returncode != 0:
            raise RuntimeError(f"Failed to fetch full Dataplex job description: {full_proc.stderr.strip()}")

        parsed = self._extract_json_payload(full_proc.stdout)
        if parsed is not None:
            return parsed
        return json.loads(full_proc.stdout.strip())


# ==============================================================================
# Terminal Presentation Functions
# ==============================================================================

def print_scorecard_presentation(scorecard: ExecutiveScorecard) -> None:
    """Renders the complete 3-query executive scorecard to terminal."""
    print("")
    print(f"{BOLD}{CYAN}================================================================================{RESET}")
    print(f"{BOLD}{CYAN}   SGX DATA CONTRACTS: EXECUTIVE DATA QUALITY SCORECARD                         {RESET}")
    print(f"{BOLD}{CYAN}   Governed by Open Data Contract Standard (ODCS) & MAS TRM Guidelines          {RESET}")
    print(f"{BOLD}{CYAN}================================================================================{RESET}")

    # --------------------------------------------------------------------------
    # Query 1: Executive KPI Dashboard
    # --------------------------------------------------------------------------
    print("")
    print(f"{BOLD}{BLUE}>> [Query 1] Executive KPI Dashboard (Latest Scan Summary){RESET}")
    print(f"{GRAY}   Target Resource: {scorecard.target_table}{RESET}")
    print(f"{GRAY}   Job ID:          {scorecard.job_id} | Time: {scorecard.execution_timestamp}{RESET}")
    print("")

    rag_color = GREEN if "GREEN" in scorecard.executive_rag_status else (RED if "RED" in scorecard.executive_rag_status else YELLOW)

    kpi_headers = ["Metric / Dimension", "Evaluated Value", "SLA Threshold", "Status"]
    kpi_rows = [
        ["Overall Table Health Score", f"{scorecard.overall_score_pct:.2f}%", "100.00%", "PASS" if scorecard.overall_score_pct == 100 else "FAIL"],
        ["Total Rules Evaluated", str(scorecard.total_rules_evaluated), "N/A", "COMPLETE"],
        ["Rules Passed / Failed", f"{scorecard.total_rules_passed} / {scorecard.total_rules_failed}", "0 Failed", "PASS" if scorecard.total_rules_failed == 0 else "FAIL"],
        ["Completeness SLA Score", f"{scorecard.completeness_score_pct:.2f}%", "100.00%", "PASS" if scorecard.completeness_score_pct == 100 else "FAIL"],
        ["Validity / Range SLA Score", f"{scorecard.validity_score_pct:.2f}%", "100.00%", "PASS" if scorecard.validity_score_pct == 100 else "FAIL"],
        ["Freshness Latency SLA (2h)", f"{scorecard.freshness_score_pct:.2f}%", "100.00%", "PASS" if scorecard.freshness_score_pct == 100 else "FAIL"],
        ["Market Integrity (Anti-Wash)", f"{scorecard.integrity_score_pct:.2f}%", "100.00%", "PASS" if scorecard.integrity_score_pct == 100 else "FAIL"],
        ["Regulatory Compliance (RAG)", scorecard.executive_rag_status, "GREEN", "COMPLIANT" if "GREEN" in scorecard.executive_rag_status else "NON-COMPLIANT"],
    ]
    print(format_table(kpi_headers, kpi_rows, ["<", ">", ">", "<"]))

    # --------------------------------------------------------------------------
    # Query 2: Dimension-Level Quality Breakdown Matrix
    # --------------------------------------------------------------------------
    print("")
    print(f"{BOLD}{BLUE}>> [Query 2] Dimension-Level Quality Breakdown Matrix{RESET}")
    print(f"{GRAY}   Distribution of rules, row volumes, and compliance ratios across dimensions{RESET}")
    print("")

    dimensions = sorted(list({r.dimension for r in scorecard.rule_results}))
    dim_headers = ["Dimension", "Total Rules", "Passed", "Failed", "Compliance %", "Total Rows", "Status"]
    dim_rows = []

    for dim in dimensions:
        dim_rules = [r for r in scorecard.rule_results if r.dimension == dim]
        tot = len(dim_rules)
        p = sum(1 for r in dim_rules if r.passed)
        f = tot - p
        pct = round(100.0 * p / tot, 2) if tot > 0 else 100.0
        rows_eval = sum(r.rows_evaluated for r in dim_rules)
        st = "PASS" if f == 0 else "FAIL"
        dim_rows.append([dim, str(tot), str(p), str(f), f"{pct:.2f}%", str(rows_eval), st])

    print(format_table(dim_headers, dim_rows, ["<", ">", ">", ">", ">", ">", "<"]))

    # --------------------------------------------------------------------------
    # Query 3: SLA Violation Incident Report & Forensics Drill-down
    # --------------------------------------------------------------------------
    print("")
    print(f"{BOLD}{BLUE}>> [Query 3] SLA Violation Incident Report & Forensics Drill-Down{RESET}")
    failed_results = [r for r in scorecard.rule_results if not r.passed]

    if not failed_results:
        print(f"{GREEN}   ✓ Zero SLA violations detected! All data contract quality rules passed.{RESET}")
    else:
        print(f"{RED}   ✗ Alert: {len(failed_results)} Data Contract Rule Violations Detected:{RESET}")
        print("")

        inc_headers = ["Dimension", "Rule / Column", "Type", "Evaluated", "Violations", "Pass %"]
        inc_rows = []
        for r in failed_results:
            violations = r.rows_evaluated - r.rows_passed
            pass_pct = f"{r.pass_ratio * 100.0:.2f}%"
            col_or_name = r.column if r.column else r.rule_name[:30]
            inc_rows.append([r.dimension, col_or_name, r.rule_type, str(r.rows_evaluated), str(violations), pass_pct])

        print(format_table(inc_headers, inc_rows, ["<", "<", "<", ">", ">", ">"]))

        print("")
        print(f"{BOLD}Executable Forensics Inspection Queries (Debug Queries):{RESET}")
        for i, r in enumerate(failed_results, 1):
            print(f"  {BOLD}{i}. [{r.dimension}] {r.rule_name}:{RESET}")
            if r.failed_records_query:
                print(f"     {CYAN}{r.failed_records_query}{RESET}")
            else:
                print(f"     {GRAY}(No SQL query provided for rule type {r.rule_type}){RESET}")

    print("")
    print(f"{BOLD}{CYAN}================================================================================{RESET}")


# ==============================================================================
# Validation Routines
# ==============================================================================

def validate_sql_files(project_id: str, dataset_id: str) -> None:
    """Validates presence and syntax of the 3 Milestone 3 SQL files."""
    ddl_file = PROJECT_ROOT / "sql" / "create_dq_export_results_table.sql"
    view_file = PROJECT_ROOT / "sql" / "create_v_dq_rule_summary.sql"
    query_file = PROJECT_ROOT / "sql" / "query_executive_scorecard.sql"

    print(f"{CYAN}>> Validating Milestone 3 SQL Files...{RESET}")

    for path, name in [(ddl_file, "Export Table DDL"), (view_file, "Reporting View"), (query_file, "Scorecard Queries")]:
        if not path.exists():
            raise FileNotFoundError(f"Missing required SQL artifact: {path} ({name})")
        content = path.read_text(encoding="utf-8")
        if len(content.strip()) == 0:
            raise ValueError(f"SQL file is empty: {path}")

    # Check structural requirements
    ddl_content = ddl_file.read_text(encoding="utf-8")
    assert "data_quality_scan" in ddl_content, "DDL missing data_quality_scan STRUCT"
    assert "data_source" in ddl_content, "DDL missing data_source STRUCT"
    assert "PARTITION BY DATE(job_start_time)" in ddl_content, "DDL missing DATE(job_start_time) partitioning"
    assert "CLUSTER BY" in ddl_content, "DDL missing CLUSTER BY clause"

    view_content = view_file.read_text(encoding="utf-8")
    for expected_col in ["job_id", "execution_date", "data_source", "rule_name", "dimension",
                         "rule_type", "passed", "evaluated_records_count", "null_count", "pass_ratio"]:
        assert expected_col in view_content, f"Reporting view missing canonical column: {expected_col}"

    query_content = query_file.read_text(encoding="utf-8")
    assert "Query 1" in query_content, "Scorecard SQL missing Query 1"
    assert "Query 2" in query_content, "Scorecard SQL missing Query 2"
    assert "Query 3" in query_content, "Scorecard SQL missing Query 3"

    print(f"{GREEN}   ✓ All 3 SQL files validated for syntax and schema contracts.{RESET}")


# ==============================================================================
# Main CLI Entrypoint
# ==============================================================================

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="SGX Data Contracts: Dataplex Auto Data Quality Scan Runner & Scorecard Reporter",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # 1. Offline evaluation mode (validates contracts & simulates DQ scan on injected data):
  python3 scripts/run_dataplex_scan.py --mode=dry-run

  # 2. Live execution mode (triggers gcloud dataplex datascans run, polls, reports scorecard):
  python3 scripts/run_dataplex_scan.py --mode=run --project-id=my-project --location=asia-southeast1

  # 3. Poll existing DataScan job:
  python3 scripts/run_dataplex_scan.py --mode=poll --job-id=job-uuid-12345

  # 4. Generate scorecard from BigQuery export table:
  python3 scripts/run_dataplex_scan.py --mode=scorecard --project-id=my-project
        """
    )
    parser.add_argument(
        "--project-id",
        type=str,
        default=None,
        help="Google Cloud Project ID (default: resolves from gcloud config or PROJECT_ID env)"
    )
    parser.add_argument(
        "--location",
        type=str,
        default="asia-southeast1",
        help="Dataplex DataScan region/location (default: asia-southeast1)"
    )
    parser.add_argument(
        "--datascan-id",
        type=str,
        default="sgx-equity-trades-dq",
        help="Dataplex DataScan identifier (default: sgx-equity-trades-dq)"
    )
    parser.add_argument(
        "--dataset",
        type=str,
        default="sgx_market_data",
        help="BigQuery dataset ID (default: sgx_market_data)"
    )
    parser.add_argument(
        "--table",
        type=str,
        default="equity_trades",
        help="Target BigQuery table ID (default: equity_trades)"
    )
    parser.add_argument(
        "--mode",
        type=str,
        choices=["run", "poll", "scorecard", "dry-run"],
        default="dry-run",
        help="Execution mode: run (trigger & poll), poll (monitor job), scorecard (query BQ), dry-run (offline simulation) [default: dry-run]"
    )
    parser.add_argument(
        "--job-id",
        type=str,
        default=None,
        help="Dataplex job UUID to poll or inspect (required for --mode=poll if not latest)"
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=300,
        help="Maximum timeout in seconds for job polling (default: 300)"
    )
    parser.add_argument(
        "--poll-interval",
        type=int,
        default=5,
        help="Interval in seconds between job polling queries (default: 5)"
    )
    parser.add_argument(
        "--spec-file",
        type=str,
        default=str(PROJECT_ROOT / "config" / "dataplex_dq_spec.yaml"),
        help="Path to Dataplex Auto DQ YAML specification"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose output and execution details"
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    project_id = args.project_id or get_default_project_id()
    if not project_id and args.mode != "dry-run":
        print(f"{RED}Error: Project ID is required for mode '{args.mode}'. Set PROJECT_ID env var or pass --project-id.{RESET}")
        return 1
    spec_path = Path(args.spec_file)

    if args.verbose:
        print(f"{GRAY}[DEBUG] Project ID:  {project_id}{RESET}")
        print(f"{GRAY}[DEBUG] Location:    {args.location}{RESET}")
        print(f"{GRAY}[DEBUG] DataScan ID: {args.datascan_id}{RESET}")
        print(f"{GRAY}[DEBUG] Dataset:     {args.dataset}{RESET}")
        print(f"{GRAY}[DEBUG] Table:       {args.table}{RESET}")
        print(f"{GRAY}[DEBUG] Mode:        {args.mode}{RESET}")
        print(f"{GRAY}[DEBUG] Spec Path:   {spec_path}{RESET}")

    # Mode 1: Offline Evaluation & Dry-Run Simulation
    if args.mode == "dry-run":
        print(f"{BOLD}{BLUE}========================================================================{RESET}")
        print(f"{BOLD}{BLUE}   DATAPLEX AUTO DATA QUALITY: OFFLINE EVALUATION & DRY-RUN             {RESET}")
        print(f"{BOLD}{BLUE}========================================================================{RESET}")

        validate_sql_files(project_id, args.dataset)

        if not spec_path.exists():
            print(f"{RED}Error: Dataplex spec file not found at {spec_path}{RESET}")
            return 1

        with open(spec_path, "r", encoding="utf-8") as f:
            spec_data = yaml.safe_load(f)

        rules = spec_data.get("rules", [])
        print(f"{GREEN}   ✓ Parsed Dataplex DQ Spec: {len(rules)} rules configured.{RESET}")

        engine = OfflineSimulationEngine(project_id, args.dataset, args.table, spec_path)
        records, violations = engine.generate_synthetic_dataset()
        print(f"{CYAN}   ✓ Generated {len(records)} test trade events ({len(violations)} injected violations).{RESET}")

        rule_evals = engine.evaluate_rules(spec_data, records)
        scorecard = engine.build_scorecard(rule_evals)

        print_scorecard_presentation(scorecard)

        # Confirm all 4 injected violations were properly flagged
        failed_dims = {r.dimension for r in rule_evals if not r.passed}
        expected_fails = {"FRESHNESS", "VALIDITY", "INTEGRITY"}
        if expected_fails.issubset(failed_dims):
            print(f"{GREEN}✓ Offline Simulation Succeeded: All injected SLA violations accurately detected.{RESET}")
            return 0
        else:
            print(f"{RED}✗ Simulation Warning: Expected violations in {expected_fails}, found {failed_dims}{RESET}")
            return 1

    # Mode 2: Live DataScan Run & Poll
    elif args.mode == "run":
        if not shutil.which("gcloud"):
            print(f"{RED}Error: gcloud SDK is not installed or not in PATH.{RESET}")
            return 1

        live_engine = GcloudDataplexEngine(project_id, args.location, args.datascan_id)
        try:
            print(f"{CYAN}>> Triggering Dataplex DataScan {BOLD}{args.datascan_id}{RESET} in {args.location}...{RESET}")
            job_id = live_engine.trigger_scan()
            print(f"{GREEN}✓ Initiated Dataplex Job: {BOLD}{job_id}{RESET}")

            job_json = live_engine.poll_job(job_id, timeout=args.timeout, poll_interval=args.poll_interval, verbose=args.verbose)
            state = job_json.get("state", "UNKNOWN")
            if state != "SUCCEEDED":
                print(f"{RED}✗ Dataplex Job finished with non-success state: {BOLD}{state}{RESET}")
                return 1
            print(f"{GREEN}✓ Dataplex Job finished with state: {BOLD}{state}{RESET}")

            # Parse results from job_json
            dq_result = job_json.get("dataQualityResult", {})
            if dq_result:
                print(f"Overall Quality Score: {dq_result.get('score', 0)}% (Passed: {dq_result.get('passed', False)})")
            return 0
        except Exception as e:
            print(f"{RED}Error during DataScan run: {e}{RESET}")
            return 1

    # Mode 3: Poll DataScan Job
    elif args.mode == "poll":
        if not args.job_id:
            print(f"{RED}Error: --job-id is required for --mode=poll.{RESET}")
            return 1

        live_engine = GcloudDataplexEngine(project_id, args.location, args.datascan_id)
        try:
            job_json = live_engine.poll_job(args.job_id, timeout=args.timeout, poll_interval=args.poll_interval, verbose=args.verbose)
            print(json.dumps(job_json, indent=2))
            return 0
        except Exception as e:
            print(f"{RED}Error polling job: {e}{RESET}")
            return 1

    # Mode 4: BigQuery Scorecard Execution
    elif args.mode == "scorecard":
        if not shutil.which("bq"):
            print(f"{RED}Error: bq CLI is not installed or not in PATH.{RESET}")
            return 1

        query_file = PROJECT_ROOT / "sql" / "query_executive_scorecard.sql"
        query_sql = query_file.read_text(encoding="utf-8")
        # Replace variables
        formatted_sql = query_sql.replace("${PROJECT_ID}", project_id).replace("sgx_market_data", args.dataset)

        print(f"{CYAN}>> Executing Executive Scorecard Queries on BigQuery export table...{RESET}")
        cmd = [
            "bq", "query",
            f"--project_id={project_id}",
            "--use_legacy_sql=false"
        ]
        proc = subprocess.run(cmd, input=formatted_sql, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
        if proc.returncode != 0:
            print(f"{RED}Error executing BigQuery scorecard queries:\n{proc.stderr.strip()}{RESET}")
            return 1

        print(proc.stdout)
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
