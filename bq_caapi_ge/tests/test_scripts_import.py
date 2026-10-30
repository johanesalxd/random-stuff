"""Smoke tests verifying that CLI scripts can be invoked with --help without import errors."""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import tempfile

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _run_help(script: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(script), "--help"],
        cwd=tempfile.gettempdir(),
        capture_output=True,
        text=True,
        check=False,
    )


def test_register_agents_help() -> None:
    result = _run_help(PROJECT_ROOT / "advanced" / "scripts" / "register_agents.py")
    assert result.returncode == 0
    assert "register_agents.py" in result.stdout or "usage:" in result.stdout.lower()


def test_setup_auth_help() -> None:
    result = _run_help(PROJECT_ROOT / "advanced" / "scripts" / "setup_auth.py")
    assert result.returncode == 0
    assert "setup_auth.py" in result.stdout or "usage:" in result.stdout.lower()


def test_register_ge_agents_help() -> None:
    result = _run_help(PROJECT_ROOT / "scripts" / "register_ge_agents.py")
    assert result.returncode == 0
    assert "register_ge_agents.py" in result.stdout or "usage:" in result.stdout.lower()


def test_chart_with_ca_api_help() -> None:
    import pytest

    pytest.importorskip("requests")
    result = _run_help(
        PROJECT_ROOT / "advanced" / "docs" / "examples" / "chart_with_ca_api.py"
    )
    assert result.returncode == 0
    assert "chart_with_ca_api.py" in result.stdout or "usage:" in result.stdout.lower()
