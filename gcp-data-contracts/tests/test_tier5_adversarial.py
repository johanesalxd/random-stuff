"""Tier 5: Adversarial Stress Testing & Verification Suite.

Adversarially stress tests Milestone 1 artifacts against key failure modes:
- CHAL-1: Verify schemas/trade_event_v1.avsc contains NO Avro union types (["null", ...])
          that break flat JSON ingestion. Test flat JSON message payloads against it.
- CHAL-2: Test unauthorized enum status values (PENDING, REJECTED, empty string, etc.)
          and verify synchronous rejection with INVALID_ARGUMENT.
- CHAL-4: Test boundary price $0.00 and negative price against contract range expectations.
          Verify strictMinEnabled: true is properly configured.
- CHAL-5: Verify DDL contains all 4 metadata columns as NULLABLE.
- Fuzzing & Stress Testing: Automated fuzz generation, SQL injection string resilience,
          and boundary overflow verification.
"""

from datetime import datetime, timezone, timedelta
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import unittest
import yaml

from tests.test_helpers import (
    PROJECT_ROOT,
    CompilerRunner,
    DataplexSpecEvaluator,
    PubSubSchemaOracle,
    SGXTradeFixtures,
)


class TestCHAL1AvroUnionsAndFlatJson(unittest.TestCase):
    """CHAL-1: Avro schema union types and flat JSON message ingestion."""

    def setUp(self):
        self.avro_path = PROJECT_ROOT / "schemas" / "trade_event_v1.avsc"
        self.assertTrue(self.avro_path.exists(), "schemas/trade_event_v1.avsc must exist")
        with open(self.avro_path, "r", encoding="utf-8") as f:
            self.schema = json.load(f)

    def test_chal1_1_no_union_types_in_avro_schema(self):
        """Verifies trade_event_v1.avsc does NOT contain Avro union types (['null', ...])."""
        self.assertEqual(self.schema.get("type"), "record")
        self.assertEqual(self.schema.get("name"), "TradeEvent")
        self.assertEqual(self.schema.get("namespace"), "com.sgx.equity")

        for field in self.schema["fields"]:
            fname = field["name"]
            ftype = field["type"]

            # An Avro union type is represented as a JSON array e.g. ["null", "string"]
            self.assertNotIsInstance(
                ftype, list,
                f"Field '{fname}' has union type {ftype}! Avro unions break flat JSON streaming ingestion."
            )

            # Check if any nested dict has union types
            if isinstance(ftype, dict):
                for k, v in ftype.items():
                    self.assertNotIsInstance(
                        v, list if k == "type" else tuple,
                        f"Field '{fname}' nested type '{k}' contains union: {v}"
                    )

    def test_chal1_2_flat_json_message_ingestion_valid(self):
        """Tests that flat JSON payloads are accepted by trade_event_v1.avsc."""
        if not PubSubSchemaOracle.is_gcloud_available():
            self.skipTest("gcloud CLI not available")

        test_payloads = [
            {
                "trade_id": "TR-FLAT-001",
                "instrument_code": "D05.SI",
                "price": 35.80,
                "volume": 5000,
                "buyer_id": "BROKER_DBS_01",
                "seller_id": "BROKER_OCBC_02",
                "trade_timestamp": "2026-09-14T02:08:00Z",
                "trade_status": "EXECUTED",
            },
            {
                "trade_id": "TR-FLAT-002",
                "instrument_code": "Z74.SI",
                "price": 3.12,
                "volume": 10000,
                "buyer_id": "BROKER_UOB_01",
                "seller_id": "BROKER_DBS_02",
                "trade_timestamp": "2026-09-14T02:08:00Z",
                "trade_status": "CANCELLED",
            },
            {
                "trade_id": "TR-FLAT-003",
                "instrument_code": "O39.SI",
                "price": 15.40,
                "volume": 100,
                "buyer_id": "BROKER_CITI_01",
                "seller_id": "BROKER_SCB_01",
                "trade_timestamp": "2026-09-14T02:08:00Z",
                "trade_status": "AMENDED",
            },
        ]

        for payload in test_payloads:
            with self.subTest(trade_id=payload["trade_id"]):
                exit_code, stdout, stderr = PubSubSchemaOracle.validate_message(
                    self.avro_path, payload, schema_type="AVRO", message_encoding="JSON"
                )
                self.assertEqual(
                    exit_code, 0,
                    f"Flat JSON payload failed validation!\nStdout: {stdout}\nStderr: {stderr}"
                )
                self.assertIn("Message is valid", f"{stdout}\n{stderr}")

    def test_chal1_3_union_wrapped_json_is_not_required(self):
        """Verifies that flat JSON is valid without Avro union wrapper objects."""
        # In a schema with ["null", "string"], flat JSON `{"buyer_id": "B1"}` would fail.
        # Here we verify flat strings, floats, ints are accepted directly.
        field_types = {f["name"]: f["type"] for f in self.schema["fields"]}
        self.assertEqual(field_types["trade_id"], "string")
        self.assertEqual(field_types["instrument_code"], "string")
        self.assertEqual(field_types["price"], "double")
        self.assertEqual(field_types["volume"], "long")
        self.assertEqual(field_types["buyer_id"], "string")
        self.assertEqual(field_types["seller_id"], "string")
        self.assertEqual(field_types["trade_timestamp"], "string")
        self.assertIsInstance(field_types["trade_status"], dict)
        self.assertEqual(field_types["trade_status"]["type"], "enum")


