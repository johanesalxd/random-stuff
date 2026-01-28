import os
import sys
import subprocess
import yaml
from pathlib import Path


def run_command(command):
    """Runs a shell command and prints output."""
    print(f"🔄 Running: {command}")
    result = subprocess.run(command, shell=True, text=True, capture_output=True)
    if result.returncode != 0:
        print(f"❌ Command failed:\n{result.stderr}")
        return False
    print("✅ Success")
    return True


def main():
    print("🚀 Starting PR Validation Simulation...")

    # 1. Setup Profile
    print("\n--- Step 1: Setting up Environment ---")
    sys.path.append(str(Path(__file__).parent))  # Add scripts dir to path
    try:
        import setup_profile as setup

        project_id = setup.setup_dbt_profile()
        if not project_id:
            sys.exit(1)
    except ImportError:
        print("❌ Error: scripts.setup_profile module not found.")
        sys.exit(1)

    # Ensure dbt uses the local profiles.yml
    os.environ["DBT_PROFILES_DIR"] = "."

    # 2. Establish Baseline (PROD)
    print("\n--- Step 2: Establishing Baseline (Simulating PROD) ---")
    print("Building 'fct_orders_broken' into 'sample_gold' dataset...")
    # We use fct_orders_broken to represent the "current buggy state"
    cmd_prod = "uv run dbt run --select fct_orders_broken --target dev --project-dir sample_project"
    if not run_command(cmd_prod):
        sys.exit(1)

    # 3. Build PR Version (CI)
    print("\n--- Step 3: Building PR Version (Simulating CI) ---")
    print("Building 'fct_orders' (the fix) into 'sample_gold_ci' dataset...")
    # We use fct_orders to represent the "proposed fix"
    cmd_ci = (
        "uv run dbt run --select fct_orders --target ci --project-dir sample_project"
    )
    if not run_command(cmd_ci):
        sys.exit(1)

    # 4. Trigger AI Validation
    print("\n--- Step 4: AI Validation Agent ---")
    prod_table = f"{project_id}.sample_gold.fct_orders_broken"
    pr_table = f"{project_id}.sample_gold_ci.fct_orders"

    print(f"🕵️‍♂️ Validating PR Table: {pr_table}")
    print(f"📉 Against Baseline:   {prod_table}")

    cmd_validate = f"uv run python scripts/ci_validation_runner.py --prod {prod_table} --pr {pr_table}"

    # We run this interactively to show output
    process = subprocess.Popen(
        cmd_validate, shell=True, stdout=sys.stdout, stderr=sys.stderr
    )
    process.communicate()

    if process.returncode == 0:
        print("\n✅ Simulation Complete: Validation Passed")
    else:
        print("\n❌ Simulation Complete: Validation Failed")
        sys.exit(process.returncode)


if __name__ == "__main__":
    main()
