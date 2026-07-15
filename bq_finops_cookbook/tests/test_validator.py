from __future__ import annotations

import sys
import shutil
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from extract_sql import extract_named_queries  # noqa: E402
from validate_cookbook import run_checks  # noqa: E402


class ValidatorTests(unittest.TestCase):
    def mutated_failures(self, relative_path: str, old: str, new: str):
        with tempfile.TemporaryDirectory() as directory:
            copy = Path(directory) / "cookbook"
            shutil.copytree(ROOT, copy, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
            path = copy / relative_path
            text = path.read_text()
            self.assertIn(old, text, f"mutation anchor missing: {old}")
            path.write_text(text.replace(old, new, 1))
            return run_checks(copy)

    def test_extract_named_queries(self) -> None:
        text = """### Query 1.1: Example\n```sql\nSELECT 1;\n```\n"""
        queries = extract_named_queries(text)
        self.assertEqual(["1.1"], [query["id"] for query in queries])
        self.assertEqual("SELECT 1;", queries[0]["sql"])

    def test_extract_rejects_duplicate_query_ids(self) -> None:
        text = """### Query 1.1: A\n```sql\nSELECT 1;\n```\n### Query 1.1: B\n```sql\nSELECT 2;\n```\n"""
        with self.assertRaises(ValueError):
            extract_named_queries(text)

    def test_repository_contract_is_green(self) -> None:
        failures = run_checks(ROOT)
        self.assertEqual([], failures, "\n".join(failures))

    def test_mutation_rejects_unqualified_view(self) -> None:
        failures = self.mutated_failures(
            ".agents/skills/bq-finops-analyst/resources/finops_agent.md",
            "`[WORKLOAD_PROJECT_ID].region-[YOUR_REGION]`.INFORMATION_SCHEMA.JOBS_BY_PROJECT",
            "`region-[YOUR_REGION]`.INFORMATION_SCHEMA.JOBS_BY_PROJECT",
        )
        self.assertIn("unqualified regional INFORMATION_SCHEMA view", failures)

    def test_mutation_rejects_write_api_ok_regression(self) -> None:
        failures = self.mutated_failures(
            ".agents/skills/bq-finops-analyst/resources/finops_agent.md",
            "error_code != 'OK'",
            "error_code != ''",
        )
        self.assertIn("Storage Write API success counted as error", failures)

    def test_mutation_rejects_skill_name_mismatch(self) -> None:
        failures = self.mutated_failures(
            ".agents/skills/bq-finops-analyst/SKILL.md",
            "name: bq-finops-analyst",
            "name: wrong-name",
        )
        self.assertIn("skill frontmatter name must exactly match its parent directory", failures)
    def test_mutations_reject_known_regressions(self) -> None:
        cases = [
            (
                "stale fixed ingestion savings",
                "Treat every price as a dated runtime input.",
                "Use $0.025/GiB for 50% cost savings.",
            ),
            (
                "destructive reservation removal command",
                "bq mk --reservation",
                "bq rm --reservation",
            ),
            (
                "invalid Standard 2500-slot guidance",
                "Standard has no baseline, so its autoscaling slots and total maximum are both capped at 1,600.",
                "Standard should use 2,500 slots.",
            ),
        ]
        for expected, old, new in cases:
            with self.subTest(expected=expected):
                failures = self.mutated_failures(
                    ".agents/skills/bq-finops-analyst/resources/finops_agent.md",
                    old,
                    new,
                )
                self.assertIn(expected, failures)


if __name__ == "__main__":
    unittest.main()
