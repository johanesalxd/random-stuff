"""Adversarial stress test suite for Dataplex Auto Data Quality rules and scan runner.

Tests cover:
- Rule 1 (Freshness SLA): Boundary timestamps (exactly 2h ago, 2h + 1s ago, future timestamps, stale timestamps).
- Rule 2 (Completeness): Null injection across trade_id, instrument_code, price, volume individually and combined.
- Rule 3 (Range Checks): Boundary price $0.00, negative prices, volume 0, negative volumes against strictMinEnabled: true.
- Rule 4 (Anti-Wash Trading): Wash trade detection (buyer_id == seller_id) and failure forensics query generation.
- Runner CLI & Simulation: Invalid arguments, boundary options, offline simulation engine, scorecard computation, and RAG status logic.
- BigQuery GoogleSQL Ground Truth: Direct execution of SQL expressions against BigQuery engine.
"""

from datetime import datetime, timezone, timedelta
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from typing import Any, Dict, List, Optional, Tuple, Union
import unittest
from unittest.mock import patch
import yaml

from scripts.run_dataplex_scan import (
    OfflineSimulationEngine,
    RuleEvaluationResult,
    ExecutiveScorecard,
    format_table,
    validate_sql_files,
    get_default_project_id,
)
from tests.test_helpers import (
    PROJECT_ROOT,
    DataplexSpecEvaluator,
    SGXTradeFixtures,
)