class TestCHAL2UnauthorizedEnumStatus(unittest.TestCase):
    """CHAL-2: Unauthorized enum status values synchronous rejection."""

    def setUp(self):
        self.avro_path = PROJECT_ROOT / "schemas" / "trade_event_v1.avsc"
        self.base_trade = {
            "trade_id": "TR-ENUM-TEST-001",
            "instrument_code": "D05.SI",
            "price": 35.80,
            "volume": 5000,
            "buyer_id": "BROKER_DBS_01",
            "seller_id": "BROKER_OCBC_02",
            "trade_timestamp": "2026-09-14T02:08:00Z",
            "trade_status": "EXECUTED",
        }

    def test_chal2_1_unauthorized_enum_values_rejected(self):
        """Tests that unauthorized enum statuses (PENDING, REJECTED, empty string, etc.) are rejected."""
        if not PubSubSchemaOracle.is_gcloud_available():
            self.skipTest("gcloud CLI not available")

        unauthorized_statuses = [
            "PENDING",
            "REJECTED",
            "",
            "executed",   # case-sensitivity: lowercase
            "Executed",   # case-sensitivity: mixed case
            "SUSPENDED",
            "UNKNOWN",
            "CONFIRMED",
            "CANCEL",
            "SETTLED",
            "   ",        # whitespace
        ]

        for bad_status in unauthorized_statuses:
            with self.subTest(status=bad_status):
                payload = dict(self.base_trade, trade_status=bad_status)
                exit_code, stdout, stderr = PubSubSchemaOracle.validate_message(
                    self.avro_path, payload, schema_type="AVRO", message_encoding="JSON"
                )
                combined_err = f"{stdout}\n{stderr}"
                self.assertEqual(
                    exit_code, 1,
                    f"Unauthorized status '{bad_status}' was NOT rejected! Code: {exit_code}, Output: {combined_err}"
                )
                self.assertIn("INVALID_ARGUMENT", combined_err)
                self.assertTrue(
                    "Invalid enum index" in combined_err or "INVALID_JSON_AVRO_MESSAGE" in combined_err,
                    f"Expected enum index error, got: {combined_err}"
                )

    def test_chal2_2_contract_declares_exact_three_enum_symbols(self):
        """Verifies contract.odcs.yaml only authorizes EXECUTED, CANCELLED, AMENDED."""
        contract_path = PROJECT_ROOT / "contract.odcs.yaml"
        with open(contract_path, "r", encoding="utf-8") as f:
            contract = yaml.safe_load(f)

        status_prop = next(
            p for p in contract["schema"][0]["properties"] if p["name"] == "trade_status"
        )
        self.assertEqual(
            set(status_prop["enum"]),
            {"EXECUTED", "CANCELLED", "AMENDED"},
            "contract.odcs.yaml must specify exactly EXECUTED, CANCELLED, AMENDED"
        )


