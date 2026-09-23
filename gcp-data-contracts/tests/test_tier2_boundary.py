"""Tier 2: Boundary and Corner Cases Test Suite.

Covers boundary conditions, edge cases, and failure modes across:
- Compiler error handling (missing, empty, and malformed contracts)
- Ingress wire schema rejection (null values, missing required fields, type mismatches, invalid enums)
- Dataplex Data Quality boundary evaluations (zero price, negative price, zero/negative volume)
- Regulatory financial assertions (wash trading collision detection, stale freshness SLA latency)
- Extreme ticker lengths and character boundaries
"""

import json
from pathlib import Path
import shutil
import tempfile
import unittest
import yaml

from tests.test_helpers import (
    PROJECT_ROOT,
    REFERENCE_AVRO_SCHEMA,
    CompilerRunner,
    DataplexSpecEvaluator,
    PubSubSchemaOracle,
    SGXTradeFixtures,
)


class TestTier2CompilerBoundaries(unittest.TestCase):
    """Tier 2: Boundary tests for compile_contract.py CLI error handling."""

    def setUp(self):
        self.compiler_path = CompilerRunner.compiler_path()
        self.temp_dir = Path(tempfile.mkdtemp(prefix="sgx_tier2_compiler_"))

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_2_1_compiler_fails_on_missing_contract_file(self):
        """Validates compiler fails cleanly with non-zero exit code on non-existent contract."""
        if not self.compiler_path.exists():
            self.skipTest("compile_contract.py not yet present")

        non_existent = self.temp_dir / "does_not_exist.odcs.yaml"
        proc = CompilerRunner.run(["--contract", str(non_existent)])
        self.assertNotEqual(
            proc.returncode, 0,
            "Compiler should return non-zero exit code when input contract file is missing"
        )
        self.assertTrue(
            "not found" in proc.stderr.lower() or "error" in proc.stderr.lower() or "no such file" in proc.stderr.lower(),
            f"Expected descriptive error message in stderr, got: {proc.stderr}"
        )

    def test_2_2_compiler_fails_on_empty_contract_file(self):
        """Validates compiler fails on an empty (0-byte) contract file."""
        if not self.compiler_path.exists():
            self.skipTest("compile_contract.py not yet present")

        empty_file = self.temp_dir / "empty.odcs.yaml"
        empty_file.write_text("", encoding="utf-8")

        proc = CompilerRunner.run(["--contract", str(empty_file)])
        self.assertNotEqual(
            proc.returncode, 0,
            "Compiler should return non-zero exit code on empty contract file"
        )

    def test_2_3_compiler_fails_on_malformed_yaml(self):
        """Validates compiler rejects corrupt YAML syntax with a non-zero exit code."""
        if not self.compiler_path.exists():
            self.skipTest("compile_contract.py not yet present")

        bad_yaml = self.temp_dir / "corrupt.yaml"
        bad_yaml.write_text("apiVersion: 3.0.0\nkind: DataContract\n  unbalanced_indent: [\n", encoding="utf-8")

        proc = CompilerRunner.run(["--contract", str(bad_yaml)])
        self.assertNotEqual(
            proc.returncode, 0,
            "Compiler should return non-zero exit code on malformed YAML"
        )

    def test_2_4_compiler_fails_on_missing_schema_properties(self):
        """Validates compiler rejects contracts that lack a schema or properties definition."""
        if not self.compiler_path.exists():
            self.skipTest("compile_contract.py not yet present")

        incomplete_contract = self.temp_dir / "incomplete.odcs.yaml"
        incomplete_contract.write_text(yaml.dump({
            "apiVersion": "3.0.0",
            "kind": "DataContract",
            "id": "urn:sgx:incomplete",
            "name": "incomplete"
            # Omitting schema and properties
        }), encoding="utf-8")

        proc = CompilerRunner.run(["--contract", str(incomplete_contract)])
        self.assertNotEqual(
            proc.returncode, 0,
            "Compiler should return non-zero exit code when contract schema is missing"
        )


