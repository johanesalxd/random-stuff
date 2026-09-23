"""Adversarial Test Suite for Milestone 3 Data Quality Artifacts.

Challenge Dimension: Executive scorecard queries and v_dq_rule_summary view
under extreme data conditions:
- ADV-M3-1: 100% GREEN (All 9 rules pass, verifying RAG status and 100.0% scores).
- ADV-M3-2: RED - Anti-Wash Trading Breach (INTEGRITY breach triggering critical RAG).
- ADV-M3-3: RED - Freshness SLA Breach (FRESHNESS breach triggering critical RAG).
- ADV-M3-4: AMBER - Validity/Range breach only (price/volume failure triggering AMBER).
- ADV-M3-5: Empty Table Edge Case (dq_export_results has 0 rows - catches division by zero).
- ADV-M3-6: Precision Preservation of pass_ratio in v_dq_rule_summary (4-decimal rounding, basis points, extreme scales).
- ADV-M3-7: Offline Simulation Engine extreme input behavior.
"""

import json
import os
from pathlib import Path
import shutil
import subprocess
import unittest

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def resolve_test_project_id() -> str:
    env_proj = os.environ.get("PROJECT_ID") or os.environ.get("GOOGLE_CLOUD_PROJECT")
    if env_proj:
        return env_proj.strip()
    if shutil.which("gcloud"):
        try:
            res = subprocess.run(["gcloud", "config", "get-value", "project"], capture_output=True, text=True)
            val = res.stdout.strip()
            if val and val != "(unset)":
                return val
        except Exception:
            pass
    return ""


def run_bq_query(query_str: str) -> list[dict]:
    """Runs a standard SQL query via bq CLI and returns JSON output."""
    if not shutil.which("bq"):
        raise unittest.SkipTest("bq CLI not available for live BigQuery evaluation")
    project_id = resolve_test_project_id()
    if not project_id:
        raise unittest.SkipTest("No active GCP project configured for live BigQuery evaluation")
    cmd = [
        "bq", "query",
        f"--project_id={project_id}",
        "--use_legacy_sql=false",
        "--format=prettyjson",
        query_str
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"BigQuery query failed (code {proc.returncode}):\n{proc.stderr}")
    try:
        return json.loads(proc.stdout)
    except Exception:
        return []