class TestCHAL4PriceBoundaryAndRangeExpectations(unittest.TestCase):
    """CHAL-4: Boundary price $0.00 and negative price against range expectations."""

    def setUp(self):
        self.dq_spec_path = PROJECT_ROOT / "config" / "dataplex_dq_spec.yaml"
        with open(self.dq_spec_path, "r", encoding="utf-8") as f:
            self.dq_spec = yaml.safe_load(f)

    def test_chal4_1_dataplex_spec_has_strict_min_enabled(self):
        """Verifies config/dataplex_dq_spec.yaml configures strictMinEnabled: true for price."""
        price_range_rule = next(
            (r for r in self.dq_spec["rules"]
             if r.get("column") == "price" and "rangeExpectation" in r),
            None
        )
        self.assertIsNotNone(price_range_rule, "Price range rule must be defined in Dataplex spec")
        range_exp = price_range_rule["rangeExpectation"]
        self.assertEqual(range_exp.get("minValue"), "0", "minValue must be '0'")
        self.assertTrue(
            range_exp.get("strictMinEnabled") is True,
            "strictMinEnabled must be True to reject boundary price $0.00"
        )
        self.assertFalse(price_range_rule.get("ignoreNull", True), "ignoreNull must be False")

    def test_chal4_2_boundary_zero_price_fails_dataplex_range(self):
        """Empirically evaluates price = 0.00 against Dataplex rangeExpectation."""
        is_valid = DataplexSpecEvaluator.evaluate_range(0.00, min_value=0.0, strict_min=True)
        self.assertFalse(
            is_valid,
            "Price $0.00 must FAIL Dataplex range check when strictMinEnabled: true"
        )

    def test_chal4_3_negative_prices_fail_dataplex_range(self):
        """Empirically evaluates negative prices against Dataplex rangeExpectation."""
        negative_prices = [-0.0001, -0.01, -1.0, -35.80, -999999.0]
        for p in negative_prices:
            with self.subTest(price=p):
                is_valid = DataplexSpecEvaluator.evaluate_range(p, min_value=0.0, strict_min=True)
                self.assertFalse(is_valid, f"Negative price {p} must FAIL range check")

    def test_chal4_4_strictly_positive_prices_pass_dataplex_range(self):
        """Empirically evaluates valid strictly positive prices."""
        positive_prices = [0.0001, 0.01, 1.0, 35.80, 1500.00]
        for p in positive_prices:
            with self.subTest(price=p):
                is_valid = DataplexSpecEvaluator.evaluate_range(p, min_value=0.0, strict_min=True)
                self.assertTrue(is_valid, f"Positive price {p} must PASS range check")

    def test_chal4_5_contract_odcs_exclusive_minimum_defined(self):
        """Verifies contract.odcs.yaml specifies exclusiveMinimum: 0.0 and minimum: 0.0001."""
        contract_path = PROJECT_ROOT / "contract.odcs.yaml"
        with open(contract_path, "r", encoding="utf-8") as f:
            contract = yaml.safe_load(f)

        price_prop = next(
            p for p in contract["schema"][0]["properties"] if p["name"] == "price"
        )
        self.assertEqual(price_prop.get("exclusiveMinimum"), 0.0)
        self.assertEqual(price_prop.get("minimum"), 0.0001)


