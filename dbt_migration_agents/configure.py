#!/usr/bin/env python3
"""Interactive setup wizard for DBT Migration Agents.

Prompts for project-specific values and generates migration_config.yaml.
Also creates necessary output directories.

Usage:
    python setup.py

    # Or with defaults for testing
    python setup.py --defaults
"""

import argparse
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional


def get_input(prompt: str, default: Optional[str] = None, required: bool = True) -> str:
    """Get user input with optional default value.

    Args:
        prompt: The prompt to display.
        default: Default value if user presses Enter.
        required: Whether the input is required.

    Returns:
        User input or default value.
    """
    if default:
        full_prompt = f"{prompt} [{default}]: "
    else:
        full_prompt = f"{prompt}: "

    while True:
        value = input(full_prompt).strip()
        if not value and default:
            return default
        if not value and required:
            print("This field is required. Please enter a value.")
            continue
        if value:
            return value
        if not required:
            return ""


def validate_project_id(project_id: str) -> bool:
    """Validate GCP project ID format.

    Args:
        project_id: Project ID to validate.

    Returns:
        True if valid, False otherwise.
    """
    if not project_id:
        return False
    if len(project_id) < 6 or len(project_id) > 30:
        return False
    if not project_id[0].isalpha():
        return False
    for char in project_id:
        if not (char.isalnum() or char == "-"):
            return False
    return True


def validate_path(path: str) -> bool:
    """Validate path format.

    Args:
        path: Path to validate.

    Returns:
        True if valid, False otherwise.
    """
    if not path:
        return False
    # Basic validation - no special characters that could cause issues
    invalid_chars = ["<", ">", ":", '"', "|", "?", "*"]
    for char in invalid_chars:
        if char in path:
            return False
    return True


def get_project_input(prompt: str, default: Optional[str] = None) -> str:
    """Get and validate a GCP project ID.

    Args:
        prompt: The prompt to display.
        default: Default value.

    Returns:
        Valid project ID.
    """
    while True:
        value = get_input(prompt, default)
        if validate_project_id(value):
            return value
        print(f"Invalid project ID: {value}")
        print("Project IDs must be 6-30 characters, start with a letter,")
        print("and contain only lowercase letters, numbers, and hyphens.")


def get_path_input(prompt: str, default: Optional[str] = None) -> str:
    """Get and validate a path.

    Args:
        prompt: The prompt to display.
        default: Default value.

    Returns:
        Valid path.
    """
    while True:
        value = get_input(prompt, default)
        if validate_path(value):
            return value
        print(f"Invalid path: {value}")