class TestMilestone3ScorecardAdversarial(unittest.TestCase):
    """Adversarial verification of executive scorecard queries under extreme conditions."""

    def test_adv_m3_1_all_rules_pass_100_percent_green(self):
        """Tests that all 3 scorecard queries produce 100% GREEN compliance when all rules pass."""
        sql = """
        WITH dq_export_results AS (
          SELECT
            'job-test-green-001' AS data_quality_job_id,
            TIMESTAMP '2026-09-14 02:00:00 UTC' AS job_start_time,
            STRUCT('equity_trades' AS table_id) AS data_source,
            dim AS rule_dimension,
            rname AS rule_name,
            'Row condition' AS rule_type,
            col AS rule_column,
            TRUE AS rule_passed,
            100 AS rule_rows_evaluated,
            100 AS job_rows_scanned,
            100 AS rule_rows_passed,
            100.0 AS rule_rows_passed_percent,
            CAST(NULL AS STRING) AS rule_failed_records_query
          FROM UNNEST([
            STRUCT('COMPLETENESS' AS dim, 'Non-null trade_id' AS rname, 'trade_id' AS col),
            STRUCT('COMPLETENESS', 'Non-null instrument_code', 'instrument_code'),
            STRUCT('COMPLETENESS', 'Non-null price', 'price'),
            STRUCT('COMPLETENESS', 'Non-null volume', 'volume'),
            STRUCT('VALIDITY', 'Price strictly positive', 'price'),
            STRUCT('VALIDITY', 'Volume strictly positive', 'volume'),
            STRUCT('VALIDITY', 'Valid trade_status enum', 'trade_status'),
            STRUCT('FRESHNESS', 'Freshness within 2 hours', 'trade_timestamp'),
            STRUCT('INTEGRITY', 'Anti-wash trading rule', 'buyer_id')
          ])
        ),
        latest_scan AS (
          SELECT data_quality_job_id
          FROM dq_export_results
          ORDER BY job_start_time DESC
          LIMIT 1
        ),
        rule_evals AS (
          SELECT
            r.data_quality_job_id,
            r.job_start_time,
            COALESCE(r.data_source.table_id, 'equity_trades') AS table_name,
            r.rule_dimension,
            r.rule_name,
            r.rule_passed,
            COALESCE(r.rule_rows_evaluated, r.job_rows_scanned, 0) AS rows_evaluated,
            COALESCE(r.rule_rows_passed, IF(r.rule_passed, r.rule_rows_evaluated, 0)) AS rows_passed
          FROM dq_export_results r
          JOIN latest_scan ls ON r.data_quality_job_id = ls.data_quality_job_id
        )
        SELECT
          MAX(data_quality_job_id) AS job_id,
          COUNT(*) AS total_rules_evaluated,
          COUNTIF(rule_passed) AS total_rules_passed,
          COUNTIF(NOT rule_passed) AS total_rules_failed,
          ROUND(100.0 * COUNTIF(rule_passed) / COUNT(*), 2) AS overall_score_pct,
          ROUND(100.0 * COUNTIF(rule_dimension = 'COMPLETENESS' AND rule_passed) / NULLIF(COUNTIF(rule_dimension = 'COMPLETENESS'), 0), 2) AS completeness_score_pct,
          ROUND(100.0 * COUNTIF(rule_dimension = 'VALIDITY' AND rule_passed) / NULLIF(COUNTIF(rule_dimension = 'VALIDITY'), 0), 2) AS validity_score_pct,
          ROUND(100.0 * COUNTIF(rule_dimension = 'FRESHNESS' AND rule_passed) / NULLIF(COUNTIF(rule_dimension = 'FRESHNESS'), 0), 2) AS freshness_score_pct,
          ROUND(100.0 * COUNTIF(rule_dimension = 'INTEGRITY' AND rule_passed) / NULLIF(COUNTIF(rule_dimension = 'INTEGRITY'), 0), 2) AS integrity_score_pct,
          CASE
            WHEN COUNTIF(NOT rule_passed) = 0 THEN 'GREEN (100% SLA Compliant)'
            WHEN COUNTIF(rule_dimension = 'INTEGRITY' AND NOT rule_passed) > 0 THEN 'RED (CRITICAL: Anti-Wash Trading Breach)'
            WHEN COUNTIF(rule_dimension = 'FRESHNESS' AND NOT rule_passed) > 0 THEN 'RED (CRITICAL: Market Data Freshness SLA Breach)'
            ELSE 'AMBER (Quality Warning: Check Range/Validity)'
          END AS executive_rag_status
        FROM rule_evals;
        """
        rows = run_bq_query(sql)
        self.assertEqual(len(rows), 1)
        kpi = rows[0]
        self.assertEqual(kpi["total_rules_evaluated"], "9")
        self.assertEqual(kpi["total_rules_passed"], "9")
        self.assertEqual(kpi["total_rules_failed"], "0")
        self.assertEqual(float(kpi["overall_score_pct"]), 100.0)
        self.assertEqual(float(kpi["completeness_score_pct"]), 100.0)
        self.assertEqual(float(kpi["validity_score_pct"]), 100.0)
        self.assertEqual(float(kpi["freshness_score_pct"]), 100.0)
        self.assertEqual(float(kpi["integrity_score_pct"]), 100.0)
        self.assertEqual(kpi["executive_rag_status"], "GREEN (100% SLA Compliant)")

    def test_adv_m3_2_anti_wash_trading_breach_triggers_red(self):
        """Tests that anti-wash trading failure triggers critical RED status."""
        sql = """
        WITH dq_export_results AS (
          SELECT
            'job-test-wash-002' AS data_quality_job_id,
            TIMESTAMP '2026-09-14 02:00:00 UTC' AS job_start_time,
            STRUCT('equity_trades' AS table_id) AS data_source,
            dim AS rule_dimension,
            rname AS rule_name,
            'Row condition' AS rule_type,
            col AS rule_column,
            passed AS rule_passed,
            100 AS rule_rows_evaluated,
            100 AS job_rows_scanned,
            passed_rows AS rule_rows_passed,
            pass_pct AS rule_rows_passed_percent,
            fail_query AS rule_failed_records_query
          FROM UNNEST([
            STRUCT('COMPLETENESS' AS dim, 'Non-null trade_id' AS rname, 'trade_id' AS col, TRUE AS passed, 100 AS passed_rows, 100.0 AS pass_pct, CAST(NULL AS STRING) AS fail_query),
            STRUCT('COMPLETENESS', 'Non-null instrument_code', 'instrument_code', TRUE, 100, 100.0, NULL),
            STRUCT('COMPLETENESS', 'Non-null price', 'price', TRUE, 100, 100.0, NULL),
            STRUCT('COMPLETENESS', 'Non-null volume', 'volume', TRUE, 100, 100.0, NULL),
            STRUCT('VALIDITY', 'Price strictly positive', 'price', TRUE, 100, 100.0, NULL),
            STRUCT('VALIDITY', 'Volume strictly positive', 'volume', TRUE, 100, 100.0, NULL),
            STRUCT('VALIDITY', 'Valid trade_status enum', 'trade_status', TRUE, 100, 100.0, NULL),
            STRUCT('FRESHNESS', 'Freshness within 2 hours', 'trade_timestamp', TRUE, 100, 100.0, NULL),
            STRUCT('INTEGRITY', 'Anti-wash trading rule', 'buyer_id', FALSE, 98, 98.0, 'SELECT * FROM equity_trades WHERE buyer_id = seller_id')
          ])
        ),
        latest_scan AS (
          SELECT data_quality_job_id
          FROM dq_export_results
          ORDER BY job_start_time DESC
          LIMIT 1
        ),
        rule_evals AS (
          SELECT
            r.data_quality_job_id,
            r.job_start_time,
            COALESCE(r.data_source.table_id, 'equity_trades') AS table_name,
            r.rule_dimension,
            r.rule_name,
            r.rule_passed,
            COALESCE(r.rule_rows_evaluated, r.job_rows_scanned, 0) AS rows_evaluated,
            COALESCE(r.rule_rows_passed, IF(r.rule_passed, r.rule_rows_evaluated, 0)) AS rows_passed
          FROM dq_export_results r
          JOIN latest_scan ls ON r.data_quality_job_id = ls.data_quality_job_id
        )
        SELECT
          COUNTIF(rule_passed) AS total_rules_passed,
          COUNTIF(NOT rule_passed) AS total_rules_failed,
          ROUND(100.0 * COUNTIF(rule_dimension = 'INTEGRITY' AND rule_passed) / NULLIF(COUNTIF(rule_dimension = 'INTEGRITY'), 0), 2) AS integrity_score_pct,
          CASE
            WHEN COUNTIF(NOT rule_passed) = 0 THEN 'GREEN (100% SLA Compliant)'
            WHEN COUNTIF(rule_dimension = 'INTEGRITY' AND NOT rule_passed) > 0 THEN 'RED (CRITICAL: Anti-Wash Trading Breach)'
            WHEN COUNTIF(rule_dimension = 'FRESHNESS' AND NOT rule_passed) > 0 THEN 'RED (CRITICAL: Market Data Freshness SLA Breach)'
            ELSE 'AMBER (Quality Warning: Check Range/Validity)'
          END AS executive_rag_status
        FROM rule_evals;
        """
        rows = run_bq_query(sql)
        self.assertEqual(len(rows), 1)
        res = rows[0]
        self.assertEqual(res["total_rules_failed"], "1")
        self.assertEqual(float(res["integrity_score_pct"]), 0.0)
        self.assertEqual(res["executive_rag_status"], "RED (CRITICAL: Anti-Wash Trading Breach)")

    def test_adv_m3_3_freshness_sla_breach_triggers_red(self):
        """Tests that freshness failure triggers critical RED status."""
        sql = """
        WITH dq_export_results AS (
          SELECT
            'job-test-fresh-003' AS data_quality_job_id,
            TIMESTAMP '2026-09-14 02:00:00 UTC' AS job_start_time,
            STRUCT('equity_trades' AS table_id) AS data_source,
            dim AS rule_dimension,
            rname AS rule_name,
            'Row condition' AS rule_type,
            col AS rule_column,
            passed AS rule_passed,
            100 AS rule_rows_evaluated,
            100 AS job_rows_scanned,
            passed_rows AS rule_rows_passed,
            pass_pct AS rule_rows_passed_percent,
            fail_query AS rule_failed_records_query
          FROM UNNEST([
            STRUCT('COMPLETENESS' AS dim, 'Non-null trade_id' AS rname, 'trade_id' AS col, TRUE AS passed, 100 AS passed_rows, 100.0 AS pass_pct, CAST(NULL AS STRING) AS fail_query),
            STRUCT('COMPLETENESS', 'Non-null instrument_code', 'instrument_code', TRUE, 100, 100.0, NULL),
            STRUCT('COMPLETENESS', 'Non-null price', 'price', TRUE, 100, 100.0, NULL),
            STRUCT('COMPLETENESS', 'Non-null volume', 'volume', TRUE, 100, 100.0, NULL),
            STRUCT('VALIDITY', 'Price strictly positive', 'price', TRUE, 100, 100.0, NULL),
            STRUCT('VALIDITY', 'Volume strictly positive', 'volume', TRUE, 100, 100.0, NULL),
            STRUCT('VALIDITY', 'Valid trade_status enum', 'trade_status', TRUE, 100, 100.0, NULL),
            STRUCT('FRESHNESS', 'Freshness within 2 hours', 'trade_timestamp', FALSE, 90, 90.0, 'SELECT * FROM equity_trades WHERE trade_timestamp < TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 2 HOUR)'),
            STRUCT('INTEGRITY', 'Anti-wash trading rule', 'buyer_id', TRUE, 100, 100.0, NULL)
          ])
        ),
        latest_scan AS (
          SELECT data_quality_job_id
          FROM dq_export_results
          ORDER BY job_start_time DESC
          LIMIT 1
        ),
        rule_evals AS (
          SELECT
            r.data_quality_job_id,
            r.job_start_time,
            COALESCE(r.data_source.table_id, 'equity_trades') AS table_name,
            r.rule_dimension,
            r.rule_name,
            r.rule_passed,
            COALESCE(r.rule_rows_evaluated, r.job_rows_scanned, 0) AS rows_evaluated,
            COALESCE(r.rule_rows_passed, IF(r.rule_passed, r.rule_rows_evaluated, 0)) AS rows_passed
          FROM dq_export_results r
          JOIN latest_scan ls ON r.data_quality_job_id = ls.data_quality_job_id
        )
        SELECT
          COUNTIF(rule_passed) AS total_rules_passed,
          COUNTIF(NOT rule_passed) AS total_rules_failed,
          ROUND(100.0 * COUNTIF(rule_dimension = 'FRESHNESS' AND rule_passed) / NULLIF(COUNTIF(rule_dimension = 'FRESHNESS'), 0), 2) AS freshness_score_pct,
          CASE
            WHEN COUNTIF(NOT rule_passed) = 0 THEN 'GREEN (100% SLA Compliant)'
            WHEN COUNTIF(rule_dimension = 'INTEGRITY' AND NOT rule_passed) > 0 THEN 'RED (CRITICAL: Anti-Wash Trading Breach)'
            WHEN COUNTIF(rule_dimension = 'FRESHNESS' AND NOT rule_passed) > 0 THEN 'RED (CRITICAL: Market Data Freshness SLA Breach)'
            ELSE 'AMBER (Quality Warning: Check Range/Validity)'
          END AS executive_rag_status
        FROM rule_evals;
        """
        rows = run_bq_query(sql)
        self.assertEqual(len(rows), 1)
        res = rows[0]
        self.assertEqual(res["total_rules_failed"], "1")
        self.assertEqual(float(res["freshness_score_pct"]), 0.0)
        self.assertEqual(res["executive_rag_status"], "RED (CRITICAL: Market Data Freshness SLA Breach)")

    def test_adv_m3_4_validity_only_breach_triggers_amber(self):
        """Tests that failure only in validity/range checks triggers AMBER status."""
        sql = """
        WITH dq_export_results AS (
          SELECT
            'job-test-amber-004' AS data_quality_job_id,
            TIMESTAMP '2026-09-14 02:00:00 UTC' AS job_start_time,
            STRUCT('equity_trades' AS table_id) AS data_source,
            dim AS rule_dimension,
            rname AS rule_name,
            'Row condition' AS rule_type,
            col AS rule_column,
            passed AS rule_passed,
            100 AS rule_rows_evaluated,
            100 AS job_rows_scanned,
            passed_rows AS rule_rows_passed,
            pass_pct AS rule_rows_passed_percent,
            fail_query AS rule_failed_records_query
          FROM UNNEST([
            STRUCT('COMPLETENESS' AS dim, 'Non-null trade_id' AS rname, 'trade_id' AS col, TRUE AS passed, 100 AS passed_rows, 100.0 AS pass_pct, CAST(NULL AS STRING) AS fail_query),
            STRUCT('COMPLETENESS', 'Non-null instrument_code', 'instrument_code', TRUE, 100, 100.0, NULL),
            STRUCT('COMPLETENESS', 'Non-null price', 'price', TRUE, 100, 100.0, NULL),
            STRUCT('COMPLETENESS', 'Non-null volume', 'volume', TRUE, 100, 100.0, NULL),
            STRUCT('VALIDITY', 'Price strictly positive', 'price', FALSE, 95, 95.0, 'SELECT * FROM equity_trades WHERE price <= 0.0 OR price IS NULL'),
            STRUCT('VALIDITY', 'Volume strictly positive', 'volume', TRUE, 100, 100.0, NULL),
            STRUCT('VALIDITY', 'Valid trade_status enum', 'trade_status', TRUE, 100, 100.0, NULL),
            STRUCT('FRESHNESS', 'Freshness within 2 hours', 'trade_timestamp', TRUE, 100, 100.0, NULL),
            STRUCT('INTEGRITY', 'Anti-wash trading rule', 'buyer_id', TRUE, 100, 100.0, NULL)
          ])
        ),
        latest_scan AS (
          SELECT data_quality_job_id
          FROM dq_export_results
          ORDER BY job_start_time DESC
          LIMIT 1
        ),
        rule_evals AS (
          SELECT
            r.data_quality_job_id,
            r.job_start_time,
            COALESCE(r.data_source.table_id, 'equity_trades') AS table_name,
            r.rule_dimension,
            r.rule_name,
            r.rule_passed,
            COALESCE(r.rule_rows_evaluated, r.job_rows_scanned, 0) AS rows_evaluated,
            COALESCE(r.rule_rows_passed, IF(r.rule_passed, r.rule_rows_evaluated, 0)) AS rows_passed
          FROM dq_export_results r
          JOIN latest_scan ls ON r.data_quality_job_id = ls.data_quality_job_id
        )
        SELECT
          COUNTIF(rule_passed) AS total_rules_passed,
          COUNTIF(NOT rule_passed) AS total_rules_failed,
          ROUND(100.0 * COUNTIF(rule_dimension = 'VALIDITY' AND rule_passed) / NULLIF(COUNTIF(rule_dimension = 'VALIDITY'), 0), 2) AS validity_score_pct,
          CASE
            WHEN COUNTIF(NOT rule_passed) = 0 THEN 'GREEN (100% SLA Compliant)'
            WHEN COUNTIF(rule_dimension = 'INTEGRITY' AND NOT rule_passed) > 0 THEN 'RED (CRITICAL: Anti-Wash Trading Breach)'
            WHEN COUNTIF(rule_dimension = 'FRESHNESS' AND NOT rule_passed) > 0 THEN 'RED (CRITICAL: Market Data Freshness SLA Breach)'
            ELSE 'AMBER (Quality Warning: Check Range/Validity)'
          END AS executive_rag_status
        FROM rule_evals;
        """
        rows = run_bq_query(sql)
        self.assertEqual(len(rows), 1)
        res = rows[0]
        self.assertEqual(res["total_rules_failed"], "1")
        self.assertEqual(float(res["validity_score_pct"]), 66.67)
        self.assertEqual(res["executive_rag_status"], "AMBER (Quality Warning: Check Range/Validity)")

    def test_adv_m3_5_empty_table_edge_case_reveals_division_by_zero(self):
        """CHALLENGE: Demonstrates that Query 1 fails with 'division by zero: 0 / 0' on empty dq_export_results."""
        sql_empty = """
        WITH dq_export_results AS (
          SELECT
            CAST(NULL AS STRING) AS data_quality_job_id,
            CAST(NULL AS TIMESTAMP) AS job_start_time,
            STRUCT(CAST(NULL AS STRING) AS table_id) AS data_source,
            CAST(NULL AS STRING) AS rule_dimension,
            CAST(NULL AS STRING) AS rule_name,
            CAST(NULL AS BOOLEAN) AS rule_passed,
            CAST(NULL AS INT64) AS rule_rows_evaluated,
            CAST(NULL AS INT64) AS job_rows_scanned,
            CAST(NULL AS INT64) AS rule_rows_passed
          LIMIT 0
        ),
        latest_scan AS (
          SELECT data_quality_job_id
          FROM dq_export_results
          ORDER BY job_start_time DESC
          LIMIT 1
        ),
        rule_evals AS (
          SELECT
            r.data_quality_job_id,
            r.job_start_time,
            COALESCE(r.data_source.table_id, 'equity_trades') AS table_name,
            r.rule_dimension,
            r.rule_name,
            r.rule_passed,
            COALESCE(r.rule_rows_evaluated, r.job_rows_scanned, 0) AS rows_evaluated,
            COALESCE(r.rule_rows_passed, IF(r.rule_passed, r.rule_rows_evaluated, 0)) AS rows_passed
          FROM dq_export_results r
          JOIN latest_scan ls ON r.data_quality_job_id = ls.data_quality_job_id
        )
        SELECT
          COUNT(*) AS total_rules_evaluated,
          ROUND(100.0 * COUNTIF(rule_passed) / COUNT(*), 2) AS overall_score_pct
        FROM rule_evals;
        """
        project_id = resolve_test_project_id()
        if not project_id:
            self.skipTest("No active GCP project configured for live BigQuery evaluation")
        cmd = ["bq", "query", f"--project_id={project_id}", "--use_legacy_sql=false", sql_empty]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        # BigQuery will fail with division by zero
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("division by zero", proc.stdout + proc.stderr)

    def test_adv_m3_6_v_dq_rule_summary_precision_and_edge_cases(self):
        """Verifies v_dq_rule_summary precision preservation and basis points behavior."""
        sql = """
        WITH test_inputs AS (
          SELECT * FROM UNNEST([
            STRUCT(100.0 AS pct, 100 AS eval, 100 AS passed, TRUE AS rpassed, '100% pass' AS descr),
            STRUCT(99.95, 10000, 9995, TRUE, '99.95% pass'),
            STRUCT(33.333333333, 3, 1, FALSE, '1/3 pass'),
            STRUCT(77.777777777, 9, 7, FALSE, '7/9 pass'),
            STRUCT(0.0, 100, 0, FALSE, '0% pass'),
            STRUCT(CAST(NULL AS FLOAT64), 1000000, 999999, FALSE, '1 violation in 1M without pct'),
            STRUCT(CAST(NULL AS FLOAT64), 0, 0, TRUE, '0 rows evaluated, passed'),
            STRUCT(CAST(NULL AS FLOAT64), 0, 0, FALSE, '0 rows evaluated, failed')
          ])
        )
        SELECT
          descr,
          ROUND(
            COALESCE(
              pct / 100.0,
              IF(eval > 0, passed / eval, NULL),
              IF(rpassed, 1.0, 0.0)
            ),
            4
          ) AS pass_ratio
        FROM test_inputs;
        """
        rows = run_bq_query(sql)
        ratios = {r["descr"]: float(r["pass_ratio"]) for r in rows}

        # 1. Exact 1.0 and 0.0
        self.assertEqual(ratios["100% pass"], 1.0)
        self.assertEqual(ratios["0% pass"], 0.0)

        # 2. Basis points precision preserved to 4 decimals (0.01% resolution)
        self.assertEqual(ratios["99.95% pass"], 0.9995)
        self.assertEqual(ratios["1/3 pass"], 0.3333)
        self.assertEqual(ratios["7/9 pass"], 0.7778)

        # 3. 0 evaluated rows fallback
        self.assertEqual(ratios["0 rows evaluated, passed"], 1.0)
        self.assertEqual(ratios["0 rows evaluated, failed"], 0.0)

        # 4. Critical insight: 1 violation in 1,000,000 rounds to 1.0000 at 4 decimal places
        self.assertEqual(ratios["1 violation in 1M without pct"], 1.0)

    def test_adv_m3_7_offline_runner_simulation_fidelity(self):
        """Verifies scripts/run_dataplex_scan.py correctly detects all 4 injected SLA violations."""
        script_path = PROJECT_ROOT / "scripts" / "run_dataplex_scan.py"
        cmd = ["python3", str(script_path), "--mode=dry-run"]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, f"Dry-run failed: {proc.stderr}")
        self.assertIn("Offline Simulation Succeeded", proc.stdout)
        self.assertIn("RED (CRITICAL: Anti-Wash Trading Breach Detected)", proc.stdout)
        self.assertIn("100.00%", proc.stdout)
        self.assertIn("55.56%", proc.stdout)


if __name__ == "__main__":
    unittest.main()
