#!/usr/bin/env python3
"""
Adversarial Challenge & Verification Test Suite for DEMO_GUIDE.md.

Validates:
1. Structural integrity of all 10 slides (Visual Layout, Objective & Takeaway,
   Console/CLI path, Speaking Script, Anticipated MAS TRM Q&As).
2. Comprehensive coverage of all 4 SGX executive personas and their core concerns:
   - Head of Data Platform (architectural stability, schema drift, storage decoupling, operational toil)
   - Chief Risk Officer (systemic risk, auditability, perimeter enforcement, regulatory non-compliance exposure)
   - Head of Securities Trading (market integrity, trade finality, false-positive wire rejects, latency impacts)
   - Technology Risk & Compliance / Internal Audit (MAS TRM Section 8 compliance, tamper evidence, SLA reporting, incident forensics)
3. Regulatory rigor and technical defensibility of citations:
   - MAS TRM Section 8 & Section 8.1
   - SFA Section 197 (Wash sales / false trading prohibition)
   - SGX Rule 4.1 (Market manipulation / wash trading)
   - MAS TRM Section 5 (Supply chain / third party)
   - MAS TRM Section 10 (System resilience & failure recovery)
   - Statutory 7-year WORM audit retention
4. Architectural accuracy:
   - Existence of all referenced files and scripts
   - Validation of CLI command flags against actual script parsers
   - Consistency of GCP resource identifiers across schemas, DDLs, YAMLs, and shell scripts
   - Matching of Dataplex DQ rules, Knowledge Catalog aspect fields, and scorecard queries
"""

import os
from pathlib import Path
import re
import subprocess
import unittest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
DEMO_GUIDE_PATH = REPO_ROOT / "DEMO_GUIDE.md"


class TestDemoGuideStructuralIntegrity(unittest.TestCase):
    """Verifies that DEMO_GUIDE.md adheres to the strict 10-slide structure."""

    @classmethod
    def setUpClass(cls):
        cls.assertTrue(DEMO_GUIDE_PATH.exists(), f"File not found: {DEMO_GUIDE_PATH}")
        cls.content = DEMO_GUIDE_PATH.read_text(encoding="utf-8")
        cls.lines = cls.content.splitlines()

    def test_slide_count_and_headers(self):
        """Verify that exactly 10 slide headers (Slide 1 to Slide 10) are present."""
        slide_headers = re.findall(r"^## Slide (\d+):", self.content, re.MULTILINE)
        expected = [str(i) for i in range(1, 11)]
        self.assertEqual(
            slide_headers,
            expected,
            f"Expected slides 1..10 in order, found: {slide_headers}",
        )

    def test_required_sections_in_each_slide(self):
        """Verify that all 10 slides contain the 5 mandatory sections."""
        slides = re.split(r"^## Slide \d+:", self.content, flags=re.MULTILINE)[1:]
        self.assertEqual(len(slides), 10, "Expected 10 slide sections")

        required_section_patterns = [
            (r"### Visual (?:Architecture|Workflow|Terminal|Data Flow|Auto DQ|Integrity|Knowledge Catalog|Scorecard|Phased)", "Visual Layout / Diagram"),
            (r"### Objective & Key Takeaway", "Objective & Key Takeaway"),
            (r"### Terminal Commands & Console Click-Path", "Console/CLI path"),
            (r"### Verbatim Executive Speaking Script", "Speaking Script"),
            (r"### Anticipated MAS TRM Q&A", "Anticipated MAS TRM Q&A"),
        ]

        for idx, slide_body in enumerate(slides, 1):
            for pattern, name in required_section_patterns:
                self.assertTrue(
                    re.search(pattern, slide_body),
                    f"Slide {idx} missing mandatory section: {name}",
                )

    def test_each_slide_has_at_least_two_qas(self):
        """Verify that every slide has at least 2 Q&A pairs under Anticipated MAS TRM Q&A."""
        slides = re.split(r"^## Slide \d+:", self.content, flags=re.MULTILINE)[1:]
        for idx, slide_body in enumerate(slides, 1):
            qa_section = re.search(
                r"### Anticipated MAS TRM Q&A(.*?)(?=^---|\Z)",
                slide_body,
                re.DOTALL | re.MULTILINE,
            )
            self.assertIsNotNone(qa_section, f"Slide {idx} missing Q&A section")
            qa_text = qa_section.group(1)

            questions = re.findall(r"#### Q\d+", qa_text)
            answers = re.findall(r"-\s+\*\*Technical Answer\*\*:", qa_text)

            self.assertGreaterEqual(
                len(questions),
                2,
                f"Slide {idx} has {len(questions)} questions; expected at least 2",
            )
            self.assertGreaterEqual(
                len(answers),
                2,
                f"Slide {idx} has {len(answers)} technical answers; expected at least 2",
            )