def collect_configuration() -> Dict[str, Any]:
    """Collect configuration from user input.

    Returns:
        Configuration dictionary.
    """
    print("\n" + "=" * 60)
    print("DBT Migration Agents - Setup Wizard")
    print("=" * 60)
    print("\nThis wizard will help you configure the migration framework.")
    print("Press Enter to accept default values shown in [brackets].\n")

    config = {}

    # Project Settings
    print("\n--- PROJECT SETTINGS ---\n")
    config["project"] = {
        "name": get_input("DBT project name", "my_dbt_project"),
        "manifest_path": get_path_input(
            "Path to DBT manifest.json", "target/manifest.json"
        ),
    }

    # GCP Settings
    print("\n--- GCP SETTINGS ---\n")
    print("Enter your GCP project IDs for each data layer.")
    print("(You can use the same project for multiple layers)\n")

    billing_project = get_project_input(
        "Billing project (for BigQuery API costs)", "my-billing-project"
    )

    config["gcp"] = {
        "billing_project": billing_project,
        "projects": {
            "bronze": get_project_input("Bronze layer project", billing_project),
            "silver": get_project_input("Silver layer project", billing_project),
            "gold": get_project_input("Gold layer project", billing_project),
        },
        "schemas": {
            "bronze": get_input("Bronze schema name", "bronze"),
            "silver": get_input("Silver schema name", "silver"),
            "gold": get_input("Gold schema name", "gold"),
        },
    }

    # Remove None values
    config["gcp"]["projects"] = {
        k: v for k, v in config["gcp"]["projects"].items() if v is not None
    }

    # DBT Paths
    print("\n--- DBT PATHS ---\n")
    print("Enter the paths to your DBT model directories.\n")

    config["dbt"] = {
        "bronze_models": get_path_input("Bronze models path", "models/bronze"),
        "silver_models": get_path_input("Silver models path", "models/silver"),
        "gold_models": get_path_input("Gold models path", "models/gold"),
        "seeds": get_path_input("Seeds path", "seeds"),
    }

    # Output Paths
    print("\n--- OUTPUT PATHS ---\n")
    print("Enter paths for generated outputs.\n")

    config["outputs"] = {
        "base_path": get_path_input("Base output path", "migration_outputs"),
        "lineage": get_path_input("Lineage outputs", "lineage_analyzer/outputs"),
        "prd": get_path_input("PRD outputs", "prd_generator/outputs"),
        "validation": get_path_input(
            "Validation outputs", "migration_validator/outputs"
        ),
        "cookbooks": get_path_input("Cookbook outputs", "code_refactor/outputs"),
    }

    # Validation Settings
    print("\n--- VALIDATION SETTINGS ---\n")
    print("Configure validation thresholds (as decimals).\n")

    row_count_threshold = get_input(
        "Row count difference threshold (0.001 = 0.1%)", "0.001"
    )
    null_threshold = get_input("NULL increase threshold (0.05 = 5%)", "0.05")

    config["validation"] = {
        "row_count_threshold": float(row_count_threshold),
        "null_threshold": float(null_threshold),
    }

    # Architecture Description (optional)
    print("\n--- ARCHITECTURE DESCRIPTION (Optional) ---\n")
    description = get_input(
        "Brief description of your data architecture",
        "Data flows from raw to refined to gold layer",
        required=False,
    )

    if description:
        config["architecture"] = {"description": description}

    return config


def generate_yaml(config: Dict[str, Any]) -> str:
    """Generate YAML configuration content.

    Args:
        config: Configuration dictionary.

    Returns:
        YAML formatted string.
    """
    lines = [
        "# DBT Migration Agents Configuration",
        "# Generated by setup wizard",
        "",
        "# === PROJECT SETTINGS ===",
        "project:",
        f'  name: "{config["project"]["name"]}"',
        f'  manifest_path: "{config["project"]["manifest_path"]}"',
        "",
        "# === GCP SETTINGS ===",
        "gcp:",
        f'  billing_project: "{config["gcp"]["billing_project"]}"',
        "",
        "  projects:",
    ]

    for key, value in config["gcp"]["projects"].items():
        lines.append(f'    {key}: "{value}"')

    lines.extend(
        [
            "",
            "  schemas:",
            f'    bronze: "{config["gcp"]["schemas"]["bronze"]}"',
            f'    silver: "{config["gcp"]["schemas"]["silver"]}"',
            f'    gold: "{config["gcp"]["schemas"]["gold"]}"',
            "",
            "# === DBT PATHS ===",
            "dbt:",
            f'  bronze_models: "{config["dbt"]["bronze_models"]}"',
            f'  silver_models: "{config["dbt"]["silver_models"]}"',
            f'  gold_models: "{config["dbt"]["gold_models"]}"',
            f'  seeds: "{config["dbt"]["seeds"]}"',
            "",
            "# === OUTPUT PATHS ===",
            "outputs:",
            f'  base_path: "{config["outputs"]["base_path"]}"',
            f'  lineage: "{config["outputs"]["lineage"]}"',
            f'  prd: "{config["outputs"]["prd"]}"',
            f'  validation: "{config["outputs"]["validation"]}"',
            f'  cookbooks: "{config["outputs"]["cookbooks"]}"',
            "",
            "# === VALIDATION SETTINGS ===",
            "validation:",
            f"  row_count_threshold: {config['validation']['row_count_threshold']}",
            f"  null_threshold: {config['validation']['null_threshold']}",
        ]
    )

    if "architecture" in config:
        lines.extend(
            [
                "",
                "# === ARCHITECTURE DESCRIPTION ===",
                "architecture:",
                f'  description: "{config["architecture"]["description"]}"',
            ]
        )

    lines.append("")
    return "\n".join(lines)


