"""
Configuration Loader for DBT Migration Agents.

Provides functions to load, validate, and access migration configuration
from migration_config.yaml.

Usage:
    from config.config_loader import load_config, get_config_value

    config = load_config()
    billing_project = get_config_value(config, 'gcp.billing_project')
"""

import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional

import yaml


class ConfigurationError(Exception):
    """Raised when configuration is invalid or missing."""

    pass


def find_config_file(config_path: Optional[str] = None) -> Path:
    """
    Find the migration configuration file.

    Args:
        config_path: Optional explicit path to config file.

    Returns:
        Path to the configuration file.

    Raises:
        ConfigurationError: If config file cannot be found.
    """
    if config_path:
        path = Path(config_path)
        if path.exists():
            return path
        raise ConfigurationError(f"Config file not found: {config_path}")

    # Search in common locations
    search_paths = [
        Path("config/migration_config.yaml"),
        Path("migration_config.yaml"),
        Path("dbt_migration_agents/config/migration_config.yaml"),
    ]

    # Also check from script location
    script_dir = Path(__file__).parent
    search_paths.append(script_dir / "migration_config.yaml")

    for path in search_paths:
        if path.exists():
            return path

    raise ConfigurationError(
        "Config file not found. Searched:\n"
        + "\n".join(f"  - {p}" for p in search_paths)
        + "\n\nPlease create migration_config.yaml from the example file."
    )


def load_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Load and validate migration configuration.

    Args:
        config_path: Optional explicit path to config file.

    Returns:
        Dictionary containing configuration values.

    Raises:
        ConfigurationError: If config is invalid or missing required fields.
    """
    config_file = find_config_file(config_path)

    try:
        with open(config_file, "r") as f:
            config = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise ConfigurationError(f"Invalid YAML in config file: {e}")

    if config is None:
        raise ConfigurationError("Config file is empty")

    # Validate required sections
    required_sections = ["project", "gcp", "dbt", "outputs"]
    for section in required_sections:
        if section not in config:
            raise ConfigurationError(f"Missing required section: {section}")

    # Validate required GCP settings
    if "billing_project" not in config.get("gcp", {}):
        raise ConfigurationError("Missing required: gcp.billing_project")

    if "projects" not in config.get("gcp", {}):
        raise ConfigurationError("Missing required: gcp.projects")

    return config


def get_config_value(config: Dict[str, Any], key_path: str, default: Any = None) -> Any:
    """
    Get a configuration value using dot notation.

    Args:
        config: Configuration dictionary.
        key_path: Dot-separated path to value (e.g., 'gcp.billing_project').
        default: Default value if key not found.

    Returns:
        Configuration value or default.

    Examples:
        get_config_value(config, 'gcp.billing_project')
        get_config_value(config, 'gcp.projects.refined')
        get_config_value(config, 'validation.row_count_threshold', 0.001)
    """
    keys = key_path.split(".")
    value = config

    for key in keys:
        if isinstance(value, dict) and key in value:
            value = value[key]
        else:
            return default

    return value


def get_gcp_project(config: Dict[str, Any], layer: str) -> str:
    """
    Get GCP project ID for a specific data layer.

    Args:
        config: Configuration dictionary.
        layer: Layer name (bronze, silver, gold).

    Returns:
        GCP project ID for the layer.

    Raises:
        ConfigurationError: If layer is not configured.
    """
    project = get_config_value(config, f"gcp.projects.{layer}")
    if not project:
        raise ConfigurationError(f"GCP project not configured for layer: {layer}")
    return project


def get_dbt_path(config: Dict[str, Any], path_type: str) -> str:
    """
    Get DBT path for a specific type.

    Args:
        config: Configuration dictionary.
        path_type: Path type (bronze_models, silver_models, gold_models, seeds).

    Returns:
        DBT path string.

    Raises:
        ConfigurationError: If path type is not configured.
    """
    path = get_config_value(config, f"dbt.{path_type}")
    if not path:
        raise ConfigurationError(f"DBT path not configured: {path_type}")
    return path


def get_output_path(config: Dict[str, Any], output_type: str) -> Path:
    """
    Get output path for a specific type.

    Args:
        config: Configuration dictionary.
        output_type: Output type (lineage, prd, validation, cookbooks).

    Returns:
        Path object for output directory.

    Raises:
        ConfigurationError: If output type is not configured.
    """
    path = get_config_value(config, f"outputs.{output_type}")
    if not path:
        raise ConfigurationError(f"Output path not configured: {output_type}")
    return Path(path)


def get_validation_threshold(config: Dict[str, Any], threshold_type: str) -> float:
    """
    Get validation threshold value.

    Args:
        config: Configuration dictionary.
        threshold_type: Threshold type (row_count_threshold, null_threshold).

    Returns:
        Threshold value as float.
    """
    defaults = {"row_count_threshold": 0.001, "null_threshold": 0.05}

    return get_config_value(
        config, f"validation.{threshold_type}", defaults.get(threshold_type, 0.01)
    )


def get_architecture_description(config: Dict[str, Any]) -> str:
    """
    Get data architecture description for documentation.

    Args:
        config: Configuration dictionary.

    Returns:
        Architecture description string.
    """
    return get_config_value(
        config, "architecture.description", "Data platform architecture."
    )


def print_config_summary(config: Dict[str, Any]) -> None:
    """
    Print a summary of the loaded configuration.

    Args:
        config: Configuration dictionary.
    """
    print("=" * 60)
    print("DBT Migration Agents Configuration Summary")
    print("=" * 60)
    print(f"Project: {get_config_value(config, 'project.name')}")
    print(f"Billing Project: {get_config_value(config, 'gcp.billing_project')}")
    print()
    print("GCP Projects:")
    for layer in ["bronze", "silver", "gold"]:
        project = get_config_value(config, f"gcp.projects.{layer}", "(not set)")
        print(f"  {layer}: {project}")
    print()
    print("DBT Paths:")
    for path_type in ["bronze_models", "silver_models", "gold_models", "seeds"]:
        path = get_config_value(config, f"dbt.{path_type}", "(not set)")
        print(f"  {path_type}: {path}")
    print("=" * 60)


if __name__ == "__main__":
    """CLI tool to validate and display configuration."""
    try:
        config_path = sys.argv[1] if len(sys.argv) > 1 else None
        config = load_config(config_path)
        print_config_summary(config)
        print("\nConfiguration is valid.")
    except ConfigurationError as e:
        print(f"Configuration Error: {e}", file=sys.stderr)
        sys.exit(1)
