#!/usr/bin/env python3
"""Adversarial E2E Lifecycle & Drift Detection Test Suite for Milestone 5.

Adversarially tests:
- ADV-M5-1: Compiler --check mode behavior under zero drift (exit 0) vs simulated drift (exit 1).
- ADV-M5-2: setup.sh lifecycle script in --dry-run mode (validates all 11 steps execute in order).
- ADV-M5-3: setup.sh CLI robustness against invalid/unknown flags.
- ADV-M5-4: run_demo.sh in --mode=simulated (validates all 7 stages and executive scorecard output).
- ADV-M5-5: run_demo.sh CLI robustness against invalid --mode choices.
- ADV-M5-6: cleanup.sh non-destructive interactive cancellation gate (input 'n' exits 0 safely).
- ADV-M5-7: cleanup.sh CLI robustness against unknown flags.
- ADV-M5-8: Contract compilation idempotency & parameter invariance (default vs customized flags).
"""

from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent


class TestMilestone5E2EAdversarial(unittest.TestCase):
    """Adversarial tests for Milestone 5 E2E dry-run workflows and drift detection."""

    def test_adv_m5_1_compiler_check_mode_clean(self):
        """Validates that compile_contract.py --check exits 0 when artifacts match."""
        # Ensure default compilation state
        subprocess.run(
            [sys.executable, str(REPO_ROOT / "compile_contract.py")],
            cwd=REPO_ROOT,
            capture_output=True,
            check=True,
        )
        res = subprocess.run(
            [sys.executable, str(REPO_ROOT / "compile_contract.py"), "--check"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(res.returncode, 0, f"Check failed:\n{res.stdout}\n{res.stderr}")
        self.assertIn("All generated artifacts are up-to-date", res.stdout)

    def test_adv_m5_2_compiler_check_mode_detects_drift(self):
        """Validates that compile_contract.py --check detects drift and returns exit code 1."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            fake_sql = tmp_path / "fake_trades.sql"
            fake_sql.write_text("-- corrupted DDL", encoding="utf-8")

            res = subprocess.run(
                [
                    sys.executable,
                    str(REPO_ROOT / "compile_contract.py"),
                    "--sql-out", str(fake_sql),
                    "--check",
                ],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
            )
            self.assertEqual(res.returncode, 1, "Drifted artifact must exit 1 in --check mode")
            self.assertIn("[DRIFT]", res.stdout)
            self.assertIn("Check failed", res.stderr)

    def test_adv_m5_3_setup_dry_run_all_eleven_steps(self):
        """Validates setup.sh --dry-run completes all 11 provisioning steps successfully."""
        res = subprocess.run(
            ["./setup.sh", "--dry-run"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(res.returncode, 0, f"setup.sh --dry-run failed:\n{res.stdout}\n{res.stderr}")
        for step in range(1, 12):
            self.assertIn(f"[Step {step}/11]", res.stdout, f"Missing Step {step}/11 in setup.sh output")
        self.assertIn("[DRY RUN COMPLETE] All 11 steps validated successfully", res.stdout)

    def test_adv_m5_4_setup_unknown_flag_rejection(self):
        """Validates that setup.sh rejects unknown flags with exit code 1."""
        res = subprocess.run(
            ["./setup.sh", "--unsupported-flag-xyz"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(res.returncode, 1)
        self.assertIn("Unknown flag", res.stdout + res.stderr)

    def test_adv_m5_5_run_demo_simulated_all_seven_stages(self):
        """Validates run_demo.sh --mode=simulated executes all 7 stages and outputs scorecard."""
        res = subprocess.run(
            ["./run_demo.sh", "--mode=simulated"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(res.returncode, 0, f"run_demo.sh failed:\n{res.stdout}\n{res.stderr}")
        for stage in range(1, 8):
            self.assertIn(f"[Stage {stage}/7]", res.stdout, f"Missing Stage {stage}/7 in run_demo output")
        self.assertIn("EXECUTIVE DATA QUALITY SCORECARD", res.stdout)
        self.assertIn("[SUCCESS] End-to-end demonstration completed successfully", res.stdout)

    def test_adv_m5_6_run_demo_invalid_mode_rejection(self):
        """Validates that run_demo.sh rejects invalid execution mode with code 1."""
        res = subprocess.run(
            ["./run_demo.sh", "--mode=unsupported_mode"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(res.returncode, 1)
        self.assertIn("Invalid --mode", res.stdout + res.stderr)

    def test_adv_m5_7_cleanup_cancellation_safety(self):
        """Validates cleanup.sh aborts without modification when user enters 'n'."""
        res = subprocess.run(
            ["./cleanup.sh"],
            input="n\n",
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(res.returncode, 0)
        self.assertIn("Cleanup cancelled by user", res.stdout)

    def test_adv_m5_8_cleanup_unknown_flag_rejection(self):
        """Validates that cleanup.sh rejects unknown flags with exit code 1."""
        res = subprocess.run(
            ["./cleanup.sh", "--bad-flag"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(res.returncode, 1)
        self.assertIn("Unknown flag", res.stdout + res.stderr)

    def test_adv_m5_9_post_simulation_contract_restoration(self):
        """Confirms compiling default contract restores parameterized placeholders cleanly."""
        res = subprocess.run(
            [sys.executable, str(REPO_ROOT / "compile_contract.py")],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        ddl = (REPO_ROOT / "sql" / "create_trades_table.sql").read_text(encoding="utf-8")
        self.assertTrue(
            "CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.sgx_market_data.equity_trades`" in ddl
            or "CREATE OR REPLACE TABLE `${PROJECT_ID}.sgx_market_data.equity_trades`" in ddl
        )

        check_res = subprocess.run(
            [sys.executable, str(REPO_ROOT / "compile_contract.py"), "--check"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(check_res.returncode, 0)


if __name__ == "__main__":
    unittest.main()
