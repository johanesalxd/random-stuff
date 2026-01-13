# Changelog

All notable changes to DBT Migration Agents will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.0.0] - 2025

### Added

- Generic template framework for any DBT + BigQuery project
- YAML configuration file (`config/migration_config.yaml`)
- Configuration loader utility with validation
- Interactive setup wizard (`setup.py`)
- Parameterized agent definitions with config placeholders
- Parameterized cookbook templates
- Comprehensive documentation (README, SETUP_GUIDE, CUSTOMIZATION)
- Support for multiple GCP project architectures
- Configurable validation thresholds

### Changed

- All hardcoded project names replaced with config references
- All hardcoded paths replaced with config references
- Agents now read configuration at runtime
- Output directories configurable via config

### Removed

- Project-specific hardcoded values
- Direct references to specific GCP projects

## [1.0.0] - 2024

### Added

- Initial implementation for specific DBT project
- 5 specialized migration agents
- Orchestrator command `/migrate-cookbook-generator`
- Lineage analysis (DBT and BigQuery)
- PRD generation
- Validation with RCA
- Migration cookbook generation