class TestRule1FreshnessBoundaries(unittest.TestCase):
    """Adversarial stress tests for Dataplex DQ Rule 1: Freshness SLA."""

    def setUp(self):
        self.spec_file = PROJECT_ROOT / "config" / "dataplex_dq_spec.yaml"
        self.assertTrue(self.spec_file.exists(), "Dataplex DQ spec file must exist")
        with open(self.spec_file, "r", encoding="utf-8") as f:
            self.spec = yaml.safe_load(f)

        self.engine = OfflineSimulationEngine(
            project_id="test-proj",
            dataset_id="test_ds",
            table_id="equity_trades",
            spec_file=self.spec_file,
        )

    def test_freshness_rule_configuration(self):
        """Verifies freshness rule exists and targets trade_timestamp within 2 hours."""
        fresh_rules = [
            r for r in self.spec.get("rules", [])
            if r.get("dimension") == "FRESHNESS"
        ]
        self.assertEqual(len(fresh_rules), 1, "Exactly 1 FRESHNESS rule expected")
        rule = fresh_rules[0]
        self.assertEqual(rule.get("column"), "trade_timestamp")
        sql_expr = rule.get("rowConditionExpectation", {}).get("sqlExpression", "")
        self.assertIn("INTERVAL 2 HOUR", sql_expr)
        self.assertIn("TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 2 HOUR)", sql_expr)

    def test_freshness_boundary_exactly_two_hours_ago(self):
        """Boundary test: Record timestamp executed exactly 2 hours (120 minutes) ago must PASS."""
        fixed_now = datetime(2026, 9, 14, 12, 0, 0, tzinfo=timezone.utc)
        exact_2h = (fixed_now - timedelta(hours=2)).isoformat()

        record = SGXTradeFixtures.get_valid_trade_batch(1)[0]
        record["trade_timestamp"] = exact_2h

        with patch("scripts.run_dataplex_scan.datetime") as mock_dt:
            mock_dt.now.return_value = fixed_now
            mock_dt.fromisoformat = datetime.fromisoformat
            mock_dt.side_effect = lambda *args, **kw: datetime(*args, **kw)

            results = self.engine.evaluate_rules(self.spec, [record])

        fresh_res = next(r for r in results if r.dimension == "FRESHNESS")
        self.assertTrue(
            fresh_res.passed,
            f"Timestamp exactly 2 hours ago ({exact_2h}) should PASS freshness SLA"
        )
        self.assertEqual(fresh_res.rows_passed, 1)

    def test_freshness_boundary_two_hours_plus_one_second_ago(self):
        """Boundary test: Record timestamp executed 2 hours and 1 second ago must FAIL."""
        fixed_now = datetime(2026, 9, 14, 12, 0, 0, tzinfo=timezone.utc)
        stale_2h_1s = (fixed_now - timedelta(hours=2, seconds=1)).isoformat()

        record = SGXTradeFixtures.get_valid_trade_batch(1)[0]
        record["trade_timestamp"] = stale_2h_1s

        with patch("scripts.run_dataplex_scan.datetime") as mock_dt:
            mock_dt.now.return_value = fixed_now
            mock_dt.fromisoformat = datetime.fromisoformat
            mock_dt.side_effect = lambda *args, **kw: datetime(*args, **kw)

            results = self.engine.evaluate_rules(self.spec, [record])

        fresh_res = next(r for r in results if r.dimension == "FRESHNESS")
        self.assertFalse(
            fresh_res.passed,
            f"Timestamp 2 hours + 1 second ago ({stale_2h_1s}) must FAIL freshness SLA"
        )
        self.assertEqual(fresh_res.rows_passed, 0)
        self.assertIn("trade_timestamp < TIMESTAMP_SUB", fresh_res.failed_records_query)

    def test_freshness_boundary_future_timestamp(self):
        """Boundary test: Future timestamp (e.g. +5 minutes, +1 hour) satisfies >= 2h ago."""
        fixed_now = datetime(2026, 9, 14, 12, 0, 0, tzinfo=timezone.utc)
        future_5m = (fixed_now + timedelta(minutes=5)).isoformat()

        record = SGXTradeFixtures.get_valid_trade_batch(1)[0]
        record["trade_timestamp"] = future_5m

        with patch("scripts.run_dataplex_scan.datetime") as mock_dt:
            mock_dt.now.return_value = fixed_now
            mock_dt.fromisoformat = datetime.fromisoformat
            mock_dt.side_effect = lambda *args, **kw: datetime(*args, **kw)

            results = self.engine.evaluate_rules(self.spec, [record])

        fresh_res = next(r for r in results if r.dimension == "FRESHNESS")
        # In SQL expression `ts >= CURRENT_TIMESTAMP - 2h`, future timestamp is >= 2h ago
        self.assertTrue(
            fresh_res.passed,
            f"Future timestamp ({future_5m}) satisfies >= CURRENT_TIMESTAMP - 2h condition"
        )

    def test_freshness_grossly_stale_records(self):
        """Stress test: Timestamps significantly beyond 2 hours (4h, 24h, 1 year) must all FAIL."""
        fixed_now = datetime(2026, 9, 14, 12, 0, 0, tzinfo=timezone.utc)
        stale_offsets = [timedelta(hours=3), timedelta(hours=24), timedelta(days=365)]

        for offset in stale_offsets:
            with self.subTest(offset=str(offset)):
                ts = (fixed_now - offset).isoformat()
                record = SGXTradeFixtures.get_valid_trade_batch(1)[0]
                record["trade_timestamp"] = ts

                with patch("scripts.run_dataplex_scan.datetime") as mock_dt:
                    mock_dt.now.return_value = fixed_now
                    mock_dt.fromisoformat = datetime.fromisoformat
                    mock_dt.side_effect = lambda *args, **kw: datetime(*args, **kw)

                    results = self.engine.evaluate_rules(self.spec, [record])

                fresh_res = next(r for r in results if r.dimension == "FRESHNESS")
                self.assertFalse(fresh_res.passed, f"Offset {offset} must fail freshness SLA")

    def test_freshness_malformed_timestamp_fails(self):
        """Stress test: Unparseable timestamp string fails evaluation gracefully."""
        record = SGXTradeFixtures.get_valid_trade_batch(1)[0]
        record["trade_timestamp"] = "NOT_A_VALID_TIMESTAMP"

        results = self.engine.evaluate_rules(self.spec, [record])
        fresh_res = next(r for r in results if r.dimension == "FRESHNESS")
        self.assertFalse(fresh_res.passed, "Malformed timestamp must not pass freshness SLA")


