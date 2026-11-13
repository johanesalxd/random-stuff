"""Validation and sequential execution tests for the beyond_bqca_walkthrough notebook."""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

PROJECT_ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK_PATH = PROJECT_ROOT / "notebooks" / "beyond_bqca_walkthrough.ipynb"

FORBIDDEN_PORTABILITY_PATTERN = re.compile(
    r"(\b[a-z0-9-]+\.corp\.google\.com\b"
    r"|\bgo/[a-z0-9_-]+"
    r"|\b(?:b|cl)/\d{4,}"
    r"|/(?:home|Users)/[A-Za-z0-9_.-]+)",
    re.IGNORECASE,
)


def test_notebook_json_structure_and_hygiene() -> None:
    """Verifies NBFormat v4 structure, unexecuted state, and portable hygiene."""
    assert NOTEBOOK_PATH.is_file(), f"Notebook missing at {NOTEBOOK_PATH}"

    raw_text = NOTEBOOK_PATH.read_text(encoding="utf-8")

    # 1. Portability and internal-link assertions (without embedding private literals)
    match_forbidden = FORBIDDEN_PORTABILITY_PATTERN.search(raw_text)
    assert match_forbidden is None, (
        f"Found non-portable reference '{match_forbidden.group(0)}' in notebook"
    )

    # 2. JSON and NBFormat validation
    data = json.loads(raw_text)
    assert data.get("nbformat") == 4
    assert data.get("nbformat_minor") == 5
    assert "colab" not in (data.get("metadata") or {})
    assert "cells" in data and isinstance(data["cells"], list)

    code_cells = [c for c in data["cells"] if c.get("cell_type") == "code"]
    assert len(code_cells) >= 5, f"Expected at least 5 code cells, found {len(code_cells)}"

    # 3. All code cells must be unexecuted (outputs empty, execution_count None)
    for idx, cell in enumerate(code_cells, 1):
        assert cell.get("outputs") == [], f"Code cell {idx} has non-empty outputs"
        assert cell.get("execution_count") is None, f"Code cell {idx} has non-None execution_count"


def test_notebook_sequential_execution_offline() -> None:
    """Executes all notebook code cells sequentially in an isolated subprocess with scrubbed environment."""
    data = json.loads(NOTEBOOK_PATH.read_text(encoding="utf-8"))
    code_blocks: list[str] = []

    for cell in data["cells"]:
        if cell.get("cell_type") == "code":
            source = "".join(cell.get("source", []))
            code_blocks.append(source)

    combined_script = "\n\n# --- CELL DIVIDER ---\n\n".join(code_blocks)

    # Scrub environment to guarantee offline safety
    env = dict(os.environ)
    env.pop("GOOGLE_CLOUD_PROJECT", None)
    env.pop("BQ_COMPUTE_PROJECT", None)
    env.pop("RUN_LIVE_BQ", None)
    env["PYTHONPATH"] = str(PROJECT_ROOT)
    env["BQCA_REPO_ROOT"] = str(PROJECT_ROOT)

    res = subprocess.run(
        [sys.executable, "-c", combined_script],
        cwd=tempfile.gettempdir(),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert res.returncode == 0, (
        f"Notebook execution failed with returncode {res.returncode}.\n"
        f"STDERR:\n{res.stderr}\n"
        f"STDOUT:\n{res.stdout}"
    )
    assert "Skipping live BigQuery execution" in res.stdout
    assert "Loaded 2 semantic contracts" in res.stdout