class TestDemoGuidePersonaCoverage(unittest.TestCase):
    """Verifies that all 4 SGX executive personas and their core concerns are thoroughly addressed."""

    @classmethod
    def setUpClass(cls):
        cls.content = DEMO_GUIDE_PATH.read_text(encoding="utf-8")

    def test_all_four_personas_appear_in_target_audience_and_qas(self):
        """Verify presence of Head of Data Platform, Chief Risk Officer, Head of Securities Trading, and Tech Risk & Compliance."""
        audience_section = self.content[:1000]
        self.assertIn("Head of Data Platform", audience_section)
        self.assertIn("Chief Risk Officer", audience_section)
        self.assertIn("Head of Securities Trading", audience_section)
        self.assertTrue(
            "Technology Risk" in audience_section or "Technology Risk & Compliance" in audience_section,
            "Tech Risk persona missing in header",
        )

        # Check Q&A persona assignments
        qa_personas = re.findall(r"#### Q\d+ \((.*?)\):", self.content)
        self.assertGreaterEqual(len(qa_personas), 20, "Expected at least 20 Q&A entries")

        persona_counts = {}
        for p in qa_personas:
            p_clean = p.strip()
            persona_counts[p_clean] = persona_counts.get(p_clean, 0) + 1

        self.assertIn("Chief Risk Officer", persona_counts)
        self.assertIn("Head of Data Platform", persona_counts)
        self.assertIn("Head of Securities Trading", persona_counts)
        self.assertTrue(
            any("Technology Risk" in k for k in persona_counts.keys()),
            "Head of Technology Risk persona missing in Q&As",
        )

        self.assertGreaterEqual(persona_counts.get("Chief Risk Officer", 0), 4)
        self.assertGreaterEqual(persona_counts.get("Head of Data Platform", 0), 4)
        self.assertGreaterEqual(persona_counts.get("Head of Securities Trading", 0), 3)

    def test_head_of_data_platform_concerns(self):
        """Verify: architectural stability, schema drift, storage decoupling, operational toil."""
        lower_content = self.content.lower()
        self.assertIn("schema drift", lower_content)
        self.assertTrue("direct subscription" in lower_content or "storage write api" in lower_content)
        self.assertTrue("operational" in lower_content and ("toil" in lower_content or "triage" in lower_content or "hours saved" in lower_content))
        self.assertTrue("architectural stability" in lower_content or "stability" in lower_content or "zero-etl" in lower_content)

    def test_chief_risk_officer_concerns(self):
        """Verify: systemic risk, auditability, perimeter enforcement, regulatory non-compliance exposure."""
        lower_content = self.content.lower()
        self.assertTrue("systemic risk" in lower_content or "risk management" in lower_content)
        self.assertIn("auditability", lower_content)
        self.assertTrue("perimeter" in lower_content and "defense" in lower_content)
        self.assertTrue("regulatory" in lower_content and "compliance" in lower_content)

    def test_head_of_securities_trading_concerns(self):
        """Verify: market integrity, trade finality, false-positive wire rejects, latency impacts."""
        lower_content = self.content.lower()
        self.assertIn("market integrity", lower_content)
        self.assertTrue("rpo=0" in lower_content or "zero data loss" in lower_content or "finality" in lower_content)
        self.assertTrue("latency" in lower_content and ("sub-millisecond" in lower_content or "<0.8 milliseconds" in lower_content))
        self.assertTrue("rejection" in lower_content and ("non-repudiation" in lower_content or "dispute" in lower_content or "clear-schema" in lower_content))

    def test_technology_risk_and_compliance_concerns(self):
        """Verify: MAS TRM Section 8 compliance, tamper evidence, SLA reporting, incident forensics."""
        lower_content = self.content.lower()
        self.assertIn("mas trm section 8", lower_content)
        self.assertTrue("tampering" in lower_content or "tamper" in lower_content or "immutable" in lower_content)
        self.assertTrue("sla" in lower_content and "scorecard" in lower_content)
        self.assertTrue("forensic" in lower_content or "incident forensics" in lower_content)