class TestTier2IngressValidationBoundaries(unittest.TestCase):
    """Tier 2: Ingress schema rejection tests using authoritative Pub/Sub Schema Registry oracle."""

    def setUp(self):
        # Use generated Avro schema if present, otherwise authoritative reference schema
        compiled_avro = PROJECT_ROOT / "schemas" / "trade_event_v1.avsc"
        if compiled_avro.exists():
            self.schema_def = compiled_avro
        else:
            self.schema_def = REFERENCE_AVRO_SCHEMA

    def test_2_5_pubsub_oracle_rejects_missing_trade_id(self):
        """Validates synchronous rejection when required trade_id is omitted from message payload."""
        if not PubSubSchemaOracle.is_gcloud_available():
            self.skipTest("gcloud CLI not available")

        valid_trade = SGXTradeFixtures.get_valid_trade_batch(1)[0]
        bad_payload = {k: v for k, v in valid_trade.items() if k != "trade_id"}

        exit_code, stdout, stderr = PubSubSchemaOracle.validate_message(self.schema_def, bad_payload)
        self.assertEqual(exit_code, 1, "Expected rejection for missing trade_id")
        self.assertIn("Field was not found in JSON object: trade_id", stderr)
        self.assertIn("INVALID_JSON_AVRO_MESSAGE", stderr)

    def test_2_6_pubsub_oracle_rejects_missing_instrument_code(self):
        """Validates synchronous rejection when instrument_code ticker is omitted."""
        if not PubSubSchemaOracle.is_gcloud_available():
            self.skipTest("gcloud CLI not available")

        valid_trade = SGXTradeFixtures.get_valid_trade_batch(1)[0]
        bad_payload = {k: v for k, v in valid_trade.items() if k != "instrument_code"}

        exit_code, stdout, stderr = PubSubSchemaOracle.validate_message(self.schema_def, bad_payload)
        self.assertEqual(exit_code, 1, "Expected rejection for missing instrument_code")
        self.assertIn("Field was not found in JSON object: instrument_code", stderr)
        self.assertIn("INVALID_JSON_AVRO_MESSAGE", stderr)

    def test_2_7_pubsub_oracle_rejects_type_mismatch_string_price(self):
        """Validates rejection when string value is supplied for double price field."""
        if not PubSubSchemaOracle.is_gcloud_available():
            self.skipTest("gcloud CLI not available")

        valid_trade = SGXTradeFixtures.get_valid_trade_batch(1)[0]
        bad_payload = {**valid_trade, "price": "expensive_market_price"}

        exit_code, stdout, stderr = PubSubSchemaOracle.validate_message(self.schema_def, bad_payload)
        self.assertEqual(exit_code, 1, "Expected rejection for string price")
        self.assertIn("expected number_float", stderr)
        self.assertIn("INVALID_JSON_AVRO_MESSAGE", stderr)

    def test_2_8_pubsub_oracle_rejects_type_mismatch_string_volume(self):
        """Validates rejection when string value is supplied for long volume field."""
        if not PubSubSchemaOracle.is_gcloud_available():
            self.skipTest("gcloud CLI not available")

        valid_trade = SGXTradeFixtures.get_valid_trade_batch(1)[0]
        bad_payload = {**valid_trade, "volume": "large_block"}

        exit_code, stdout, stderr = PubSubSchemaOracle.validate_message(self.schema_def, bad_payload)
        self.assertEqual(exit_code, 1, "Expected rejection for string volume")
        self.assertTrue("number_integer" in stderr or "number_long" in stderr or "expected number" in stderr)

    def test_2_9_pubsub_oracle_rejects_invalid_enum_trade_status(self):
        """Validates rejection when invalid enum symbol is passed for trade_status."""
        if not PubSubSchemaOracle.is_gcloud_available():
            self.skipTest("gcloud CLI not available")

        valid_trade = SGXTradeFixtures.get_valid_trade_batch(1)[0]
        bad_payload = {**valid_trade, "trade_status": "PENDING_CONFIRMATION"}

        exit_code, stdout, stderr = PubSubSchemaOracle.validate_message(self.schema_def, bad_payload)
        self.assertEqual(exit_code, 1, "Expected rejection for invalid enum symbol")
        self.assertIn("Invalid enum index without default value: TradeStatus", stderr)
        self.assertIn("INVALID_JSON_AVRO_MESSAGE", stderr)