def create_directories(config: Dict[str, Any], base_path: Path) -> None:
    """Create output directories.

    Args:
        config: Configuration dictionary.
        base_path: Base path for the framework.
    """
    directories = [
        config["outputs"]["lineage"],
        config["outputs"]["prd"],
        config["outputs"]["validation"],
        config["outputs"]["cookbooks"],
        "migration_validator/scripts",
    ]

    for directory in directories:
        dir_path = base_path / directory
        dir_path.mkdir(parents=True, exist_ok=True)
        # Create .gitkeep to preserve empty directories
        gitkeep = dir_path / ".gitkeep"
        if not gitkeep.exists():
            gitkeep.touch()

    print(f"\nCreated output directories.")


def run_with_defaults() -> Dict[str, Any]:
    """Generate default configuration for testing.

    Returns:
        Default configuration dictionary.
    """
    return {
        "project": {
            "name": "my_dbt_project",
            "manifest_path": "target/manifest.json",
        },
        "gcp": {
            "billing_project": "my-billing-project",
            "projects": {
                "bronze": "my-bronze-project",
                "silver": "my-silver-project",
                "gold": "my-gold-project",
            },
            "schemas": {
                "bronze": "bronze",
                "silver": "silver",
                "gold": "gold",
            },
        },
        "dbt": {
            "bronze_models": "models/bronze",
            "silver_models": "models/silver",
            "gold_models": "models/gold",
            "seeds": "seeds",
        },
        "outputs": {
            "base_path": "migration_outputs",
            "lineage": "lineage_analyzer/outputs",
            "prd": "prd_generator/outputs",
            "validation": "migration_validator/outputs",
            "cookbooks": "code_refactor/outputs",
        },
        "validation": {
            "row_count_threshold": 0.001,
            "null_threshold": 0.05,
        },
        "architecture": {
            "description": "Data flows from raw to refined to gold layer",
        },
    }


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Setup wizard for DBT Migration Agents"
    )
    parser.add_argument(
        "--defaults",
        action="store_true",
        help="Use default values (for testing)",
    )
    parser.add_argument(
        "--output",
        default="config/migration_config.yaml",
        help="Output path for configuration file",
    )
    args = parser.parse_args()

    # Determine base path (parent of this script)
    base_path = Path(__file__).parent

    # Collect or generate configuration
    if args.defaults:
        print("Using default configuration values...")
        config = run_with_defaults()
    else:
        config = collect_configuration()

    # Generate YAML
    yaml_content = generate_yaml(config)

    # Show preview
    print("\n" + "=" * 60)
    print("Configuration Preview")
    print("=" * 60)
    print(yaml_content)

    # Confirm
    if not args.defaults:
        confirm = get_input("\nSave this configuration? (y/n)", "y")
        if confirm.lower() != "y":
            print("Configuration cancelled.")
            sys.exit(0)

    # Write configuration
    config_path = base_path / args.output
    config_path.parent.mkdir(parents=True, exist_ok=True)

    with open(config_path, "w") as f:
        f.write(yaml_content)

    print(f"\nConfiguration saved to: {config_path}")

    # Create directories
    create_directories(config, base_path)

    # Validate configuration
    print("\nValidating configuration...")
    try:
        sys.path.insert(0, str(base_path))
        from config.config_loader import load_config

        load_config(str(config_path))
        print("Configuration is valid.")
    except Exception as e:
        print(f"Warning: Configuration validation failed: {e}")

    # Final instructions
    print("\n" + "=" * 60)
    print("Setup Complete")
    print("=" * 60)
    print("\nNext steps:")
    print("1. Review config/migration_config.yaml")
    print("2. Generate DBT manifest: dbt parse")
    print("3. Start Claude Code and run: /migrate-cookbook-generator")
    print("\nSee README.md for detailed usage instructions.")


if __name__ == "__main__":
    main()
