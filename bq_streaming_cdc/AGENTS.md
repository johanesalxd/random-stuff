# AGENTS.md

This document provides operational guidelines for AI agents working in the `bq_streaming_cdc` project. This project demonstrates BigQuery Change Data Capture (CDC) using the Storage Write API and dynamic Protobuf generation.

## 1. Environment & Build

This project uses `uv` for dependency management and execution.

### Project Setup
- **Initialize**: `uv sync` (installs dependencies from `uv.lock`)
- **Add Dependency**: `uv add <package>`
- **Add Dev Dependency**: `uv add --dev <package>`

### Execution
- **Run Python Scripts**: `uv run <script_name.py>`
- **Run Demo**: `./run_demo.sh` (ensure `chmod +x` is set)

### Testing & Verification
- **Run Tests**: `uv run pytest` (if tests are added in the future)
- **Linting**: `uv run ruff check .`
- **Formatting**: `uv run ruff format .`

> **Note**: Always use `uv run` to execute commands within the virtual environment context. Do not manually activate venvs unless instructed.

## 2. Code Style & Standards

Adhere to the following conventions when writing or modifying Python code in this project.

### General Philosophy
- **Readability First**: Prefer explicit over implicit.
- **Modern Python**: Use Python 3.11+ features (type hinting, f-strings).
- **Structure**: Keep the structure flat. The `BigQueryCDCWriter` and `CDCSchemaFactory` pattern in `stream_cdc.py` is the established pattern.

### Formatting
- **Tool**: Use `ruff` for all formatting.
- **Line Length**: Default (88 chars).
- **Quotes**: Double quotes `"` for strings.
- **Imports**: Sorted automatically by `ruff`. Group standard library, third-party, then local.

### Naming Conventions
- **Files**: `snake_case.py` (e.g., `stream_cdc.py`)
- **Classes**: `PascalCase` (e.g., `BigQueryCDCWriter`)
- **Functions/Variables**: `snake_case` (e.g., `append_rows`, `dataset_id`)
- **Constants**: `UPPER_SNAKE_CASE` (e.g., `PROJECT_ID`)
- **Private Members**: Prefix with `_` (e.g., `_create_proto_row`)

### Type Hinting
- **Strictness**: All function signatures should have type hints.
- **Imports**: Use `typing` module (`List`, `Dict`, `Any`, `Type`, `Optional`).
- **Return Types**: Explicitly state return types, including `-> None`.

```python
def process_data(items: List[Dict[str, Any]]) -> bool:
    ...
```

### Documentation (Docstrings)
- **Style**: Google Style Docstrings.
- **Requirement**: Required for all public classes and methods.
- **Format**:
  ```python
  def connect(self, timeout: int = 30) -> None:
      """
      Establishes a connection to the service.

      Args:
          timeout: The max time to wait in seconds.

      Raises:
          ConnectionError: If the connection fails.
      """
  ```

### Error Handling
- **Logging**: Use the standard `logging` module. Do NOT use `print` for application logs (except for CLI output in simple scripts like `create_table.py`).
- **Pattern**: Catch specific exceptions when possible.
- **Tracebacks**: Use `logger.exception("Message")` inside `except` blocks to capture stack traces.

### BigQuery / Cloud Specifics
- **Clients**: Instantiate clients (`bigquery.Client`, `BigQueryWriteClient`) inside classes or main functions.
- **Credentials**: Prefer `GOOGLE_APPLICATION_CREDENTIALS` or ADC.
- **Protobuf**: Use `descriptor_pb2` to dynamically generate Protobuf classes matching the table schema + CDC fields (`_CHANGE_TYPE`, `_CHANGE_SEQUENCE_NUMBER`). Avoid adding external `.proto` files unless necessary for performance.

## 3. Workflow for Agents

1.  **Exploration**: Check `pyproject.toml` to confirm dependencies.
2.  **Modification**:
    -   Plan changes first.
    -   Write code.
    -   **Immediately** run `uv run ruff format .` and `uv run ruff check . --fix`.
3.  **Verification**:
    -   Use `./run_demo.sh` to verify end-to-end functionality.
    -   If modifying `stream_cdc.py`, ensure `verify_table_content()` still passes.
4.  **Committing**:
    -   Update `README.md` if behavior changes.
    -   Use conventional commits (e.g., `feat:`, `fix:`, `docs:`).

## 4. Specific Configuration Files

- **.gitignore**: Ensure `.python-version`, `.venv/`, `__pycache__/` are ignored.
- **pyproject.toml**: Used for `uv` project definition.