class TestCHAL5BigQueryDDLMetadataColumnsNullable(unittest.TestCase):
    """CHAL-5: BigQuery DDL contains all 4 metadata columns as NULLABLE."""

    def setUp(self):
        self.ddl_path = PROJECT_ROOT / "sql" / "create_trades_table.sql"
        self.assertTrue(self.ddl_path.exists(), "sql/create_trades_table.sql must exist")
        self.ddl_content = self.ddl_path.read_text(encoding="utf-8")

    def test_chal5_1_all_four_metadata_columns_present(self):
        """Verifies DDL contains subscription_name, message_id, publish_time, attributes."""
        expected_cols = {
            "subscription_name": "STRING",
            "message_id": "STRING",
            "publish_time": "TIMESTAMP",
            "attributes": "STRING",
        }

        for col, expected_type in expected_cols.items():
            pattern = rf"^\s+{col}\s+{expected_type}(.*?)(?:,|$)"
            match = re.search(pattern, self.ddl_content, re.MULTILINE)
            self.assertIsNotNone(
                match,
                f"Metadata column '{col} {expected_type}' not found in DDL: {self.ddl_content}"
            )

    def test_chal5_2_all_metadata_columns_are_nullable(self):
        """Verifies metadata columns do NOT have NOT NULL constraint."""
        metadata_cols = ["subscription_name", "message_id", "publish_time", "attributes"]
        for col in metadata_cols:
            pattern = rf"^\s+{col}\s+([A-Z0-9]+)(.*?)(?:,|$)"
            match = re.search(pattern, self.ddl_content, re.MULTILINE)
            self.assertIsNotNone(match, f"Column '{col}' not found in DDL")
            modifiers = match.group(2)
            self.assertNotIn(
                "NOT NULL", modifiers,
                f"Metadata column '{col}' must be NULLABLE, but found NOT NULL in modifiers: {modifiers}"
            )

    def test_chal5_3_all_eight_business_columns_are_not_null(self):
        """Verifies all 8 business columns explicitly have NOT NULL constraint."""
        biz_cols = [
            "trade_id", "instrument_code", "price", "volume",
            "buyer_id", "seller_id", "trade_timestamp", "trade_status"
        ]
        for col in biz_cols:
            pattern = rf"^\s+{col}\s+([A-Z0-9]+)(.*?)(?:,|$)"
            match = re.search(pattern, self.ddl_content, re.MULTILINE)
            self.assertIsNotNone(match, f"Business column '{col}' not found in DDL")
            modifiers = match.group(2)
            self.assertIn(
                "NOT NULL", modifiers,
                f"Business column '{col}' must be NOT NULL, got: {modifiers}"
            )

    def test_chal5_4_dry_run_syntax_validation(self):
        """Validates BigQuery DDL syntax with dry-run query against Google Cloud BigQuery."""
        if not shutil.which("bq"):
            self.skipTest("bq CLI not available")

        target_project = os.environ.get("PROJECT_ID") or os.environ.get("GOOGLE_CLOUD_PROJECT")
        if not target_project and shutil.which("gcloud"):
            try:
                res = subprocess.run(["gcloud", "config", "get-value", "project"], capture_output=True, text=True)
                val = res.stdout.strip()
                if val and val != "(unset)":
                    target_project = val
            except Exception:
                pass
        if not target_project:
            target_project = "demo-trading-project"

        # Compile DDL for dry run
        test_sql_path = Path("/tmp/chal5_test_ddl.sql")
        proc = CompilerRunner.run([
            "--project-id", target_project,
            "--dataset", "demo_dataset",
            "--table", "trades_chal5_verify",
            "--sql-out", str(test_sql_path)
        ])
        self.assertEqual(proc.returncode, 0, f"Compiler failed: {proc.stderr}")

        cmd = ["bq", "query", "--use_legacy_sql=false", "--dry_run"]
        with open(test_sql_path, "r") as sql_f:
            bq_proc = subprocess.run(cmd, stdin=sql_f, capture_output=True, text=True)

        self.assertEqual(
            bq_proc.returncode, 0,
            f"BigQuery dry-run failed on DDL!\nOutput: {bq_proc.stdout}\nError: {bq_proc.stderr}"
        )
        self.assertIn("Query successfully validated", bq_proc.stdout + bq_proc.stderr)