class TestRule2CompletenessBoundaries(unittest.TestCase):
    """Adversarial stress tests for Dataplex DQ Rule 2: Completeness (Non-Nulls)."""

    def setUp(self):
        self.spec_file = PROJECT_ROOT / "config" / "dataplex_dq_spec.yaml"
        with open(self.spec_file, "r", encoding="utf-8") as f:
            self.spec = yaml.safe_load(f)

        self.engine = OfflineSimulationEngine(
            project_id="test-proj",
            dataset_id="test_ds",
            table_id="equity_trades",
            spec_file=self.spec_file,
        )
        self.required_cols = ["trade_id", "instrument_code", "price", "volume"]

    def test_completeness_rules_configured(self):
        """Verifies all 4 required columns have nonNullExpectation configured with threshold 1.0."""
        comp_rules = [
            r for r in self.spec.get("rules", [])
            if r.get("dimension") == "COMPLETENESS" and "nonNullExpectation" in r
        ]
        configured_cols = {r.get("column") for r in comp_rules}
        for col in self.required_cols:
            self.assertIn(col, configured_cols, f"Missing nonNullExpectation for column: {col}")

    def test_null_in_trade_id_only_fails_trade_id_rule(self):
        """Injecting NULL into trade_id fails trade_id rule but other completeness rules pass."""
        record = SGXTradeFixtures.get_valid_trade_batch(1)[0]
        record["trade_id"] = None

        results = self.engine.evaluate_rules(self.spec, [record])
        comp_res = {r.column: r for r in results if r.dimension == "COMPLETENESS"}

        self.assertFalse(comp_res["trade_id"].passed, "trade_id rule must fail on NULL")
        self.assertEqual(comp_res["trade_id"].rows_null, 1)
        self.assertIn("WHERE trade_id IS NULL", comp_res["trade_id"].failed_records_query)

        self.assertTrue(comp_res["instrument_code"].passed)
        self.assertTrue(comp_res["price"].passed)
        self.assertTrue(comp_res["volume"].passed)

    def test_null_in_instrument_code_only_fails_instrument_code_rule(self):
        """Injecting NULL into instrument_code fails instrument_code rule while others pass."""
        record = SGXTradeFixtures.get_valid_trade_batch(1)[0]
        record["instrument_code"] = None

        results = self.engine.evaluate_rules(self.spec, [record])
        comp_res = {r.column: r for r in results if r.dimension == "COMPLETENESS"}

        self.assertFalse(comp_res["instrument_code"].passed)
        self.assertEqual(comp_res["instrument_code"].rows_null, 1)
        self.assertTrue(comp_res["trade_id"].passed)
        self.assertTrue(comp_res["price"].passed)
        self.assertTrue(comp_res["volume"].passed)

    def test_null_in_price_only_fails_price_rule(self):
        """Injecting NULL into price fails price completeness rule while others pass."""
        record = SGXTradeFixtures.get_valid_trade_batch(1)[0]
        record["price"] = None

        results = self.engine.evaluate_rules(self.spec, [record])
        comp_res = {r.column: r for r in results if r.dimension == "COMPLETENESS"}

        self.assertFalse(comp_res["price"].passed)
        self.assertEqual(comp_res["price"].rows_null, 1)
        self.assertTrue(comp_res["trade_id"].passed)
        self.assertTrue(comp_res["instrument_code"].passed)
        self.assertTrue(comp_res["volume"].passed)

    def test_null_in_volume_only_fails_volume_rule(self):
        """Injecting NULL into volume fails volume completeness rule while others pass."""
        record = SGXTradeFixtures.get_valid_trade_batch(1)[0]
        record["volume"] = None

        results = self.engine.evaluate_rules(self.spec, [record])
        comp_res = {r.column: r for r in results if r.dimension == "COMPLETENESS"}

        self.assertFalse(comp_res["volume"].passed)
        self.assertEqual(comp_res["volume"].rows_null, 1)
        self.assertTrue(comp_res["trade_id"].passed)
        self.assertTrue(comp_res["instrument_code"].passed)
        self.assertTrue(comp_res["price"].passed)

    def test_all_four_columns_null_simultaneously(self):
        """Injecting NULL across all 4 columns simultaneously fails all 4 completeness rules."""
        record = SGXTradeFixtures.get_valid_trade_batch(1)[0]
        for col in self.required_cols:
            record[col] = None

        results = self.engine.evaluate_rules(self.spec, [record])
        comp_res = [r for r in results if r.dimension == "COMPLETENESS"]
        self.assertEqual(len(comp_res), 4)
        for r in comp_res:
            self.assertFalse(r.passed, f"Rule for {r.column} must fail when value is NULL")
            self.assertEqual(r.rows_null, 1)


