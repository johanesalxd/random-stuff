import os
import yaml
from pathlib import Path


def setup_dbt_profile():
    """
    Generates a local profiles.yml for the simulation.
    Uses the current user's GCP project or defaults to the config.
    """
    # Load project config to get project ID
    try:
        with open("config/migration_config.yaml", "r") as f:
            config = yaml.safe_load(f)
            project_id = config.get("gcp", {}).get("billing_project")
    except FileNotFoundError:
        # Fallback if config isn't generated yet
        project_id = os.environ.get("GOOGLE_CLOUD_PROJECT")

    if not project_id:
        print("❌ Error: Could not determine GCP Project ID.")
        print(
            "Please ensure config/migration_config.yaml exists or GOOGLE_CLOUD_PROJECT is set."
        )
        return None

    # Define profile structure
    profile_data = {
        "sample_project": {
            "target": "dev",
            "outputs": {
                "dev": {
                    "type": "bigquery",
                    "method": "oauth",
                    "project": project_id,
                    "dataset": "sample_gold",  # Simulating PROD
                    "threads": 4,
                    "timeout_seconds": 300,
                    "location": "US",
                    "priority": "interactive",
                },
                "ci": {
                    "type": "bigquery",
                    "method": "oauth",
                    "project": project_id,
                    "dataset": "sample_gold_ci",  # Simulating PR Build
                    "threads": 4,
                    "timeout_seconds": 300,
                    "location": "US",
                    "priority": "interactive",
                },
            },
        }
    }

    # Write to local directory
    profiles_path = Path("profiles.yml")
    with open(profiles_path, "w") as f:
        yaml.dump(profile_data, f)

    print(f"✅ Generated local profiles.yml for project: {project_id}")
    return project_id


if __name__ == "__main__":
    setup_dbt_profile()
