# AGENTS.md

Agent instructions for `bq_caapi_ge` -- Conversational Analytics API data agents with Gemini Enterprise integration via built-in A2A protocol.

## Project Overview

- **Language:** Python 3.11 (`>=3.11,<3.12`)
- **Package manager:** `uv` (lockfile: `uv.lock`)
- **Core deps:** CA API (`google-cloud-geminidataanalytics`), `python-dotenv`
- **Optional deps:** Google ADK (`google-adk`) -- only for `advanced/` path
- **Linter/Formatter:** Ruff with default config (no `ruff.toml` or `[tool.ruff]`)
- **Tests:** None configured. If added, use `pytest` in a `tests/` directory.

## Build, Lint, and Run Commands

```bash
# Install dependencies (default path)
uv sync
uv sync --group dev          # includes ruff

# Install dependencies (advanced path -- adds google-adk)
uv sync --extra advanced

# Lint and format
uv run ruff check .           # lint
uv run ruff check --fix .     # lint with auto-fix
uv run ruff format .          # format
uv run ruff format --check .  # format check (CI)

# Default path: create agents and register in GE
uv run python scripts/admin_tools.py
uv run python scripts/register_ge_agents.py \
    --agents agent_id_1 agent_id_2 --auth-id bq-caapi-oauth

# Advanced path: ADK agent runtime
export $(cat .env | xargs)
uv run adk run advanced/app/orders
bash advanced/scripts/deploy_agents.sh
uv run python advanced/scripts/setup_auth.py
uv run python advanced/scripts/register_agents.py --orders-resource <RESOURCE>
```

If tests are added, run a single test with:
```bash
uv run pytest tests/test_module.py::test_function -v
```

## Project Structure

```
scripts/                        # Shared + default path scripts
  admin_tools.py                # Create/update CA API Data Agents (both paths)
  register_ge_agents.py         # Fetch A2A card, register in GE (default path)
advanced/                       # Custom ADK runtime path (optional)
  app/                          # ADK agent packages (deployable units)
    orders/                     # Orders Analyst agent
    inventory/                  # Inventory Analyst agent
  scripts/                      # Advanced deployment scripts
    deploy_agents.sh            # Deploy to Vertex AI Agent Engine
    setup_auth.py               # Create OAuth auth resources (standalone)
    register_agents.py          # Register ADK agents in GE (adkAgentDefinition)
  test_web/                     # Flask OAuth test harness
  docs/examples/                # Reference implementations (print() is OK here)
```

## Code Style

### Formatting

- **Line length:** 88 characters (Ruff default)
- **Indentation:** 4 spaces
- **Quotes:** Double quotes
- **Trailing commas:** Use in multi-line structures

### Imports

Order (enforced by Ruff isort):
1. `from __future__ import annotations` (always first)
2. Standard library (`json`, `logging`, `os`, `datetime`, etc.)
3. Third-party (`google.adk`, `google.cloud`, `dotenv`, `flask`)
4. Local/relative imports

```python
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timedelta
from typing import Any, Optional

from google.adk.agents import Agent
from google.adk.tools.base_tool import BaseTool
```

### Type Annotations

- Every module starts with `from __future__ import annotations`
- Use lowercase generics: `dict[str, Any]`, `list[str]` (not `Dict`, `List`)
- Use PEP 604 unions: `str | None` (enabled by future annotations)
- Use `Optional[dict]` for return types (existing codebase convention)
- Type-annotate all function parameters and return values

### Naming Conventions

- **Functions/variables:** `snake_case` (`bridge_oauth_token`, `get_bq_refs`)
- **Constants:** `UPPER_SNAKE_CASE` (`PROJECT_ID`, `MODEL_NAME`, `SCOPES`)
- **Classes:** `PascalCase` (framework classes only; no custom classes)
- **Modules/files:** `snake_case` (`admin_tools.py`, `setup_auth.py`)
- **Agent names:** `snake_case` strings (`"orders_analyst"`, `"inventory_analyst"`)

### Logging

- Use `logging` module. Never use `print()` in agent or script code.
  (`print` is acceptable only in `advanced/docs/examples/` and `advanced/test_web/`.)
- Module-level setup:
  ```python
  logging.basicConfig(level=logging.INFO)
  logger = logging.getLogger(__name__)
  ```
- Scripts use extended format: `"%(asctime)s - %(name)s - %(levelname)s - %(message)s"`
- Use f-strings in log messages (project convention, not `%s` style)

### Docstrings

Google-style docstrings on all public functions and script modules.
Include `Args:`, `Returns:`, `Raises:` sections where applicable:

```python
def create_auth_resource(auth_id: str) -> None:
    """Create an OAuth authorization resource in Gemini Enterprise.

    Args:
        auth_id: The authorization resource ID to create.

    Raises:
        ValueError: If OAUTH_CLIENT_ID or OAUTH_CLIENT_SECRET is not set.
    """
```

### Error Handling

- Raise `ValueError` for missing configuration or invalid input
- Catch specific exceptions, not bare `except Exception`
- Log errors with `logger.error()` and include `exc_info=True` when re-raising
- For "already exists" cases, catch and log as info rather than failing
- Use `check=False` with `subprocess.run` when handling errors manually;
  use `check=True` or `check_output` when failure should propagate

### Configuration

- All config via environment variables using `os.getenv()` with sensible defaults
- Use `python-dotenv` (`load_dotenv()`) for `.env` files
- Root `.env` for shared config; per-agent `.env` in `advanced/app/<agent>/`
- Never hardcode secrets; `.env` files are gitignored

### Agent Module Pattern

Each agent package (`advanced/app/orders/`, `advanced/app/inventory/`) follows:
- `__init__.py` re-exports: `from . import agent as agent`
- `agent.py` defines: module-level config, async `bridge_oauth_token` callback,
  `DataAgentCredentialsConfig`, `DataAgentToolset`, and a `root_agent` variable
- The `root_agent` variable name is required by the ADK framework

### Shell Scripts

- Use `#!/bin/bash` and `set -e`
- Validate required env vars early with clear error messages
- Use color codes for output (`RED`, `GREEN`, `YELLOW`, `NC`)
- Load `.env` with `export $(cat .env | xargs)`

## Environment and Secrets

- `.env` files are gitignored -- never commit them
- See `.env.example` for required variables
- Per-agent `.env` files: `advanced/app/orders/.env`, `advanced/app/inventory/.env`
- `OAUTH_CLIENT_ID` and `OAUTH_CLIENT_SECRET` are required for all operations
- `GOOGLE_GENAI_USE_VERTEXAI=TRUE` must be set for ADK to use Vertex AI