class TestRule3RangeChecksBoundaries(unittest.TestCase):
    """Adversarial stress tests for Dataplex DQ Rule 3: Range Checks."""

    def setUp(self):
        self.spec_file = PROJECT_ROOT / "config" / "dataplex_dq_spec.yaml"
        with open(self.spec_file, "r", encoding="utf-8") as f:
            self.spec = yaml.safe_load(f)

        self.engine = OfflineSimulationEngine(
            project_id="test-proj",
            dataset_id="test_ds",
            table_id="equity_trades",
            spec_file=self.spec_file,
        )

    def test_range_rule_spec_configurations(self):
        """Verifies strictMinEnabled: true and minValue: '0' for price and volume."""
        range_rules = {
            r.get("column"): r for r in self.spec.get("rules", [])
            if "rangeExpectation" in r
        }
        self.assertIn("price", range_rules)
        self.assertIn("volume", range_rules)

        for col in ["price", "volume"]:
            rule = range_rules[col]
            self.assertEqual(rule.get("dimension"), "VALIDITY")
            self.assertFalse(rule.get("ignoreNull", True))
            range_exp = rule["rangeExpectation"]
            self.assertEqual(range_exp.get("minValue"), "0")
            self.assertTrue(
                range_exp.get("strictMinEnabled") is True,
                f"strictMinEnabled must be true for {col}"
            )

    def test_price_boundary_zero_rejected(self):
        """Boundary test: Price $0.00 must FAIL range check when strictMinEnabled: true."""
        record = SGXTradeFixtures.get_valid_trade_batch(1)[0]
        record["price"] = 0.00

        results = self.engine.evaluate_rules(self.spec, [record])
        price_range = next(r for r in results if r.column == "price" and r.rule_type == "Range Check")
        self.assertFalse(price_range.passed, "Price $0.00 must FAIL range check")
        self.assertEqual(price_range.rows_passed, 0)
        self.assertIn("price <= 0.0", price_range.failed_records_query)

    def test_negative_prices_rejected(self):
        """Stress test: Negative prices (-0.0001, -1.0, -100.0) must FAIL range check."""
        for neg_p in [-0.0001, -0.01, -1.0, -100.0, -999999.0]:
            with self.subTest(price=neg_p):
                record = SGXTradeFixtures.get_valid_trade_batch(1)[0]
                record["price"] = neg_p
                results = self.engine.evaluate_rules(self.spec, [record])
                price_range = next(r for r in results if r.column == "price" and r.rule_type == "Range Check")
                self.assertFalse(price_range.passed, f"Negative price {neg_p} must fail range check")

    def test_tiny_positive_price_passes(self):
        """Boundary test: Strictly positive price (0.0001, 0.01) must PASS range check."""
        for pos_p in [0.0001, 0.001, 0.01, 1.0, 35.80]:
            with self.subTest(price=pos_p):
                record = SGXTradeFixtures.get_valid_trade_batch(1)[0]
                record["price"] = pos_p
                results = self.engine.evaluate_rules(self.spec, [record])
                price_range = next(r for r in results if r.column == "price" and r.rule_type == "Range Check")
                self.assertTrue(price_range.passed, f"Positive price {pos_p} must pass range check")

    def test_volume_boundary_zero_rejected(self):
        """Boundary test: Volume 0 must FAIL range check when strictMinEnabled: true."""
        record = SGXTradeFixtures.get_valid_trade_batch(1)[0]
        record["volume"] = 0

        results = self.engine.evaluate_rules(self.spec, [record])
        vol_range = next(r for r in results if r.column == "volume" and r.rule_type == "Range Check")
        self.assertFalse(vol_range.passed, "Volume 0 must FAIL range check")
        self.assertEqual(vol_range.rows_passed, 0)
        self.assertIn("volume <= 0.0", vol_range.failed_records_query)

    def test_negative_volumes_rejected(self):
        """Stress test: Negative volumes (-1, -100, -5000) must FAIL range check."""
        for neg_v in [-1, -10, -500, -10000]:
            with self.subTest(volume=neg_v):
                record = SGXTradeFixtures.get_valid_trade_batch(1)[0]
                record["volume"] = neg_v
                results = self.engine.evaluate_rules(self.spec, [record])
                vol_range = next(r for r in results if r.column == "volume" and r.rule_type == "Range Check")
                self.assertFalse(vol_range.passed, f"Negative volume {neg_v} must fail range check")

    def test_minimum_positive_volume_passes(self):
        """Boundary test: Volume = 1 share must PASS range check."""
        record = SGXTradeFixtures.get_valid_trade_batch(1)[0]
        record["volume"] = 1

        results = self.engine.evaluate_rules(self.spec, [record])
        vol_range = next(r for r in results if r.column == "volume" and r.rule_type == "Range Check")
        self.assertTrue(vol_range.passed, "Volume 1 must PASS range check")


