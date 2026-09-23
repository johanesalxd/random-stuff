"""Tier 1: Feature Coverage Test Suite.

Covers all 5 core features with at least 5 isolated tests per feature:
- Feature 1: Open Data Contract Standard (contract.odcs.yaml)
- Feature 2: Pure-Python Contract Compiler (compile_contract.py)
- Feature 3: Pub/Sub Avro Schema (schemas/trade_event_v1.avsc)
- Feature 4: BigQuery Table DDL (sql/create_trades_table.sql)
- Feature 5: Dataplex Auto Data Quality Spec (config/dataplex_dq_spec.yaml)
"""

import json
from pathlib import Path
import re
import shutil
import tempfile
import unittest
import yaml

from tests.test_helpers import (
    PROJECT_ROOT,
    CompilerRunner,
    PubSubSchemaOracle,
)


class TestFeature1ODCSContract(unittest.TestCase):
    """Feature 1: Tests for Open Data Contract Standard specification (contract.odcs.yaml)."""

    def setUp(self):
        self.contract_path = PROJECT_ROOT / "contract.odcs.yaml"

    def test_1_1_odcs_file_exists_and_parses_yaml(self):
        """Validates contract.odcs.yaml exists and parses cleanly as YAML."""
        self.assertTrue(
            self.contract_path.exists(),
            f"contract.odcs.yaml not found at {self.contract_path}. Feature 1 implementation pending."
        )
        with open(self.contract_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        self.assertIsInstance(data, dict, "contract.odcs.yaml root must be a YAML mapping/dict")

    def test_1_2_odcs_top_level_metadata(self):
        """Validates top-level ODCS v3.0 metadata fields."""
        if not self.contract_path.exists():
            self.skipTest("contract.odcs.yaml not yet present")
        with open(self.contract_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        self.assertIn("apiVersion", data, "Missing apiVersion in contract")
        self.assertTrue(str(data["apiVersion"]).startswith("3."), f"Expected ODCS v3.x, got {data.get('apiVersion')}")
        self.assertEqual(data.get("kind"), "DataContract", "kind must be DataContract")
        self.assertIn("id", data, "Missing contract id URN")
        self.assertIn("name", data, "Missing contract name")
        self.assertIn("version", data, "Missing contract version")
        self.assertIn("status", data, "Missing contract status")

    def test_1_3_odcs_schema_properties_completeness(self):
        """Validates all 8 required SGX equity trade fields are defined with schema metadata."""
        if not self.contract_path.exists():
            self.skipTest("contract.odcs.yaml not yet present")
        with open(self.contract_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        # Handle ODCS v3 schema list
        schema_entries = data.get("schema") or data.get("models")
        self.assertIsNotNone(schema_entries, "Missing schema or models in contract")
        self.assertTrue(len(schema_entries) > 0, "Schema must contain at least one entity")

        first_entity = schema_entries[0] if isinstance(schema_entries, list) else list(schema_entries.values())[0]
        properties = first_entity.get("properties") or first_entity.get("fields")
        self.assertIsNotNone(properties, "Entity must define properties or fields")

        # Normalize properties map
        prop_map = {}
        if isinstance(properties, list):
            for p in properties:
                prop_map[p["name"]] = p
        elif isinstance(properties, dict):
            prop_map = properties

        expected_fields = [
            "trade_id", "instrument_code", "price", "volume",
            "buyer_id", "seller_id", "trade_timestamp", "trade_status"
        ]
        for field in expected_fields:
            self.assertIn(field, prop_map, f"Required field '{field}' missing from contract properties")
            field_def = prop_map[field]
            self.assertTrue(
                field_def.get("required", False),
                f"Field '{field}' must have required: true"
            )

    def test_1_4_odcs_freshness_sla_definition(self):
        """Validates freshness SLA definition on trade_timestamp within 2 hours."""
        if not self.contract_path.exists():
            self.skipTest("contract.odcs.yaml not yet present")
        with open(self.contract_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        sla = data.get("sla") or data.get("servicelevels") or {}
        freshness = sla.get("freshness") or {}
        self.assertTrue(
            bool(freshness),
            "contract.odcs.yaml must specify freshness SLA under sla.freshness"
        )
        max_age = freshness.get("maxAge") or freshness.get("threshold") or ""
        self.assertTrue(
            "2h" in str(max_age).lower() or "2 hour" in str(max_age).lower() or "120" in str(max_age),
            f"Freshness SLA should mandate <= 2h latency, got: {max_age}"
        )

    def test_1_5_odcs_quality_rules_completeness(self):
        """Validates contract quality rules contain completeness, range, set, and integrity rules."""
        if not self.contract_path.exists():
            self.skipTest("contract.odcs.yaml not yet present")
        with open(self.contract_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        quality_rules = data.get("quality") or []
        self.assertTrue(len(quality_rules) > 0, "contract.odcs.yaml must define quality rules")

        # Collect rule types, columns, and descriptions
        rule_text = json.dumps(quality_rules).lower()
        self.assertIn("trade_id", rule_text, "Quality rules must reference trade_id")
        self.assertIn("price", rule_text, "Quality rules must reference price")
        self.assertIn("volume", rule_text, "Quality rules must reference volume")
        self.assertTrue(
            "buyer_id" in rule_text and "seller_id" in rule_text,
            "Quality rules must include anti-wash trading comparison between buyer_id and seller_id"
        )


class TestFeature2ContractCompiler(unittest.TestCase):
    """Feature 2: Tests for pure-Python contract compiler (compile_contract.py)."""

    def setUp(self):
        self.compiler_path = CompilerRunner.compiler_path()
        self.temp_dir = Path(tempfile.mkdtemp(prefix="sgx_e2e_compiler_"))

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_2_1_compiler_cli_help(self):
        """Validates compiler displays CLI help usage and exits with code 0."""
        self.assertTrue(
            self.compiler_path.exists(),
            f"compile_contract.py not found at {self.compiler_path}. Feature 2 implementation pending."
        )
        proc = CompilerRunner.run(["--help"])
        self.assertEqual(proc.returncode, 0, f"Compiler --help failed with stderr: {proc.stderr}")
        self.assertIn("contract", proc.stdout.lower(), "Help text should mention contract")

    def test_2_2_compiler_compiles_default_artifacts(self):
        """Validates compiler executes against contract.odcs.yaml with code 0."""
        if not self.compiler_path.exists() or not (PROJECT_ROOT / "contract.odcs.yaml").exists():
            self.skipTest("compile_contract.py or contract.odcs.yaml not yet present")
        proc = CompilerRunner.run()
        self.assertEqual(proc.returncode, 0, f"Compiler failed with stderr: {proc.stderr}")

    def test_2_3_compiler_custom_output_flags(self):
        """Validates custom output destination flags (--avro-out, --sql-out, --dataplex-out)."""
        if not self.compiler_path.exists() or not (PROJECT_ROOT / "contract.odcs.yaml").exists():
            self.skipTest("compile_contract.py or contract.odcs.yaml not yet present")

        custom_avro = self.temp_dir / "custom_schema.avsc"
        custom_sql = self.temp_dir / "custom_ddl.sql"
        custom_dq = self.temp_dir / "custom_dq.yaml"

        proc = CompilerRunner.run([
            "--avro-out", str(custom_avro),
            "--sql-out", str(custom_sql),
            "--dataplex-out", str(custom_dq)
        ])
        self.assertEqual(proc.returncode, 0, f"Compiler failed with custom flags: {proc.stderr}")
        self.assertTrue(custom_avro.exists(), "Custom Avro output file was not generated")
        self.assertTrue(custom_sql.exists(), "Custom SQL DDL output file was not generated")
        self.assertTrue(custom_dq.exists(), "Custom Dataplex DQ output file was not generated")

    def test_2_4_compiler_custom_project_dataset_table(self):
        """Validates parameter substitution for GCP project, dataset, and table in DDL."""
        if not self.compiler_path.exists() or not (PROJECT_ROOT / "contract.odcs.yaml").exists():
            self.skipTest("compile_contract.py or contract.odcs.yaml not yet present")

        custom_sql = self.temp_dir / "substituted_ddl.sql"
        proj = "sgx-prod-prj-2026"
        ds = "market_data_sg"
        tbl = "sgx_trades_table"

        proc = CompilerRunner.run([
            "--sql-out", str(custom_sql),
            "--project-id", proj,
            "--dataset", ds,
            "--table", tbl
        ])
        self.assertEqual(proc.returncode, 0, f"Compiler execution failed: {proc.stderr}")
        self.assertTrue(custom_sql.exists())
        sql_content = custom_sql.read_text(encoding="utf-8")
        expected_ref = f"{proj}.{ds}.{tbl}"
        self.assertIn(
            expected_ref, sql_content,
            f"Expected table reference '{expected_ref}' in generated SQL DDL"
        )

    def test_2_5_compiler_deterministic_idempotency(self):
        """Validates that consecutive compiler runs generate byte-identical output artifacts."""
        if not self.compiler_path.exists() or not (PROJECT_ROOT / "contract.odcs.yaml").exists():
            self.skipTest("compile_contract.py or contract.odcs.yaml not yet present")

        run1_dir = self.temp_dir / "run1"
        run2_dir = self.temp_dir / "run2"
        run1_dir.mkdir()
        run2_dir.mkdir()

        # Run 1
        CompilerRunner.run([
            "--avro-out", str(run1_dir / "schema.avsc"),
            "--sql-out", str(run1_dir / "ddl.sql"),
            "--dataplex-out", str(run1_dir / "dq.yaml")
        ])

        # Run 2
        CompilerRunner.run([
            "--avro-out", str(run2_dir / "schema.avsc"),
            "--sql-out", str(run2_dir / "ddl.sql"),
            "--dataplex-out", str(run2_dir / "dq.yaml")
        ])

        for fname in ["schema.avsc", "ddl.sql", "dq.yaml"]:
            f1 = (run1_dir / fname).read_bytes()
            f2 = (run2_dir / fname).read_bytes()
            self.assertEqual(
                f1, f2,
                f"Compiler output for {fname} is non-deterministic between runs!"
            )


class TestFeature3AvroSchema(unittest.TestCase):
    """Feature 3: Tests for Pub/Sub Avro Schema (schemas/trade_event_v1.avsc)."""

    def setUp(self):
        self.avro_path = PROJECT_ROOT / "schemas" / "trade_event_v1.avsc"

    def test_3_1_avro_schema_file_and_json_validity(self):
        """Validates that schemas/trade_event_v1.avsc exists and is valid JSON."""
        self.assertTrue(
            self.avro_path.exists(),
            f"Avro schema not found at {self.avro_path}. Feature 3 implementation pending."
        )
        with open(self.avro_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertIsInstance(data, dict, "Avro schema root must be a JSON object")

    def test_3_2_avro_record_metadata(self):
        """Validates top-level Avro record type, name, and namespace."""
        if not self.avro_path.exists():
            self.skipTest("schemas/trade_event_v1.avsc not yet present")
        with open(self.avro_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.assertEqual(data.get("type"), "record", "Top-level Avro type must be 'record'")
        self.assertEqual(data.get("name"), "TradeEvent", "Record name must be 'TradeEvent'")
        self.assertEqual(data.get("namespace"), "com.sgx.equity", "Record namespace must be 'com.sgx.equity'")

    def test_3_3_avro_primitive_fields(self):
        """Validates all 8 trade fields are defined with correct Avro primitive types."""
        if not self.avro_path.exists():
            self.skipTest("schemas/trade_event_v1.avsc not yet present")
        with open(self.avro_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        field_map = {f["name"]: f for f in data.get("fields", [])}
        expected_types = {
            "trade_id": "string",
            "instrument_code": "string",
            "price": "double",
            "volume": "long",
            "buyer_id": "string",
            "seller_id": "string",
            "trade_timestamp": "string"
        }
        for name, exp_type in expected_types.items():
            self.assertIn(name, field_map, f"Field '{name}' missing from Avro schema")
            actual_type = field_map[name]["type"]
            self.assertEqual(
                actual_type, exp_type,
                f"Field '{name}' expected type '{exp_type}', got '{actual_type}'"
            )

    def test_3_4_avro_trade_status_enum(self):
        """Validates trade_status field is modeled as an enum with required symbols."""
        if not self.avro_path.exists():
            self.skipTest("schemas/trade_event_v1.avsc not yet present")
        with open(self.avro_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        field_map = {f["name"]: f for f in data.get("fields", [])}
        self.assertIn("trade_status", field_map, "Missing 'trade_status' field")
        status_type = field_map["trade_status"]["type"]
        self.assertIsInstance(status_type, dict, "trade_status type should be an inline enum definition")
        self.assertEqual(status_type.get("type"), "enum")
        symbols = status_type.get("symbols", [])
        for expected_symbol in ["EXECUTED", "CANCELLED", "AMENDED"]:
            self.assertIn(
                expected_symbol, symbols,
                f"Symbol '{expected_symbol}' missing from TradeStatus enum"
            )

    def test_3_5_avro_pubsub_schema_oracle_validation(self):
        """Validates schema against Google Cloud Pub/Sub Schema Registry CLI oracle."""
        if not self.avro_path.exists():
            self.skipTest("schemas/trade_event_v1.avsc not yet present")
        if not PubSubSchemaOracle.is_gcloud_available():
            self.skipTest("gcloud SDK not available")

        exit_code, stdout, stderr = PubSubSchemaOracle.validate_schema(self.avro_path, schema_type="AVRO")
        output = f"{stdout}\n{stderr}"
        self.assertEqual(
            exit_code, 0,
            f"gcloud pubsub schemas validate-schema failed on {self.avro_path}!\nStderr: {stderr}\nStdout: {stdout}"
        )
        self.assertIn("Schema is valid", output)


class TestFeature4BigQueryTableDDL(unittest.TestCase):
    """Feature 4: Tests for BigQuery Table DDL (sql/create_trades_table.sql)."""

    def setUp(self):
        self.sql_path = PROJECT_ROOT / "sql" / "create_trades_table.sql"

    def test_4_1_ddl_statement_syntax(self):
        """Validates sql/create_trades_table.sql exists and contains CREATE OR REPLACE TABLE."""
        self.assertTrue(
            self.sql_path.exists(),
            f"SQL DDL not found at {self.sql_path}. Feature 4 implementation pending."
        )
        content = self.sql_path.read_text(encoding="utf-8").upper()
        self.assertTrue(
            "CREATE TABLE IF NOT EXISTS" in content or "CREATE OR REPLACE TABLE" in content,
            "DDL must contain CREATE TABLE statement",
        )

    def test_4_2_ddl_trade_columns_and_types(self):
        """Validates column definitions and types in BigQuery DDL."""
        if not self.sql_path.exists():
            self.skipTest("sql/create_trades_table.sql not yet present")
        content = self.sql_path.read_text(encoding="utf-8")

        expected_columns = [
            ("trade_id", "STRING"),
            ("instrument_code", "STRING"),
            ("price", "NUMERIC"),
            ("volume", "INT64"),
            ("buyer_id", "STRING"),
            ("seller_id", "STRING"),
            ("trade_timestamp", "TIMESTAMP"),
            ("trade_status", "STRING")
        ]
        for col_name, col_type in expected_columns:
            pattern = re.compile(rf"\b{col_name}\b\s+{col_type}\b", re.IGNORECASE)
            self.assertTrue(
                pattern.search(content),
                f"Column '{col_name} {col_type}' not found in DDL: {content}"
            )

    def test_4_3_ddl_not_null_constraints(self):
        """Validates NOT NULL constraints on critical financial execution columns."""
        if not self.sql_path.exists():
            self.skipTest("sql/create_trades_table.sql not yet present")
        content = self.sql_path.read_text(encoding="utf-8")

        critical_cols = ["trade_id", "instrument_code", "price", "volume", "buyer_id", "seller_id", "trade_timestamp"]
        for col in critical_cols:
            pattern = re.compile(rf"\b{col}\b[^\n,]+NOT\s+NULL", re.IGNORECASE)
            self.assertTrue(
                pattern.search(content),
                f"Column '{col}' must be declared with NOT NULL constraint in DDL"
            )

    def test_4_4_ddl_partitioning_and_clustering(self):
        """Validates PARTITION BY trade_timestamp (DAY) and CLUSTER BY clauses."""
        if not self.sql_path.exists():
            self.skipTest("sql/create_trades_table.sql not yet present")
        content = self.sql_path.read_text(encoding="utf-8").upper()

        self.assertIn("PARTITION BY", content, "DDL must contain PARTITION BY clause")
        self.assertIn("TRADE_TIMESTAMP", content, "Partitioning must be on trade_timestamp")
        self.assertIn("CLUSTER BY", content, "DDL must contain CLUSTER BY clause")
        self.assertIn("INSTRUMENT_CODE", content, "Clustering must include instrument_code")

    def test_4_5_ddl_metadata_columns_for_pubsub(self):
        """Validates BigQuery direct subscription metadata columns for Storage Write API."""
        if not self.sql_path.exists():
            self.skipTest("sql/create_trades_table.sql not yet present")
        content = self.sql_path.read_text(encoding="utf-8")

        metadata_cols = ["subscription_name", "message_id", "publish_time", "attributes"]
        for col in metadata_cols:
            self.assertIn(
                col, content.lower(),
                f"Storage Write API metadata column '{col}' missing from table DDL"
            )


class TestFeature5DataplexDQSpec(unittest.TestCase):
    """Feature 5: Tests for Dataplex Auto Data Quality Spec (config/dataplex_dq_spec.yaml)."""

    def setUp(self):
        self.dq_path = PROJECT_ROOT / "config" / "dataplex_dq_spec.yaml"

    def test_5_1_dq_spec_file_and_yaml_validity(self):
        """Validates config/dataplex_dq_spec.yaml exists and parses cleanly as YAML."""
        self.assertTrue(
            self.dq_path.exists(),
            f"Dataplex DQ spec not found at {self.dq_path}. Feature 5 implementation pending."
        )
        with open(self.dq_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        self.assertIsInstance(data, dict, "Dataplex DQ spec root must be a YAML mapping")

    def test_5_2_dq_spec_rules_container(self):
        """Validates rules list exists and contains Dataplex Auto DQ rule definitions."""
        if not self.dq_path.exists():
            self.skipTest("config/dataplex_dq_spec.yaml not yet present")
        with open(self.dq_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        rules = data.get("rules")
        self.assertIsInstance(rules, list, "Dataplex DQ spec must have top-level 'rules' list")
        self.assertTrue(len(rules) >= 4, f"Expected at least 4 Dataplex rules, got {len(rules)}")

    def test_5_3_dq_spec_completeness_rules(self):
        """Validates nonNullExpectation completeness rules for critical columns."""
        if not self.dq_path.exists():
            self.skipTest("config/dataplex_dq_spec.yaml not yet present")
        with open(self.dq_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        rules = data.get("rules", [])
        non_null_cols = set()
        for r in rules:
            if "nonNullExpectation" in r:
                col = r.get("column")
                if col:
                    non_null_cols.add(col)
                self.assertEqual(r.get("dimension"), "COMPLETENESS", f"Rule for {col} should have dimension COMPLETENESS")

        for exp_col in ["trade_id", "instrument_code", "price", "volume"]:
            self.assertIn(
                exp_col, non_null_cols,
                f"Missing nonNullExpectation rule for critical column '{exp_col}'"
            )

    def test_5_4_dq_spec_range_and_set_rules(self):
        """Validates rangeExpectation (price > 0, volume > 0) and setExpectation (trade_status)."""
        if not self.dq_path.exists():
            self.skipTest("config/dataplex_dq_spec.yaml not yet present")
        with open(self.dq_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        rules = data.get("rules", [])
        range_rules = [r for r in rules if "rangeExpectation" in r]
        set_rules = [r for r in rules if "setExpectation" in r]

        self.assertTrue(len(range_rules) >= 2, "Expected rangeExpectation rules for price and volume")
        range_cols = {r.get("column"): r["rangeExpectation"] for r in range_rules}
        self.assertIn("price", range_cols)
        self.assertIn("volume", range_cols)

        # Check strict min enabled
        self.assertTrue(
            range_cols["price"].get("strictMinEnabled", False),
            "Price rangeExpectation must have strictMinEnabled: true (price > 0)"
        )

        # Check set rule for status
        self.assertTrue(len(set_rules) >= 1, "Expected setExpectation rule for trade_status")
        status_rule = set_rules[0]
        self.assertEqual(status_rule.get("column"), "trade_status")
        values = status_rule["setExpectation"].get("values", [])
        self.assertTrue(set(["EXECUTED", "CANCELLED", "AMENDED"]).issubset(set(values)))

    def test_5_5_dq_spec_freshness_and_anti_wash_rules(self):
        """Validates freshness SLA rule and anti-wash trading rule (buyer_id != seller_id)."""
        if not self.dq_path.exists():
            self.skipTest("config/dataplex_dq_spec.yaml not yet present")
        with open(self.dq_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        rules = data.get("rules", [])
        rule_yaml_str = yaml.dump(rules)

        # Freshness SLA validation
        self.assertTrue(
            "freshness" in rule_yaml_str.lower() or "timestamp" in rule_yaml_str.lower(),
            "Missing Freshness SLA rule in Dataplex spec"
        )
        self.assertTrue(
            "2 hour" in rule_yaml_str.lower() or "2h" in rule_yaml_str.lower() or "interval 2 hour" in rule_yaml_str.lower(),
            "Freshness rule must reference 2-hour SLA interval"
        )

        # Anti-wash trading rule validation
        self.assertTrue(
            "buyer_id != seller_id" in rule_yaml_str or "buyer_id = seller_id" in rule_yaml_str,
            "Missing anti-wash trading rule comparing buyer_id and seller_id"
        )


if __name__ == "__main__":
    unittest.main()