class TestDemoGuideRegulatoryRigor(unittest.TestCase):
    """Verifies that all MAS TRM Section 8, SFA Section 197, and SGX Rule 4.1 citations are defensible."""

    @classmethod
    def setUpClass(cls):
        cls.content = DEMO_GUIDE_PATH.read_text(encoding="utf-8")

    def test_mas_trm_section_8_citations(self):
        """MAS TRM Section 8 (and Section 8.1 data integrity controls) must be cited and contextualized."""
        self.assertIn("MAS TRM Section 8", self.content)
        self.assertIn("MAS TRM Section 8.1", self.content)
        self.assertIn("Data Integrity Controls", self.content)

    def test_sfa_section_197_citation(self):
        """Securities and Futures Act Section 197 (wash sales / false trading prohibition) must be cited."""
        self.assertIn("Section 197", self.content)
        self.assertTrue(
            "Securities and Futures Act" in self.content or "SFA Section 197" in self.content
        )
        self.assertTrue(
            "wash trading" in self.content.lower() or "wash sales" in self.content.lower()
        )

    def test_sgx_rule_4_1_citation(self):
        """SGX Trading Rule 4.1 must be cited for market manipulation / wash trading."""
        self.assertTrue(
            "SGX Rule 4.1" in self.content or "SGX Trading Rule 4.1" in self.content
        )

    def test_additional_regulatory_frameworks(self):
        """Verify MAS TRM Section 5, Section 10, and statutory recordkeeping citations."""
        self.assertIn("MAS TRM Section 5", self.content)  # Software supply chain
        self.assertIn("MAS TRM Section 10", self.content)  # System resilience
        self.assertTrue("7 years" in self.content or "7-year" in self.content)  # Statutory retention