class TestRule4AntiWashTradingBoundaries(unittest.TestCase):
    """Adversarial stress tests for Dataplex DQ Rule 4: Anti-Wash Trading (Integrity)."""

    def setUp(self):
        self.spec_file = PROJECT_ROOT / "config" / "dataplex_dq_spec.yaml"
        with open(self.spec_file, "r", encoding="utf-8") as f:
            self.spec = yaml.safe_load(f)

        self.engine = OfflineSimulationEngine(
            project_id="test-proj",
            dataset_id="test_ds",
            table_id="equity_trades",
            spec_file=self.spec_file,
        )

    def test_anti_wash_trading_rule_configuration(self):
        """Verifies anti-wash trading rule exists under INTEGRITY dimension with buyer_id != seller_id."""
        integ_rules = [
            r for r in self.spec.get("rules", [])
            if r.get("dimension") == "INTEGRITY"
        ]
        self.assertEqual(len(integ_rules), 1, "Exactly 1 INTEGRITY rule expected")
        rule = integ_rules[0]
        sql_expr = rule.get("rowConditionExpectation", {}).get("sqlExpression", "")
        self.assertEqual(sql_expr, "buyer_id != seller_id")

    def test_wash_trade_identical_counterparties_fails(self):
        """Stress test: Trade where buyer_id == seller_id must FAIL integrity rule."""
        identical_pairs = [
            ("BROKER_DBS_01", "BROKER_DBS_01"),
            ("BROKER_OCBC_02", "BROKER_OCBC_02"),
            ("WASH_TRADER_999", "WASH_TRADER_999"),
        ]
        for buyer, seller in identical_pairs:
            with self.subTest(buyer=buyer, seller=seller):
                record = SGXTradeFixtures.get_valid_trade_batch(1)[0]
                record["buyer_id"] = buyer
                record["seller_id"] = seller

                results = self.engine.evaluate_rules(self.spec, [record])
                wash_res = next(r for r in results if r.dimension == "INTEGRITY")
                self.assertFalse(wash_res.passed, f"Wash trade ({buyer} == {seller}) must FAIL integrity rule")
                self.assertEqual(wash_res.rows_passed, 0)
                self.assertIn("buyer_id = seller_id", wash_res.failed_records_query)

    def test_wash_trade_with_whitespace_stripping(self):
        """Stress test: Counterparties identical after trimming must FAIL integrity rule."""
        record = SGXTradeFixtures.get_valid_trade_batch(1)[0]
        record["buyer_id"] = "BROKER_DBS_01 "
        record["seller_id"] = " BROKER_DBS_01"

        results = self.engine.evaluate_rules(self.spec, [record])
        wash_res = next(r for r in results if r.dimension == "INTEGRITY")
        self.assertFalse(wash_res.passed, "Wash trade with whitespace padding must FAIL integrity rule")

    def test_distinct_counterparties_pass(self):
        """Valid counterparty pairs must PASS integrity rule."""
        valid_pairs = [
            ("BROKER_DBS_01", "BROKER_OCBC_02"),
            ("BROKER_UOB_01", "BROKER_CITI_01"),
            ("BROKER_HSBC_01", "BROKER_SCB_01"),
        ]
        for buyer, seller in valid_pairs:
            with self.subTest(buyer=buyer, seller=seller):
                record = SGXTradeFixtures.get_valid_trade_batch(1)[0]
                record["buyer_id"] = buyer
                record["seller_id"] = seller

                results = self.engine.evaluate_rules(self.spec, [record])
                wash_res = next(r for r in results if r.dimension == "INTEGRITY")
                self.assertTrue(wash_res.passed, f"Valid trade ({buyer} != {seller}) must PASS")


