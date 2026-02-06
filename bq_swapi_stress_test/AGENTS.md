# AGENTS.md

Agent instructions for `bq_swapi_stress_test` -- an Apache Beam streaming pipeline that stress-tests BigQuery Storage Write API throughput with synthetic e-commerce data.

## Project Overview

- **Language:** Python 3.13 (`.python-version`), `requires-python = ">=3.10"` in `pyproject.toml`
- **Package manager:** `uv` (lockfile: `uv.lock`; no `requirements.txt`)
- **Framework:** Apache Beam (`apache-beam[gcp]>=2.50.0`)
- **Linter/Formatter:** Ruff with default config (no `ruff.toml`, no `[tool.ruff]` section)
- **Tests:** None exist. No test framework is configured.
- **Architecture:** Single-file project. All pipeline logic is in `src/bq_stress_test.py`.

## Build and Run Commands

```bash
# Install dependencies (always use uv, never pip)
uv sync

# Lint and format (run both before every commit)
uv run ruff check .          # lint only
uv run ruff check --fix .    # lint with auto-fix
uv run ruff format .         # format in-place
uv run ruff format --check . # format dry-run

# Submit Dataflow streaming job (requires env vars below)
./run.sh

# Cancel running jobs
./cancel.sh        # interactive confirmation
./cancel.sh -f     # force, no prompt

# Run pipeline directly (local DirectRunner or custom)
uv run python src/bq_stress_test.py \
  --output_table=PROJECT:DATASET.TABLE \
  --runner=DirectRunner
```

### Required Environment Variables (for `run.sh`)

```bash
export GCP_PROJECT="your-project-id"
export GCP_REGION="asia-southeast1"
export GCP_TEMP_BUCKET="gs://your-bucket/dataflow/stress-test"
```

### Testing

No tests exist yet. If adding tests:
- Directory: `tests/` mirroring `src/` structure
- Framework: `pytest`
- Run all: `uv run pytest`
- Run single test: `uv run pytest tests/test_file.py::test_function_name`
- Run by keyword: `uv run pytest -k "test_generate"`

## Project Structure

```
src/bq_stress_test.py   # All pipeline logic: constants, data gen, Beam pipeline
run.sh                   # Drop/create BQ table, submit Dataflow job
cancel.sh                # Find and cancel active Dataflow jobs
pyproject.toml           # Project metadata and dependencies
uv.lock                  # Pinned dependency versions
.python-version          # Python 3.13
```

## Code Style

### Formatting

- **Tool:** Ruff (default config -- 88 char line length, 4-space indent, double quotes)
- **Trailing commas:** Required in multi-line structures (lists, dicts, function args)
- **Pre-commit step:** Always run `uv run ruff format . && uv run ruff check --fix .`

### Imports

Three groups separated by blank lines, enforced by Ruff isort:

```python
# 1. Standard library
import argparse
import json
import logging
import time
import uuid

# 2. Third-party
import apache_beam as beam
from apache_beam.options.pipeline_options import PipelineOptions, StandardOptions
from apache_beam.utils.timestamp import Timestamp

# 3. Local (none currently)
```

Use specific imports, never wildcard (`from module import *`).

### Type Annotations

- Annotate all function parameters and return values
- Use built-in generics (`dict`, `list`, `str`, `int`), not `typing.Dict`/`typing.List`
- For Beam elements with version-dependent types, use untyped param + `hasattr` guard:

```python
def generate_transaction(element) -> dict:
    seq_num = element.value if hasattr(element, "value") else element
```

### Naming

| Kind | Convention | Examples |
|------|-----------|----------|
| Functions/variables | `snake_case` | `generate_transaction`, `unit_price` |
| Constants | `UPPER_SNAKE_CASE` | `PRODUCTS`, `TABLE_SCHEMA`, `PAYMENT_METHODS` |
| Files | `snake_case` | `bq_stress_test.py` |
| Classes | `PascalCase` | (none in this project currently) |

### Docstrings

Google-style. Required on all public functions and the module itself.

```python
def generate_address_blob(element: int) -> str:
    """Generate a ~4.7KB shipping address JSON blob.

    This is the "fat" field that brings row size to ~5KB total.
    Uses deterministic generation for reproducibility.

    Args:
        element: Sequence number from GenerateSequence.

    Returns:
        JSON string of the address structure.
    """
```

### Error Handling and Logging

- Use `logging` module exclusively -- never `print()` in pipeline code
- Configure at entry point: `logging.getLogger().setLevel(logging.INFO)`
- Use `logging.info()` for status messages
- Let Beam handle retries and quota errors internally
- Use `argparse` with `required=True` for mandatory CLI arguments

### Data Generation Conventions

- All generated data must be **deterministic** from the sequence number (no `random`)
- Cycle through constant lists with modulo: `PRODUCTS[seq_num % len(PRODUCTS)]`
- Use `json.dumps()` for structured blob fields
- Use `uuid.UUID(int=n)` for deterministic UUIDs

### Shell Scripts

- Shebang: `#!/bin/bash` with `set -e`
- Environment variables with defaults: `PROJECT="${GCP_PROJECT:-your-project-id}"`
- Quote all variable expansions
- Use `2>/dev/null || true` for optional/cleanup operations
- Provide `echo` feedback for each step

### Secrets and Configuration

- All config via environment variables -- never hardcode project IDs or credentials
- `.env` files are gitignored
- `run.sh` unsets `GOOGLE_APPLICATION_CREDENTIALS` to rely on ADC

## Workflow

1. **Before editing:** Read `pyproject.toml` and `src/bq_stress_test.py`
2. **After editing:** Run `uv run ruff format . && uv run ruff check --fix .`
3. **Verify locally:** Use `DirectRunner` for logic changes when possible
4. **Commits:** Conventional commits (`feat:`, `fix:`, `docs:`, `refactor:`)
5. **Cost warning:** `./run.sh` submits a Dataflow job (~$12 per 10-minute run)