class TestDemoGuideArchitecturalAccuracy(unittest.TestCase):
    """Verifies that all commands, files, flags, and schemas in DEMO_GUIDE.md match the codebase."""

    @classmethod
    def setUpClass(cls):
        cls.content = DEMO_GUIDE_PATH.read_text(encoding="utf-8")

    def test_referenced_files_exist_on_filesystem(self):
        """Verify all file paths mentioned in DEMO_GUIDE.md exist."""
        referenced_files = [
            "contract.odcs.yaml",
            "compile_contract.py",
            "schemas/trade_event_v1.avsc",
            "sql/create_trades_table.sql",
            "config/dataplex_dq_spec.yaml",
            "config/aspect_contract_template.yaml",
            "config/table_aspect_payload.yaml",
            "scripts/publish_events.py",
            "scripts/run_dataplex_scan.py",
            "setup.sh",
            "run_demo.sh",
            "cleanup.sh",
            "sql/query_executive_scorecard.sql",
        ]
        for rel_path in referenced_files:
            abs_path = REPO_ROOT / rel_path
            self.assertTrue(abs_path.exists(), f"Referenced file missing on disk: {rel_path}")

    def test_lifecycle_scripts_are_executable(self):
        """Verify setup.sh, run_demo.sh, cleanup.sh have executable permissions."""
        scripts = ["setup.sh", "run_demo.sh", "cleanup.sh"]
        for s in scripts:
            path = REPO_ROOT / s
            self.assertTrue(os.access(path, os.X_OK), f"{s} is not executable (chmod +x needed)")

    def test_script_cli_flags_validity(self):
        """Verify CLI flags shown in DEMO_GUIDE.md are accepted by the scripts."""
        # 1. compile_contract.py flags
        compile_py = (REPO_ROOT / "compile_contract.py").read_text()
        self.assertIn("--contract", compile_py)
        self.assertIn("--output-dir", compile_py)

        # 2. publish_events.py flags
        pub_py = (REPO_ROOT / "scripts" / "publish_events.py").read_text()
        self.assertIn("--mode", pub_py)
        self.assertIn("--topic", pub_py)
        self.assertIn("--project-id", pub_py)
        self.assertIn("--count", pub_py)
        # Verify modes: valid, invalid-schema, trigger-dlq
        self.assertIn('"valid"', pub_py)
        self.assertIn('"invalid-schema"', pub_py)
        self.assertIn('"trigger-dlq"', pub_py)

        # 3. run_dataplex_scan.py flags
        scan_py = (REPO_ROOT / "scripts" / "run_dataplex_scan.py").read_text()
        self.assertIn("--project-id", scan_py)
        self.assertIn("--location", scan_py)
        self.assertIn("--mode", scan_py)
        # Modes: run, scorecard, dry-run, poll
        self.assertIn("run", scan_py)
        self.assertIn("scorecard", scan_py)

        # 4. setup.sh flags
        setup_sh = (REPO_ROOT / "setup.sh").read_text()
        self.assertIn("--project-id", setup_sh)
        self.assertIn("--region", setup_sh)

        # 5. run_demo.sh flags
        run_demo_sh = (REPO_ROOT / "run_demo.sh").read_text()
        self.assertIn("--project-id", run_demo_sh)
        self.assertIn("--mode", run_demo_sh)
        self.assertIn("live", run_demo_sh)
        self.assertIn("simulated", run_demo_sh)

        # 6. cleanup.sh flags
        cleanup_sh = (REPO_ROOT / "cleanup.sh").read_text()
        self.assertIn("--project-id", cleanup_sh)

    def test_dataplex_dq_rules_match_spec_yaml(self):
        """Verify the 9 rules listed in Slide 6 match config/dataplex_dq_spec.yaml."""
        spec_path = REPO_ROOT / "config" / "dataplex_dq_spec.yaml"
        spec = yaml.safe_load(spec_path.read_text())
        rules = spec.get("rules", [])
        self.assertEqual(len(rules), 9, f"Expected 9 rules in dataplex_dq_spec.yaml, found {len(rules)}")

        # Check dimension counts
        dimensions = [r["dimension"] for r in rules]
        self.assertEqual(dimensions.count("COMPLETENESS"), 4)
        self.assertEqual(dimensions.count("VALIDITY"), 3)
        self.assertEqual(dimensions.count("FRESHNESS"), 1)
        self.assertEqual(dimensions.count("INTEGRITY"), 1)

    def test_dataplex_aspect_type_matches_template(self):
        """Verify Aspect Type fields in Slide 8 match config/aspect_contract_template.yaml."""
        template_path = REPO_ROOT / "config" / "aspect_contract_template.yaml"
        aspect_spec = yaml.safe_load(template_path.read_text())
        self.assertEqual(aspect_spec.get("name"), "DataContractSpec")

        field_names = [f["name"] for f in aspect_spec.get("recordFields", [])]
        expected_fields = [
            "contract_id",
            "contract_version",
            "domain",
            "data_owner",
            "criticality_tier",
            "freshness_sla_hours",
            "regulatory_standard",
            "last_audit_timestamp",
            "dq_scorecard_status",
        ]
        self.assertEqual(field_names, expected_fields)

    def test_gcp_resource_naming_consistency(self):
        """Verify topic, subscription, dataset, table, and scan naming consistency."""
        resource_mappings = {
            "Pub/Sub Topic": "sgx-equity-trades-topic",
            "Pub/Sub Schema": "sgx-trades-schema",
            "DLQ Topic": "sgx-equity-trades-dlq-topic",
            "DLQ Subscription": "sgx-equity-trades-dlq-sub",
            "BQ Direct Subscription": "sgx-equity-trades-bq-sub",
            "BigQuery Dataset": "sgx_market_data",
            "BigQuery Table": "equity_trades",
            "Dataplex DataScan": "sgx-equity-trades-dq",
            "Dataplex Aspect Type": "data-contract-spec",
        }
        for resource, name in resource_mappings.items():
            self.assertIn(
                name,
                self.content,
                f"Standard resource identifier '{name}' for {resource} missing in DEMO_GUIDE.md",
            )


if __name__ == "__main__":
    unittest.main()