class TestDataplexScanRunnerScript(unittest.TestCase):
    """Stress tests for scripts/run_dataplex_scan.py CLI and execution mechanics."""

    def setUp(self):
        self.runner_script = PROJECT_ROOT / "scripts" / "run_dataplex_scan.py"
        self.assertTrue(self.runner_script.exists(), "run_dataplex_scan.py must exist")

    def test_cli_help_flag_succeeds(self):
        """Invoking with --help returns exit code 0 and displays flags."""
        res = subprocess.run(
            [sys.executable, str(self.runner_script), "--help"],
            capture_output=True, text=True, check=False
        )
        self.assertEqual(res.returncode, 0)
        self.assertIn("--project-id", res.stdout)
        self.assertIn("--mode", res.stdout)
        self.assertIn("dry-run", res.stdout)

    def test_cli_invalid_mode_choice_fails(self):
        """Invoking with an unrecognized mode produces exit code 2 (argparse error)."""
        res = subprocess.run(
            [sys.executable, str(self.runner_script), "--mode=invalid_xyz_mode"],
            capture_output=True, text=True, check=False
        )
        self.assertEqual(res.returncode, 2)
        self.assertIn("invalid choice", res.stderr)

    def test_cli_poll_mode_without_job_id_fails(self):
        """Invoking --mode=poll without --job-id exits with code 1."""
        res = subprocess.run(
            [sys.executable, str(self.runner_script), "--mode=poll"],
            capture_output=True, text=True, check=False
        )
        self.assertEqual(res.returncode, 1)
        self.assertIn("--job-id is required", res.stdout + res.stderr)

    def test_cli_missing_spec_file_fails(self):
        """Invoking --mode=dry-run with non-existent --spec-file exits with code 1."""
        res = subprocess.run(
            [sys.executable, str(self.runner_script), "--mode=dry-run", "--spec-file=/tmp/non_existent_spec.yaml"],
            capture_output=True, text=True, check=False
        )
        self.assertEqual(res.returncode, 1)
        self.assertIn("spec file not found", res.stdout + res.stderr)

    def test_cli_dry_run_success_with_all_flags(self):
        """Invoking --mode=dry-run with explicit boundary parameters succeeds cleanly."""
        cmd = [
            sys.executable, str(self.runner_script),
            "--mode=dry-run",
            "--project-id=test-custom-proj",
            "--dataset=custom_market_data",
            "--table=custom_trades",
            "--location=asia-southeast1",
            "--verbose"
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, check=False)
        self.assertEqual(res.returncode, 0, f"dry-run failed:\nStdout: {res.stdout}\nStderr: {res.stderr}")
        self.assertIn("EXECUTIVE DATA QUALITY SCORECARD", res.stdout)
        self.assertIn("test-custom-proj.custom_market_data.custom_trades", res.stdout)
        self.assertIn("All injected SLA violations accurately detected", res.stdout)

    def test_format_table_utility_edge_cases(self):
        """Stress tests ASCII table formatter with empty inputs, mismatched widths, and long strings."""
        self.assertEqual(format_table([], []), "")

        # Single row and column
        t1 = format_table(["Header"], [["Value"]])
        self.assertIn("Header", t1)
        self.assertIn("Value", t1)

        # Mismatched rows
        t2 = format_table(["Col1", "Col2"], [["Val1"]])
        self.assertIn("Col1", t2)
        self.assertIn("Val1", t2)

    def test_executive_rag_status_transitions(self):
        """Verifies RAG indicator transitions: GREEN on perfect pass, RED on wash/freshness, AMBER on validity."""
        engine = OfflineSimulationEngine(
            project_id="test-proj",
            dataset_id="test_ds",
            table_id="equity_trades",
            spec_file=PROJECT_ROOT / "config" / "dataplex_dq_spec.yaml",
        )

        with open(engine.spec_file) as f:
            spec_data = yaml.safe_load(f)

        # 1. Perfectly conforming trade events -> GREEN
        valid_trades = SGXTradeFixtures.get_valid_trade_batch(5)
        evals_green = engine.evaluate_rules(spec_data, valid_trades)
        scorecard_green = engine.build_scorecard(evals_green)
        self.assertIn("GREEN", scorecard_green.executive_rag_status)
        self.assertEqual(scorecard_green.total_rules_failed, 0)
        self.assertEqual(scorecard_green.overall_score_pct, 100.0)

        # 2. Injected Wash Trade -> RED
        wash_trade = SGXTradeFixtures.get_wash_trade_payload()
        evals_red_wash = engine.evaluate_rules(spec_data, [wash_trade])
        scorecard_red_wash = engine.build_scorecard(evals_red_wash)
        self.assertIn("RED", scorecard_red_wash.executive_rag_status)
        self.assertIn("Anti-Wash Trading Breach", scorecard_red_wash.executive_rag_status)

        # 3. Injected Stale Trade -> RED
        stale_trade = SGXTradeFixtures.get_stale_sla_payload(hours_ago=5.0)
        evals_red_stale = engine.evaluate_rules(spec_data, [stale_trade])
        scorecard_red_stale = engine.build_scorecard(evals_red_stale)
        self.assertIn("RED", scorecard_red_stale.executive_rag_status)

        # 4. Injected Negative Price (Validity failure only, while integrity and freshness pass)
        now_iso = SGXTradeFixtures.now_iso()
        val_bad_trade = {
            "trade_id": "TR-VAL-001",
            "instrument_code": "D05.SI",
            "price": -10.0,
            "volume": 100,
            "buyer_id": "B1",
            "seller_id": "S1",
            "trade_timestamp": now_iso,
            "trade_status": "EXECUTED",
        }
        evals_amber = engine.evaluate_rules(spec_data, [val_bad_trade])
        scorecard_amber = engine.build_scorecard(evals_amber)
        self.assertIn("AMBER", scorecard_amber.executive_rag_status)

    def test_sql_files_validation_method(self):
        """Verifies validate_sql_files confirms all 3 required Milestone 3 SQL files."""
        # Should execute with zero assertion errors
        validate_sql_files("test-proj", "test_ds")