class TestTier2DataQualityBoundaries(unittest.TestCase):
    """Tier 2: Semantic Data Quality boundary condition evaluations (Dataplex rules)."""

    def test_2_10_dataplex_zero_price_boundary_rejected(self):
        """Validates that price = 0.00 fails Dataplex rangeExpectation (minValue: '0', strictMinEnabled: true)."""
        is_valid = DataplexSpecEvaluator.evaluate_range(0.00, min_value=0.0, strict_min=True)
        self.assertFalse(is_valid, "Zero price must be rejected when strictMinEnabled: true")

    def test_2_11_dataplex_negative_price_boundary_rejected(self):
        """Validates that negative price fails Dataplex rangeExpectation."""
        is_valid = DataplexSpecEvaluator.evaluate_range(-25.50, min_value=0.0, strict_min=True)
        self.assertFalse(is_valid, "Negative price must be rejected")

    def test_2_12_dataplex_strictly_positive_price_passes(self):
        """Validates that legitimate positive trade prices pass Dataplex rangeExpectation."""
        self.assertTrue(DataplexSpecEvaluator.evaluate_range(0.001, min_value=0.0, strict_min=True))
        self.assertTrue(DataplexSpecEvaluator.evaluate_range(35.80, min_value=0.0, strict_min=True))

    def test_2_13_dataplex_zero_and_negative_volume_boundary_rejected(self):
        """Validates that volume = 0 and negative volume fail Dataplex rangeExpectation."""
        self.assertFalse(
            DataplexSpecEvaluator.evaluate_range(0, min_value=0, strict_min=True),
            "Zero volume must be rejected"
        )
        self.assertFalse(
            DataplexSpecEvaluator.evaluate_range(-1000, min_value=0, strict_min=True),
            "Negative volume must be rejected"
        )
        self.assertTrue(
            DataplexSpecEvaluator.evaluate_range(1, min_value=0, strict_min=True),
            "Positive volume of 1 share must pass"
        )

    def test_2_14_dataplex_anti_wash_trading_collision_detected(self):
        """Validates that matching buyer_id and seller_id triggers anti-wash trading rule failure."""
        # Wash trading match
        is_valid = DataplexSpecEvaluator.evaluate_anti_wash_trading("BROKER_DBS_01", "BROKER_DBS_01")
        self.assertFalse(is_valid, "Wash trade (buyer == seller) must violate integrity rule")

        # Legitimate counterparties
        is_valid = DataplexSpecEvaluator.evaluate_anti_wash_trading("BROKER_DBS_01", "BROKER_OCBC_02")
        self.assertTrue(is_valid, "Distinct counterparties must pass integrity rule")

    def test_2_15_dataplex_freshness_sla_latency_boundary(self):
        """Validates that execution timestamp older than 2 hours violates freshness SLA."""
        now_iso = SGXTradeFixtures.now_iso()
        self.assertTrue(
            DataplexSpecEvaluator.evaluate_freshness(now_iso, max_age_hours=2.0),
            "Fresh timestamp must satisfy SLA"
        )

        stale_trade = SGXTradeFixtures.get_stale_sla_payload(hours_ago=2.5)
        self.assertFalse(
            DataplexSpecEvaluator.evaluate_freshness(stale_trade["trade_timestamp"], max_age_hours=2.0),
            "Trade older than 2 hours must violate freshness SLA"
        )


if __name__ == "__main__":
    unittest.main()
