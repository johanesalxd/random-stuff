from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from decision_contract import evaluate_strategy  # noqa: E402


class DecisionContractTests(unittest.TestCase):
    def scenarios(self):
        for path in sorted((ROOT / "tests/fixtures").glob("*.json")):
            yield path, json.loads(path.read_text())

    def test_scenario_contracts(self) -> None:
        for path, scenario in self.scenarios():
            with self.subTest(path=path.name):
                result = evaluate_strategy(scenario["input"])
                expected = scenario["expected"]
                self.assertEqual(expected["strategy"], result["strategy"])
                self.assertEqual(expected["confidence"], result["confidence"])
                for warning in expected.get("warnings", []):
                    self.assertIn(warning, result["warnings"])

    def test_zero_median_never_divides_by_zero(self) -> None:
        result = evaluate_strategy({
            "evidence_complete": True,
            "avg_slots": 20,
            "p25_slots": 0,
            "p50_slots": 0,
            "p95_slots": 100,
            "max_slots": 200,
            "cv": 2.0,
            "monthly_on_demand_cost": 50,
            "standard_max_slots": 1600,
            "recommender_strategy": None,
        })
        self.assertIsNone(result["burst_ratio"])
        self.assertIn("BURST_RATIO_UNDEFINED", result["warnings"])

    def test_standard_is_never_recommended_above_cap(self) -> None:
        result = evaluate_strategy({
            "evidence_complete": True,
            "avg_slots": 700,
            "p25_slots": 200,
            "p50_slots": 450,
            "p95_slots": 1800,
            "max_slots": 2400,
            "cv": 0.8,
            "monthly_on_demand_cost": 8500,
            "standard_max_slots": 1600,
            "recommender_strategy": None,
        })
        self.assertNotEqual("STANDARD_AUTOSCALING", result["strategy"])
        self.assertIn("STANDARD_CAP_EXCEEDED", result["warnings"])
    def test_caller_cannot_raise_standard_cap(self) -> None:
        result = evaluate_strategy({
            "evidence_complete": True,
            "avg_slots": 700,
            "p25_slots": 200,
            "p50_slots": 450,
            "p95_slots": 1800,
            "max_slots": 2400,
            "cv": 0.8,
            "monthly_on_demand_cost": 8500,
            "standard_max_slots": 9999,
            "recommender_strategy": None,
        })
        self.assertEqual("ENTERPRISE_EVALUATION", result["strategy"])
        self.assertIn("IGNORED_CALLER_SUPPLIED_STANDARD_CAP", result["warnings"])

    def test_missing_required_metric_is_insufficient_evidence(self) -> None:
        result = evaluate_strategy({
            "evidence_complete": True,
            "avg_slots": None,
            "p25_slots": 50,
            "p50_slots": 100,
            "p95_slots": 200,
            "max_slots": 300,
            "cv": 0.4,
        })
        self.assertEqual("INSUFFICIENT_EVIDENCE", result["strategy"])
        self.assertEqual("LOW", result["confidence"])


if __name__ == "__main__":
    unittest.main()