class TestDataplexSqlExpressionsOnBigQuery(unittest.TestCase):
    """Ground truth empirical tests evaluating DQ SQL expressions directly in BigQuery."""

    @classmethod
    def setUpClass(cls):
        cls.bq_available = shutil.which("bq") is not None
        cls.project_id = get_default_project_id()

    def setUp(self):
        if not self.bq_available:
            self.skipTest("BigQuery CLI (bq) not available")

    def run_bq_query(self, query: str) -> List[Dict[str, Any]]:
        """Executes a GoogleSQL expression query against BigQuery and parses JSON results."""
        cmd = [
            "bq", "query",
            f"--project_id={self.project_id}",
            "--use_legacy_sql=false",
            "--format=json",
            query
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
        self.assertEqual(
            proc.returncode, 0,
            f"BigQuery query failed:\nStdout: {proc.stdout}\nStderr: {proc.stderr}"
        )
        return json.loads(proc.stdout)

    def test_bq_freshness_sql_evaluation(self):
        """Validates GoogleSQL evaluation of Rule 1: trade_timestamp >= TIMESTAMP_SUB(base, INTERVAL 2 HOUR)."""
        query = """
        SELECT 
          (ts >= TIMESTAMP_SUB(base_ts, INTERVAL 2 HOUR)) AS rule_eval,
          label
        FROM (
          SELECT TIMESTAMP '2026-09-14 12:00:00 UTC' AS base_ts
        ) CROSS JOIN UNNEST([
          STRUCT(TIMESTAMP '2026-09-14 10:00:00 UTC' AS ts, 'exact_2h' AS label),
          STRUCT(TIMESTAMP '2026-09-14 09:59:59 UTC' AS ts, 'stale_2h_1s' AS label),
          STRUCT(TIMESTAMP '2026-09-14 10:00:01 UTC' AS ts, 'within_2h' AS label),
          STRUCT(TIMESTAMP '2026-09-14 12:05:00 UTC' AS ts, 'future_5m' AS label)
        ])
        """
        results = {r["label"]: r["rule_eval"] for r in self.run_bq_query(query)}
        self.assertEqual(results["exact_2h"], "true")
        self.assertEqual(results["stale_2h_1s"], "false")
        self.assertEqual(results["within_2h"], "true")
        self.assertEqual(results["future_5m"], "true")

    def test_bq_range_checks_sql_evaluation(self):
        """Validates GoogleSQL evaluation of Rule 3: price > 0.0 and volume > 0."""
        query = """
        SELECT 
          label,
          (price > 0.0) AS price_pass,
          (volume > 0) AS volume_pass
        FROM UNNEST([
          STRUCT('zero_price' AS label, 0.0 AS price, 1000 AS volume),
          STRUCT('neg_price' AS label, -12.50 AS price, 1000 AS volume),
          STRUCT('valid_price' AS label, 35.80 AS price, 1000 AS volume),
          STRUCT('zero_vol' AS label, 35.80 AS price, 0 AS volume),
          STRUCT('neg_vol' AS label, 35.80 AS price, -500 AS volume),
          STRUCT('valid_vol' AS label, 35.80 AS price, 1 AS volume)
        ])
        """
        results = {r["label"]: r for r in self.run_bq_query(query)}
        self.assertEqual(results["zero_price"]["price_pass"], "false")
        self.assertEqual(results["neg_price"]["price_pass"], "false")
        self.assertEqual(results["valid_price"]["price_pass"], "true")
        self.assertEqual(results["zero_vol"]["volume_pass"], "false")
        self.assertEqual(results["neg_vol"]["volume_pass"], "false")
        self.assertEqual(results["valid_vol"]["volume_pass"], "true")

    def test_bq_anti_wash_trading_sql_evaluation(self):
        """Validates GoogleSQL evaluation of Rule 4: buyer_id != seller_id."""
        query = """
        SELECT 
          label,
          (buyer_id != seller_id) AS rule_pass,
          (buyer_id = seller_id) AS violation_detected
        FROM UNNEST([
          STRUCT('wash_trade' AS label, 'BROKER_DBS_01' AS buyer_id, 'BROKER_DBS_01' AS seller_id),
          STRUCT('legit_trade' AS label, 'BROKER_DBS_01' AS buyer_id, 'BROKER_OCBC_02' AS seller_id)
        ])
        """
        results = {r["label"]: r for r in self.run_bq_query(query)}
        self.assertEqual(results["wash_trade"]["rule_pass"], "false")
        self.assertEqual(results["wash_trade"]["violation_detected"], "true")
        self.assertEqual(results["legit_trade"]["rule_pass"], "true")
        self.assertEqual(results["legit_trade"]["violation_detected"], "false")


if __name__ == "__main__":
    unittest.main()
