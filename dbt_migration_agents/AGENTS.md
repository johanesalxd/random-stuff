# Agent Guidelines for DBT Migration Agents

This file provides instructions for AI agents working in this repository.

## 1. Build, Lint, and Test Commands

### Dependencies & Setup
- **Install dependencies:** `pip install -e .[dev]`
- **Install dev dependencies:** `pip install -e .[dev,lineage]`
- **Setup Wizard:** `python setup.py` (generates `config/migration_config.yaml`)

### Linting & Formatting
The project uses `black` and `isort` for formatting.
- **Format code:** `black . && isort .`
- **Check formatting:** `black --check . && isort --check-only .`
- **Configuration:** Settings are in `pyproject.toml`.
  - Line length: 88
  - Target version: Python 3.8+

### Testing
Tests are configured to use `pytest`.
- **Run all tests:** `pytest`
- **Run a single test file:** `pytest tests/test_file.py`
- **Run a single test function:** `pytest tests/test_file.py::test_function_name`
- **Note:** The `tests/` directory is currently referenced in `pyproject.toml` but may not be present in the repo. If adding tests, place them in `tests/` and follow the `test_*.py` naming convention.

## 2. Code Style Guidelines

### Python Style
- **Formatting:** Strictly adhere to `black` and `isort`.
- **Type Hinting:**
  - Use type hints for **all** function arguments and return values.
  - Use `typing` module (e.g., `List`, `Dict`, `Optional`, `Any`) for compatibility with older Python versions if necessary (>=3.8).
  - Example: `def get_config_value(config: Dict[str, Any], key: str) -> Optional[Any]:`
- **Naming Conventions:**
  - Classes: `PascalCase` (e.g., `ConfigurationError`)
  - Functions & Variables: `snake_case` (e.g., `load_config`, `project_id`)
  - Constants: `UPPER_CASE`
- **Docstrings:**
  - Use Google-style docstrings for all modules, classes, and public functions.
  - Sections: `Args:`, `Returns:`, `Raises:`.
  - Example:
    ```python
    def validate_path(path: str) -> bool:
        """
        Validate path format.

        Args:
            path: Path to validate.

        Returns:
            True if valid, False otherwise.
        """
    ```
- **Error Handling:**
  - Use specific custom exceptions where appropriate (e.g., `ConfigurationError`).
  - Catch specific exceptions rather than bare `except:`.

### Imports
- **Order:** Standard library -> Third-party -> Local application.
- **Style:** Absolute imports preferred.
- **Sorting:** Handled by `isort`.

### File Operations
- **Paths:** Use `pathlib.Path` for path manipulations instead of `os.path`.
- **Reading/Writing:** context managers (`with open(...)`) are required.

## 3. Project Structure & Architecture

### Core Components
- **`config/`**: Configuration loading and validation (`config_loader.py`).
- **`lineage_analyzer/`**: Analyzes DBT lineage.
- **`prd_generator/`**: Generates migration requirements.
- **`migration_validator/`**: Validates data parity between layers.
- **`code_refactor/`**: Generates DBT code.
- **`sample_project/`**: A sample DBT project for testing agents.

### Agent Workflow
This repository defines several agents (in `.agents/agents/`) that orchestrate the migration process:
1.  **Lineage Analyzer**: Maps dependencies.
2.  **PRD Generator**: Plans the migration.
3.  **Cookbook Generator**: Creates the migration guide.
4.  **Validation Subagent**: Verifies the result.

### Rules for Modification
- **Config:** Do not hardcode project-specific values. Use `config_loader.py` to fetch from `migration_config.yaml`.
- **Output:** Agents write outputs to directories defined in `config/migration_config.yaml` (default: `migration_outputs/`).
- **Safety:** Always validate paths and project IDs before using them (see `setup.py` validators).

## 4. Development Workflow

### Adding a New Feature
1.  **Create a Branch:** Start a new branch for your feature.
2.  **Design:** if complex, check `docs/` for architecture guides.
3.  **Implement:** Write code following the style guidelines.
4.  **Format:** Run `black . && isort .` frequently.
5.  **Verify:**
    - If adding a new agent capability, test it against the `sample_project`.
    - Run `pytest` (if applicable).

### Using the Sample Project
The `sample_project/` directory is the primary integration test bed.
1.  **Configure:** Copy `config/migration_config.example.yaml` to `config/migration_config.yaml` and point it to the sample project.
    ```yaml
    project:
      name: "sample_project"
      manifest_path: "sample_project/target/manifest.json"
    dbt:
      staging_models: "sample_project/models/silver"
      # ... other paths relative to root or absolute
    ```
2.  **Generate Manifest:** Run `dbt parse` inside `sample_project`.
3.  **Run Agents:** Execute the agent commands against the sample models (e.g., `models/gold/fct_orders_broken.sql`).

## 5. Troubleshooting & Common Issues

- **Import Errors:** Ensure you have installed the package in editable mode (`pip install -e .`).
- **Config Errors:** The `config_loader.py` is strict. Ensure `migration_config.yaml` exists and has all required sections.
- **Path Issues:**
    - Always use `pathlib.Path`.
    - Be aware of the difference between execution root (repo root) and dbt project root.
    - Configuration paths should generally be relative to the repo root or absolute.

## 6. Git Commit Messages
- **Format:** `type(scope): subject`
- **Types:**
    - `feat`: New feature
    - `fix`: Bug fix
    - `docs`: Documentation only
    - `style`: Formatting, missing semi-colons, etc.
    - `refactor`: Code change that neither fixes a bug nor adds a feature
    - `test`: Adding missing tests
    - `chore`: Maintain
- **Example:** `feat(lineage): add support for external tables`
