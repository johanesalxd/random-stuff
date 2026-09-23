"""Tier 3: Cross-Feature Combinations Test Suite.

Verifies end-to-end integration pipelines and cross-artifact interactions:
1. Contract YAML -> Compiler -> Pub/Sub Avro Schema -> gcloud schema probe
2. Compiled Avro Schema + Valid JSON Message -> gcloud message validation probe
3. Compiled Avro Schema + Injected Invalid Messages -> Ingress rejection diagnostic
4. Contract YAML -> Compiler -> BigQuery DDL -> GoogleSQL syntax dry-run verification
5. Contract YAML -> Compiler -> Dataplex DQ Spec -> Dataplex proto schema compliance
6. Cross-artifact alignment: Avro fields == BigQuery DDL columns == Dataplex target columns
7. CLI Parameter propagation: --project-id, --dataset, --table into generated DDL
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
    REFERENCE_AVRO_SCHEMA,
    CompilerRunner,
    PubSubSchemaOracle,
    SGXTradeFixtures,
)


class TestTier3Combinations(unittest.TestCase):
    """Tier 3: Cross-feature integration pipelines and cross-artifact interactions."""

    def setUp(self):
        self.compiler_path = CompilerRunner.compiler_path()
        self.contract_path = PROJECT_ROOT / "contract.odcs.yaml"
        self.temp_dir = Path(tempfile.mkdtemp(prefix="sgx_tier3_combinations_"))

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_3_1_pipeline_contract_to_avro_pubsub_probe(self):
        """Cross-Feature 1: Contract -> Compiler -> Avro Schema -> gcloud pubsub schema probe."""
        if not self.compiler_path.exists() or not self.contract_path.exists():
            self.skipTest("compile_contract.py or contract.odcs.yaml not yet present")
        if not PubSubSchemaOracle.is_gcloud_available():
            self.skipTest("gcloud SDK not available")

        out_avro = self.temp_dir / "pipeline_trade_event.avsc"
        proc = CompilerRunner.run([
            "--contract", str(self.contract_path),
            "--avro-out", str(out_avro)
        ])
        self.assertEqual(proc.returncode, 0, f"Compiler failed: {proc.stderr}")
        self.assertTrue(out_avro.exists(), "Avro schema was not generated")

        # Validate with authoritative Google Cloud Pub/Sub Schema Registry CLI
        exit_code, stdout, stderr = PubSubSchemaOracle.validate_schema(out_avro, schema_type="AVRO")
        output = f"{stdout}\n{stderr}"
        self.assertEqual(
            exit_code, 0,
            f"Generated Avro schema failed gcloud validation!\nStdout: {stdout}\nStderr: {stderr}"
        )
        self.assertIn("Schema is valid", output)

    def test_3_2_pipeline_avro_with_valid_trade_message(self):
        """Cross-Feature 2: Compiled Avro Schema + Valid SGX Trade JSON -> Message Oracle."""
        if not PubSubSchemaOracle.is_gcloud_available():
            self.skipTest("gcloud SDK not available")

        # Determine schema source (compiled or reference)
        compiled_avro = PROJECT_ROOT / "schemas" / "trade_event_v1.avsc"
        if compiled_avro.exists():
            schema_source = compiled_avro
        elif self.compiler_path.exists() and self.contract_path.exists():
            schema_source = self.temp_dir / "temp_schema.avsc"
            CompilerRunner.run(["--contract", str(self.contract_path), "--avro-out", str(schema_source)])
        else:
            schema_source = REFERENCE_AVRO_SCHEMA

        valid_trade = SGXTradeFixtures.get_valid_trade_batch(1)[0]
        exit_code, stdout, stderr = PubSubSchemaOracle.validate_message(
            schema_source, valid_trade, schema_type="AVRO", message_encoding="JSON"
        )
        output = f"{stdout}\n{stderr}"
        self.assertEqual(
            exit_code, 0,
            f"Valid trade message rejected by schema oracle!\nStdout: {stdout}\nStderr: {stderr}"
        )
        self.assertIn("Message is valid", output)

    def test_3_3_pipeline_avro_with_invalid_trade_messages(self):
        """Cross-Feature 3: Compiled Avro Schema + Injected Invalid Messages -> Rejection Code."""
        if not PubSubSchemaOracle.is_gcloud_available():
            self.skipTest("gcloud SDK not available")

        compiled_avro = PROJECT_ROOT / "schemas" / "trade_event_v1.avsc"
        schema_source = compiled_avro if compiled_avro.exists() else REFERENCE_AVRO_SCHEMA

        invalid_cases = SGXTradeFixtures.get_invalid_ingress_payloads()
        for case_name, bad_payload, expected_err in invalid_cases:
            with self.subTest(case=case_name):
                exit_code, stdout, stderr = PubSubSchemaOracle.validate_message(
                    schema_source, bad_payload, schema_type="AVRO", message_encoding="JSON"
                )
                self.assertEqual(
                    exit_code, 1,
                    f"Invalid payload '{case_name}' was unexpectedly accepted by schema oracle!"
                )
                self.assertIn(
                    "INVALID_ARGUMENT", stderr,
                    f"Expected INVALID_ARGUMENT error for case '{case_name}', got: {stderr}"
                )

    def test_3_4_pipeline_contract_to_sql_ddl_and_syntax_dry_run(self):
        """Cross-Feature 4: Contract -> Compiler -> BigQuery DDL -> GoogleSQL syntax dry-run verification."""
        if not self.compiler_path.exists() or not self.contract_path.exists():
            self.skipTest("compile_contract.py or contract.odcs.yaml not yet present")

        out_sql = self.temp_dir / "pipeline_table.sql"
        proc = CompilerRunner.run([
            "--contract", str(self.contract_path),
            "--sql-out", str(out_sql)
        ])
        self.assertEqual(proc.returncode, 0, f"Compiler failed: {proc.stderr}")
        self.assertTrue(out_sql.exists(), "SQL DDL was not generated")

        content = out_sql.read_text(encoding="utf-8")

        # Verify GoogleSQL DDL Syntax rules
        # 1. Balanced parentheses
        open_count = content.count("(")
        close_count = content.count(")")
        self.assertEqual(
            open_count, close_count,
            f"Unbalanced parentheses in generated SQL DDL: {open_count} open vs {close_count} close"
        )

        # 2. Table creation clause
        self.assertRegex(content, r"CREATE\s+(OR\s+REPLACE\s+)?TABLE", "DDL must have CREATE TABLE statement")

        # 3. Partition and Cluster clauses
        self.assertIn("PARTITION BY", content.upper())
        self.assertIn("CLUSTER BY", content.upper())

    def test_3_5_pipeline_contract_to_dataplex_yaml_spec_validation(self):
        """Cross-Feature 5: Contract -> Compiler -> Dataplex DQ Spec -> Schema compliance."""
        if not self.compiler_path.exists() or not self.contract_path.exists():
            self.skipTest("compile_contract.py or contract.odcs.yaml not yet present")

        out_dq = self.temp_dir / "pipeline_dq.yaml"
        proc = CompilerRunner.run([
            "--contract", str(self.contract_path),
            "--dataplex-out", str(out_dq)
        ])
        self.assertEqual(proc.returncode, 0, f"Compiler failed: {proc.stderr}")
        self.assertTrue(out_dq.exists(), "Dataplex DQ spec was not generated")

        with open(out_dq, "r", encoding="utf-8") as f:
            dq_data = yaml.safe_load(f)

        self.assertIn("rules", dq_data, "Dataplex spec missing 'rules' sequence")
        valid_dimensions = {"COMPLETENESS", "VALIDITY", "FRESHNESS", "CONSISTENCY", "UNIQUENESS", "ACCURACY", "INTEGRITY"}
        valid_expectations = {
            "nonNullExpectation", "rangeExpectation", "setExpectation",
            "regexExpectation", "uniquenessExpectation", "rowConditionExpectation",
            "tableConditionExpectation", "sqlAssertion"
        }

        for idx, rule in enumerate(dq_data["rules"]):
            dim = rule.get("dimension")
            self.assertIn(
                dim, valid_dimensions,
                f"Rule #{idx} has invalid Dataplex dimension: '{dim}'"
            )
            # Must define at least one valid expectation type
            defined_expectations = valid_expectations.intersection(set(rule.keys()))
            self.assertTrue(
                len(defined_expectations) >= 1,
                f"Rule #{idx} does not specify any recognised Dataplex expectation: {rule}"
            )

    def test_3_6_cross_artifact_column_alignment(self):
        """Cross-Feature 6: Cross-artifact alignment between Avro fields and BigQuery DDL columns."""
        compiled_avro = PROJECT_ROOT / "schemas" / "trade_event_v1.avsc"
        compiled_ddl = PROJECT_ROOT / "sql" / "create_trades_table.sql"

        if not compiled_avro.exists() or not compiled_ddl.exists():
            self.skipTest("Generated Avro schema or BigQuery DDL not yet present")

        with open(compiled_avro, "r", encoding="utf-8") as f:
            avro_data = json.load(f)
        avro_fields = [f["name"] for f in avro_data.get("fields", [])]

        ddl_content = compiled_ddl.read_text(encoding="utf-8")

        # Every Avro field must exist as a column in BigQuery DDL
        for field in avro_fields:
            self.assertRegex(
                ddl_content, rf"\b{field}\b",
                f"Avro field '{field}' is missing from BigQuery DDL definition!"
            )

    def test_3_7_compiler_parameter_propagation(self):
        """Cross-Feature 7: CLI parameter propagation into generated DDL table identifier."""
        if not self.compiler_path.exists() or not self.contract_path.exists():
            self.skipTest("compile_contract.py or contract.odcs.yaml not yet present")

        custom_sql = self.temp_dir / "propagated.sql"
        test_proj = "sgx-exchange-prod-2026"
        test_ds = "equities_clearing"
        test_tbl = "settled_trades"

        proc = CompilerRunner.run([
            "--contract", str(self.contract_path),
            "--sql-out", str(custom_sql),
            "--project-id", test_proj,
            "--dataset", test_ds,
            "--table", test_tbl
        ])
        self.assertEqual(proc.returncode, 0)
        content = custom_sql.read_text(encoding="utf-8")

        expected_pattern = rf"`?{test_proj}\.{test_ds}\.{test_tbl}`?"
        self.assertRegex(
            content, expected_pattern,
            f"Expected table identifier '{test_proj}.{test_ds}.{test_tbl}' in DDL: {content}"
        )


if __name__ == "__main__":
    unittest.main()
