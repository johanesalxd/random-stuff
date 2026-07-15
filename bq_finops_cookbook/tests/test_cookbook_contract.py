from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / ".agents/skills/bq-finops-analyst/SKILL.md"
AGENT = ROOT / ".agents/skills/bq-finops-analyst/resources/finops_agent.md"
README = ROOT / "README.md"
CLAIMS = ROOT / ".agents/skills/bq-finops-analyst/resources/claim_matrix.json"
MANIFEST = ROOT / ".agents/skills/bq-finops-analyst/resources/execution_manifest.json"

EXPECTED_QUERY_IDS = {
    "0.1", "0.2", "0.2a", "0.3", "0.4", "0.5",
    "1.1", "1.2", "1.3",
    "4.1", "4.2", "4.3", "4.4", "4.5", "4.8", "4.9",
    "4.10", "4.11", "4.12", "4.13", "4.14",
    "5.1", "6.1", "6.2", "6.3",
}

REQUIRED_CLAIMS = {
    "standard_max_reservation_slots",
    "reservation_slot_increment",
    "autoscale_billing_duration",
    "reservation_flag_mutex",
    "storage_write_exactly_once",
    "on_demand_price",
    "storage_write_price",
    "queue_limit_interactive",
    "storage_billing_model_change_delay",
}

FINAL_HEADINGS = {
    "Current State Summary",
    "Evidence Quality",
    "Recommended Strategy",
    "Alternative Analysis",
    "Optimization Actions",
    "Implementation Proposals",
    "Validation Criteria",
    "Documentation Checks",
    "MCP / bq Execution Notes",
    "Next Steps",
}


def query_ids(text: str) -> set[str]:
    return set(re.findall(r"^### Query ([0-9]+(?:\.[0-9]+[a-z]?)?):", text, re.MULTILINE))


class CookbookContractTests(unittest.TestCase):
    def test_query_inventory_is_complete_and_unique(self) -> None:
        ids = re.findall(r"^### Query ([0-9]+(?:\.[0-9]+[a-z]?)?):", AGENT.read_text(), re.MULTILINE)
        self.assertEqual(EXPECTED_QUERY_IDS, set(ids))
        self.assertEqual(len(ids), len(set(ids)))

    def test_canonical_files_do_not_point_to_missing_docs_reference(self) -> None:
        for path in (README, SKILL, AGENT):
            self.assertNotIn("docs/REFERENCES.md", path.read_text(), path)

    def test_runtime_files_do_not_embed_us_on_demand_price(self) -> None:
        for path in (README, SKILL, AGENT):
            text = path.read_text()
            self.assertNotRegex(text, r"\$?6\.25\s*(?:/|per\s+)(?:TB|TiB)", str(path))

    def test_claim_matrix_covers_volatile_rules(self) -> None:
        data = json.loads(CLAIMS.read_text())
        by_id = {item["id"]: item for item in data["claims"]}
        self.assertTrue(REQUIRED_CLAIMS <= by_id.keys())
        for claim_id in REQUIRED_CLAIMS:
            claim = by_id[claim_id]
            self.assertRegex(claim["authority_url"], r"^https://(?:docs\.)?cloud\.google\.com/")
            self.assertRegex(claim["verified_on"], r"^20\d{2}-\d{2}-\d{2}$")
            self.assertIn(claim["status"], {"verified", "runtime_input"})

    def test_execution_manifest_matches_query_inventory(self) -> None:
        manifest = json.loads(MANIFEST.read_text())
        self.assertIn("Gemini 3.5 Flash", manifest["runtime"])
        self.assertIn("thinking: High", manifest["runtime"])
        ids = [item["id"] for item in manifest["queries"]]
        self.assertEqual(EXPECTED_QUERY_IDS, set(ids))
        self.assertEqual(len(ids), len(set(ids)))
        for item in manifest["queries"]:
            self.assertIn(item["required"], {True, False})
            self.assertTrue(item["report"])
            self.assertTrue(item["evidence_type"])

    def test_standard_examples_never_exceed_current_cap(self) -> None:
        for path in ROOT.rglob("*.md"):
            if ".hermes" in path.parts:
                continue
            text = path.read_text()
            for block in re.findall(r"```(?:bash|shell)\n(.*?)```", text, re.DOTALL):
                if "--edition=STANDARD" not in block and "--edition STANDARD" not in block:
                    continue
                values = [int(v) for v in re.findall(r"--(?:autoscale_max_slots|max_slots)[= ](\d+)", block)]
                if values:
                    self.assertLessEqual(max(values), 1600, f"Invalid Standard size in {path}")
                else:
                    self.assertRegex(
                        block,
                        r"\[(?:MAX_SLOTS|STANDARD_(?:AUTOSCALE_SLOTS|MAX_RESERVATION_SIZE)_MAX_1600)\]",
                        f"Standard block lacks a bounded max placeholder: {path}",
                    )

    def test_mutating_commands_are_explicitly_proposals(self) -> None:
        mutating = re.compile(r"\b(?:bq\s+(?:mk|update|rm)|ALTER\s+SCHEMA|CREATE\s+RESERVATION)\b", re.I)
        code_block = re.compile(r"```(?:bash|shell|sql)\n(.*?)```", re.DOTALL)
        for path in ROOT.rglob("*.md"):
            if ".hermes" in path.parts:
                continue
            text = path.read_text()
            for match in code_block.finditer(text):
                if not mutating.search(match.group(1)):
                    continue
                context = text[max(0, match.start() - 500):match.start()]
                self.assertRegex(context, r"PROPOSAL_(?:NONDESTRUCTIVE|DESTRUCTIVE)", f"Untagged command block: {path}")

    def test_runtime_queries_minimize_identifiable_fields(self) -> None:
        text = AGENT.read_text()
        self.assertNotIn("\n  query,\n", text)
        self.assertNotIn("\n  user_email,\n", text)
        self.assertNotIn("\n  job_id,\n", text)

    def test_all_samples_are_unmistakably_synthetic(self) -> None:
        for path in (ROOT / "sample_results").rglob("*.md"):
            self.assertIn("**Synthetic sample:**", path.read_text()[:500], str(path))

    def test_final_samples_follow_report_contract(self) -> None:
        for path in (ROOT / "sample_results").rglob("06_final_recommendation.md"):
            headings = set(re.findall(r"^## (.+)$", path.read_text(), re.MULTILINE))
            self.assertTrue(FINAL_HEADINGS <= headings, f"Missing {FINAL_HEADINGS - headings} in {path}")


if __name__ == "__main__":
    unittest.main()