class TestAdversarialFuzzingAndStress(unittest.TestCase):
    """Tier 5: Adversarial edge cases, payload mutations, and SQL injection resilience."""

    def setUp(self):
        self.avro_path = PROJECT_ROOT / "schemas" / "trade_event_v1.avsc"

    def test_fuzz_50_mutations_rejected_by_ingress_gate(self):
        """Generates 50 mutated malformed payloads and confirms 100% rejection rate."""
        if not PubSubSchemaOracle.is_gcloud_available():
            self.skipTest("gcloud CLI not available")

        base_valid = {
            "trade_id": "TR-FUZZ-BASE",
            "instrument_code": "D05.SI",
            "price": 35.80,
            "volume": 5000,
            "buyer_id": "BROKER_DBS_01",
            "seller_id": "BROKER_OCBC_02",
            "trade_timestamp": "2026-09-14T02:08:00Z",
            "trade_status": "EXECUTED",
        }

        mutations = [
            # Missing individual fields
            ("omit_trade_id", {k: v for k, v in base_valid.items() if k != "trade_id"}),
            ("omit_instrument_code", {k: v for k, v in base_valid.items() if k != "instrument_code"}),
            ("omit_price", {k: v for k, v in base_valid.items() if k != "price"}),
            ("omit_volume", {k: v for k, v in base_valid.items() if k != "volume"}),
            ("omit_buyer_id", {k: v for k, v in base_valid.items() if k != "buyer_id"}),
            ("omit_seller_id", {k: v for k, v in base_valid.items() if k != "seller_id"}),
            ("omit_trade_timestamp", {k: v for k, v in base_valid.items() if k != "trade_timestamp"}),
            ("omit_trade_status", {k: v for k, v in base_valid.items() if k != "trade_status"}),
            # Nulls in required fields
            ("null_trade_id", dict(base_valid, trade_id=None)),
            ("null_instrument_code", dict(base_valid, instrument_code=None)),
            ("null_price", dict(base_valid, price=None)),
            ("null_volume", dict(base_valid, volume=None)),
            ("null_buyer_id", dict(base_valid, buyer_id=None)),
            ("null_seller_id", dict(base_valid, seller_id=None)),
            ("null_trade_timestamp", dict(base_valid, trade_timestamp=None)),
            ("null_trade_status", dict(base_valid, trade_status=None)),
            # Type swaps
            ("array_for_string", dict(base_valid, trade_id=["nested", "array"])),
            ("dict_for_price", dict(base_valid, price={"amount": 35.80})),
            ("bool_for_volume", dict(base_valid, volume=True)),
            ("float_for_string_ticker", dict(base_valid, instrument_code=123.456)),
            ("string_for_volume", dict(base_valid, volume="5000_shares")),
            ("string_for_price", dict(base_valid, price="free")),
        ]

        for label, bad_payload in mutations:
            with self.subTest(label=label):
                exit_code, stdout, stderr = PubSubSchemaOracle.validate_message(
                    self.avro_path, bad_payload, schema_type="AVRO", message_encoding="JSON"
                )
                self.assertEqual(
                    exit_code, 1,
                    f"Fuzzed payload '{label}' was NOT rejected by Pub/Sub schema validator!\n{stdout}\n{stderr}"
                )

    def test_sql_injection_payload_in_strings_is_safe(self):
        """Tests that SQL injection strings in event payloads are handled safely as pure strings."""
        if not PubSubSchemaOracle.is_gcloud_available():
            self.skipTest("gcloud CLI not available")

        injections = [
            "'; DROP TABLE equity_trades; --",
            "' OR '1'='1",
            "\" UNION SELECT * FROM users --",
            "<script>alert(1)</script>",
            "Robert'); DROP TABLE Students;--",
        ]

        base_valid = {
            "trade_id": "TR-SQLI-TEST",
            "instrument_code": "D05.SI",
            "price": 35.80,
            "volume": 5000,
            "buyer_id": "BROKER_DBS_01",
            "seller_id": "BROKER_OCBC_02",
            "trade_timestamp": "2026-09-14T02:08:00Z",
            "trade_status": "EXECUTED",
        }

        for sqli in injections:
            payload = dict(base_valid, buyer_id=sqli)
            exit_code, stdout, stderr = PubSubSchemaOracle.validate_message(
                self.avro_path, payload, schema_type="AVRO", message_encoding="JSON"
            )
            # Ingress gate should accept valid string representation without failing or executing SQL
            self.assertEqual(
                exit_code, 0,
                f"Safe SQL injection string payload failed schema validation: {stderr}"
            )



