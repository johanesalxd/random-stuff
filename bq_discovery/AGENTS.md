# AGENTS.md — bq-discovery

Agent directives for this repository. Follow these rules precisely; they
take precedence over global agent defaults where they conflict.

---

## Project overview

`bq-discovery` is a Python CLI tool that scans BigQuery IAM policies and
dataset ACLs across a GCP organization using Cloud Asset Inventory and the
BigQuery API. Output is written as JSON, JSONL, or CSV for direct `bq load`
import.

Key modules:
- `bq_discovery/cli.py` — argument parsing and entry point
- `bq_discovery/scanner.py` — orchestration: resolves projects, fans out scanners
- `bq_discovery/iam_scanner.py` — Cloud Asset Inventory `searchAllIamPolicies`
- `bq_discovery/acl_scanner.py` — BigQuery dataset legacy ACLs
- `bq_discovery/models.py` — `PermissionEntry`, `ScanResult`, enums
- `bq_discovery/resolvers/` — project listing and group membership expansion

---

## Environment

- **Python:** 3.12+ required
- **Package manager:** `uv` exclusively — never use pip, poetry, or pip-tools
- **Config:** `pyproject.toml` only — no `requirements.txt`, `setup.py`

---

## Commands

### Install / sync dependencies

```bash
uv sync
```

### Run the tool

```bash
# Application default credentials must be set first
env -u GOOGLE_APPLICATION_CREDENTIALS \
  uv run bq-discovery --org-id YOUR_ORG_ID -v
```

### Lint

```bash
uv run ruff check .
uv run ruff format --check .
```

### Format (auto-fix)

```bash
uv run ruff format .
uv run ruff check --fix .
```

### Run all tests

```bash
uv run pytest
```

### Run a single test file

```bash
uv run pytest tests/test_iam_scanner.py
```

### Run a single test by name

```bash
uv run pytest tests/test_iam_scanner.py::test_parse_resource_name_table
```

### Run tests matching a keyword

```bash
uv run pytest -k "member_type"
```

---

## Code style

### Formatting

- Line length: **88 characters** (ruff default, configured in `pyproject.toml`)
- `ruff` handles all formatting — do not introduce `black` or `isort`
- ruff lint rules active: `E`, `F`, `I` (isort), `N` (naming), `W`

### Imports

Always include `from __future__ import annotations` as the first import.
Three groups, separated by blank lines, alphabetically sorted within each:

```python
from __future__ import annotations

import csv
import logging

from google.cloud import asset_v1

from bq_discovery.models import PermissionEntry, ResourceType
```

### Type hints

Use Python 3.10+ union syntax exclusively. Never import from `typing` except
`Any`.

| Use | Not |
|-----|-----|
| `str \| None` | `Optional[str]` |
| `list[str]` | `List[str]` |
| `dict[str, Any]` | `Dict[str, Any]` |
| `tuple[str, str]` | `Tuple[str, str]` |

### Naming

- Functions and variables: `snake_case`
- Classes: `PascalCase`
- Constants / enum values: `UPPER_SNAKE_CASE`
- Private / module-internal: prefix with `_` (e.g. `_parse_resource_name`)
- CLI entry point function: `main`

### Docstrings

Google-style with `Args:`, `Returns:`, `Raises:` sections. Required for all
public functions and classes. Private functions shorter than 5 statements may
omit them.

```python
def scan(project_id: str, dry_run: bool = False) -> list[PermissionEntry]:
    """Scan IAM policies for a single project.

    Args:
        project_id: GCP project ID to scan.
        dry_run: If True, validate inputs but skip API calls.

    Returns:
        List of permission entries found.

    Raises:
        google.api_core.exceptions.PermissionDenied: If credentials lack
            cloudasset.viewer on the project.
    """
```

### Logging

Use `%s` lazy formatting — never f-strings in log calls.

```python
logger = logging.getLogger(__name__)

# Good
logger.info("Scanning project: %s", project_id)
logger.error("Failed to list datasets for %s: %s", project_id, err)

# Bad
logger.info(f"Scanning project: {project_id}")
```

### Error handling

- Raise exceptions with context: `raise ValueError(f"Invalid org_id: {org_id}")`
- Log errors before appending to `ScanResult.errors`; do not swallow silently
- Use `google.api_core.exceptions` types for GCP API errors

### Data models

- Add new resource types to `ResourceType` enum in `models.py`
- New output fields go on `PermissionEntry`; update `to_dict()`, `to_jsonl()`,
  and `to_csv()` in `ScanResult` together
- `PermissionEntry.to_dict()` must remain JSON-serializable (enum `.value`)

---

## Testing

Framework: `pytest`. No unittest classes.

### Conventions

- File: `tests/test_<module>.py`
- Function: `test_<function>_<scenario>` as a standalone function
- Use bare `assert`; use `pytest.raises(ExcType, match="...")` for exceptions
- Tests call internal functions directly — do not test through the CLI
- No mocks for internal logic; only mock external API clients when unavoidable

### Pattern

```python
def test_parse_resource_name_table():
    """Table resource name returns (project, dataset, table)."""
    result = _parse_resource_name(
        "//bigquery.googleapis.com/projects/p/datasets/d/tables/t"
    )
    assert result == ("p", "d", "t")
```

### What to test

- Internal parsing and transformation functions (e.g. `_parse_resource_name`,
  `_extract_member_type`, `_build_asset_types`)
- Model serialization: `to_dict()`, `to_json()`, `to_jsonl()`, `to_csv()`
- CLI argument parsing (`cli.py`) with `argparse` directly
- Edge cases: empty strings, malformed inputs, missing optional fields

### What not to test

- Live GCP API calls — these require credentials and are out of scope
- `main()` end-to-end — test the component functions instead
- Stdlib behavior that isn't part of this codebase's logic

---

## Security guardrails

- Never hardcode credentials, project IDs, org IDs, or user emails in source
- `reports/` is gitignored — never force-add files from that directory
- Public files (README, code) must use generic placeholders (`MY_PROJECT`,
  `proj-a`, `YOUR_ORG_ID`) — no customer-specific values
- Secrets go in environment variables or ADC; never in `pyproject.toml`

---

## Git commit style

Format: `<type>: <subject>` (imperative, ≤50 chars, no trailing period)

Types: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`

```
feat: Add --skip-acls flag to bypass dataset ACL scan
fix: Handle missing dataset_id in project-scoped CAI results
docs: Update README with JSONL loading instructions
```

Do **not** push to remote — remote operations are user-only.