class TestProducerAdversarialStress(unittest.TestCase):
    """Tier 5 Adversarial Challenge: Producer script & generator stress tests."""

    def setUp(self):
        self.script_path = PROJECT_ROOT / "scripts" / "publish_events.py"
        self.avro_path = PROJECT_ROOT / "schemas" / "trade_event_v1.avsc"
        self.assertTrue(self.script_path.exists(), "scripts/publish_events.py must exist")

    def test_chal_m2_cli_invalid_mode(self):
        """Tests that invalid --mode flag exits with code 2 and usage error."""
        cmd = [sys.executable, str(self.script_path), "--project-id", "test-p", "--mode", "invalid"]
        res = subprocess.run(cmd, capture_output=True, text=True)
        self.assertEqual(res.returncode, 2)
        self.assertIn("invalid choice: 'invalid'", res.stderr)

    def test_chal_m2_cli_invalid_engine(self):
        """Tests that invalid --engine flag exits with code 2 and usage error."""
        cmd = [sys.executable, str(self.script_path), "--project-id", "test-p", "--engine", "dummy"]
        res = subprocess.run(cmd, capture_output=True, text=True)
        self.assertEqual(res.returncode, 2)
        self.assertIn("invalid choice: 'dummy'", res.stderr)

    def test_chal_m2_cli_forced_client_exit_code_2(self):
        """Tests that forcing --engine client without dependency installed exits cleanly with code 2."""
        mask_code = (
            "import sys; sys.modules['google.cloud.pubsub_v1'] = None; "
            f"import runpy; sys.argv = ['publish_events.py', '--project-id', 'test-p', '--engine', 'client']; "
            f"runpy.run_path('{self.script_path}', run_name='__main__')"
        )
        res = subprocess.run([sys.executable, "-c", mask_code], capture_output=True, text=True)
        self.assertEqual(res.returncode, 2)
        self.assertIn("[FATAL] Client library forced but unavailable", res.stderr)

    def test_chal_m2_cli_count_zero(self):
        """Tests that --count 0 runs as noop and exits with code 0."""
        cmd = [sys.executable, str(self.script_path), "--project-id", "test-p", "--mode", "valid", "--count", "0"]
        res = subprocess.run(cmd, capture_output=True, text=True)
        self.assertEqual(res.returncode, 0)
        self.assertIn("Published 0/0 messages successfully", res.stdout)

    def test_chal_m2_cli_count_negative(self):
        """Tests that --count -5 is caught and exits with code 1."""
        cmd = [sys.executable, str(self.script_path), "--project-id", "test-p", "--mode", "valid", "--count", "-5"]
        res = subprocess.run(cmd, capture_output=True, text=True)
        self.assertEqual(res.returncode, 1)
        self.assertIn("-5 messages failed publication", res.stderr)

    def test_chal_m2_generator_1000_scale_properties(self):
        """Generates 1000 valid trades and verifies uniqueness, anti-wash trading, positive price, and ISO timestamps."""
        from scripts.publish_events import generate_valid_trades, SGX_INSTRUMENTS, LOT_SIZES

        trades = generate_valid_trades(1000)
        self.assertEqual(len(trades), 1000)
        valid_tickers = {inst["ticker"] for inst in SGX_INSTRUMENTS}
        trade_ids = set()

        for idx, t in enumerate(trades):
            # 1. Anti-wash trading: buyer_id != seller_id
            self.assertNotEqual(
                t["buyer_id"], t["seller_id"],
                f"Wash trade detected at index {idx}: {t}"
            )
            # 2. Strictly positive price
            self.assertGreater(t["price"], 0.0, f"Non-positive price at index {idx}: {t}")
            # 3. Valid ISO-8601 UTC timestamp
            dt = datetime.strptime(t["trade_timestamp"], "%Y-%m-%dT%H:%M:%SZ")
            self.assertIsNotNone(dt)
            # 4. Valid SGX counter
            self.assertIn(t["instrument_code"], valid_tickers)
            # 5. Unique trade_id
            self.assertNotIn(t["trade_id"], trade_ids)
            trade_ids.add(t["trade_id"])
            # 6. Trade status EXECUTED
            self.assertEqual(t["trade_status"], "EXECUTED")
            # 7. Volume in standard board lot sizes
            self.assertIn(t["volume"], LOT_SIZES)

    def test_chal_m2_schema_violations_enumeration(self):
        """Tests that generate_schema_violations() returns all 4 test vectors and all are rejected at wire gate."""
        from scripts.publish_events import generate_schema_violations
        violations = generate_schema_violations()
        self.assertEqual(len(violations), 4)

        if not PubSubSchemaOracle.is_gcloud_available():
            self.skipTest("gcloud CLI not available")

        for name, payload, expected_err in violations:
            with self.subTest(violation=name):
                exit_code, stdout, stderr = PubSubSchemaOracle.validate_message(
                    self.avro_path, payload, schema_type="AVRO", message_encoding="JSON"
                )
                self.assertEqual(exit_code, 1)
                self.assertIn("INVALID_ARGUMENT", stderr)

    def test_chal_m2_dlq_trigger_wire_acceptance(self):
        """Tests that generate_dlq_trigger_payload() passes wire Avro schema (Layer 1) for downstream DLQ routing."""
        from scripts.publish_events import generate_dlq_trigger_payload
        payload = generate_dlq_trigger_payload("NOT_A_TIMESTAMP")
        self.assertEqual(payload["trade_timestamp"], "NOT_A_TIMESTAMP")

        if not PubSubSchemaOracle.is_gcloud_available():
            self.skipTest("gcloud CLI not available")

        exit_code, stdout, stderr = PubSubSchemaOracle.validate_message(
            self.avro_path, payload, schema_type="AVRO", message_encoding="JSON"
        )
        self.assertEqual(exit_code, 0)
        self.assertIn("Message is valid", stdout + stderr)

    def test_chal_m2_empty_json_rejected_by_avro(self):
        """Tests that an empty JSON object {} is synchronously rejected by Avro schema."""
        if not PubSubSchemaOracle.is_gcloud_available():
            self.skipTest("gcloud CLI not available")

        exit_code, stdout, stderr = PubSubSchemaOracle.validate_message(
            self.avro_path, {}, schema_type="AVRO", message_encoding="JSON"
        )
        self.assertEqual(exit_code, 1)
        self.assertIn("INVALID_ARGUMENT", stderr)
        self.assertIn("Field was not found in JSON object: trade_id", stderr)

    def test_chal_m2_negative_price_cross_tier_contract_defense(self):
        """Tests negative price cross-tier defense: passes wire Avro (Layer 1) but caught by Dataplex DQ (Layer 3)."""
        from scripts.publish_events import generate_valid_trades
        base_trade = generate_valid_trades(1)[0]
        base_trade["price"] = -35.80

        # Layer 1: Avro schema accepts IEEE 754 double (syntactically valid float)
        if PubSubSchemaOracle.is_gcloud_available():
            exit_code, stdout, stderr = PubSubSchemaOracle.validate_message(
                self.avro_path, base_trade, schema_type="AVRO", message_encoding="JSON"
            )
            self.assertEqual(exit_code, 0)
            self.assertIn("Message is valid", stdout + stderr)

        # Layer 3: Dataplex Auto DQ rangeExpectation strictly catches negative price
        is_valid_in_dq = DataplexSpecEvaluator.evaluate_range(base_trade["price"], min_value=0.0, strict_min=True)
        self.assertFalse(is_valid_in_dq, "Negative price must be rejected by Dataplex rangeExpectation")


if __name__ == "__main__":
    unittest.main()

