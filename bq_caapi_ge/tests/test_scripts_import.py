"""Smoke tests verifying that CLI scripts can be invoked with --help without import errors."""

from __future__ import annotations

import os
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


def test_export_semantic_layer_help() -> None:
    result = _run_help(PROJECT_ROOT / "scripts" / "export_semantic_layer.py")
    assert result.returncode == 0
    assert "export_semantic_layer.py" in result.stdout or "usage:" in result.stdout.lower()


def test_verify_bqca_audit_help() -> None:
    result = _run_help(PROJECT_ROOT / "scripts" / "verify_bqca_audit.py")
    assert result.returncode == 0
    assert "verify_bqca_audit.py" in result.stdout or "usage:" in result.stdout.lower()


def test_validate_ca_agent_help() -> None:
    result = _run_help(PROJECT_ROOT / "scripts" / "validate_ca_agent.py")
    assert result.returncode == 0
    assert "validate_ca_agent.py" in result.stdout or "usage:" in result.stdout.lower()


def test_export_semantic_layer_single_format_clean_stdout() -> None:
    import json

    script = PROJECT_ROOT / "scripts" / "export_semantic_layer.py"
    contract = PROJECT_ROOT / "config" / "semantic_contracts" / "thelook_orders.yaml"
    sql_res = subprocess.run(
        [sys.executable, str(script), "--contract", str(contract), "--format", "graph-ddl"],
        cwd=tempfile.gettempdir(),
        capture_output=True,
        text=True,
        check=False,
    )
    assert sql_res.returncode == 0, sql_res.stderr
    assert not sql_res.stdout.startswith("===")
    assert "CREATE OR REPLACE PROPERTY GRAPH" in sql_res.stdout

    json_res = subprocess.run(
        [sys.executable, str(script), "--contract", str(contract), "--format", "datasource-json"],
        cwd=tempfile.gettempdir(),
        capture_output=True,
        text=True,
        check=False,
    )
    assert json_res.returncode == 0, json_res.stderr
    parsed = json.loads(json_res.stdout)
    assert "tableReferences" in parsed


def test_chart_with_ca_api_help() -> None:
    import pytest

    pytest.importorskip("requests")
    result = _run_help(
        PROJECT_ROOT / "advanced" / "docs" / "examples" / "chart_with_ca_api.py"
    )
    assert result.returncode == 0
    assert "chart_with_ca_api.py" in result.stdout or "usage:" in result.stdout.lower()


def test_deploy_agents_stage_only() -> None:
    import shutil

    deploy_script = PROJECT_ROOT / "advanced" / "scripts" / "deploy_agents.sh"
    temp_stage = tempfile.mkdtemp()
    try:
        stage_result = subprocess.run(
            ["bash", str(deploy_script), "--stage-only", temp_stage],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        assert stage_result.returncode == 0, f"deploy_agents.sh failed: {stage_result.stderr}"

        env_file = Path(temp_stage) / "agents" / "semantic_analytics" / ".env"
        assert env_file.exists()
        env_text = env_file.read_text(encoding="utf-8")
        assert "OAUTH_CLIENT_SECRET" not in env_text
        assert "FLASK_SECRET_KEY" not in env_text
        assert "SQL_ROLE_ASSERTION_HMAC_SECRET" not in env_text
        assert "SQL_AUTH_MODE=user" in env_text

        python_code = (
            "import agents.semantic_analytics.agent as a\n"
            "assert a.root_agent.name == 'semantic_analytics', f'Unexpected name: {a.root_agent.name}'\n"
            "from semantic.registry import load_contracts\n"
            "contracts = load_contracts()\n"
            "assert len(contracts) == 2, f'Expected 2 contracts, got {len(contracts)}'\n"
        )
        run_env = dict(os.environ)
        run_env["PYTHONPATH"] = str(temp_stage)

        sub_proc = subprocess.run(
            [sys.executable, "-c", python_code],
            cwd=tempfile.gettempdir(),
            env=run_env,
            capture_output=True,
            text=True,
            check=False,
        )
        assert sub_proc.returncode == 0, f"Import subprocess failed: {sub_proc.stderr}\nOutput: {sub_proc.stdout}"
    finally:
        shutil.rmtree(temp_stage, ignore_errors=True)


def test_deploy_agents_stage_only_impersonated_sa() -> None:
    import shutil

    deploy_script = PROJECT_ROOT / "advanced" / "scripts" / "deploy_agents.sh"
    temp_stage = tempfile.mkdtemp()
    role_sa = "role-apac@example-project.iam.gserviceaccount.com"
    caller_sa = "gateway-runner@example-project.iam.gserviceaccount.com"
    role_map_json = f'{{"apac_analyst": "{role_sa}"}}'

    env = dict(os.environ)
    env["DEPLOY_SQL_AUTH_MODE"] = "impersonated_sa"
    env["SQL_ROLE_TRUSTED_CALLER_SA"] = caller_sa
    env["SQL_ROLE_SA_MAP_JSON"] = role_map_json
    env["SQL_ROLE_ASSERTION_HMAC_SECRET"] = "do-not-copy-this-hmac-secret-123456789"

    try:
        stage_result = subprocess.run(
            ["bash", str(deploy_script), "--stage-only", temp_stage],
            cwd=PROJECT_ROOT,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        assert stage_result.returncode == 0, f"deploy_agents.sh failed: {stage_result.stderr}"

        env_file = Path(temp_stage) / "agents" / "semantic_analytics" / ".env"
        assert env_file.exists()
        env_text = env_file.read_text(encoding="utf-8")
        assert "SQL_AUTH_MODE=impersonated_sa" in env_text
        assert f"SQL_ROLE_TRUSTED_CALLER_SA={caller_sa}" in env_text
        assert "SQL_ROLE_ASSERTION_HMAC_SECRET" not in env_text
        assert "OAUTH_CLIENT_SECRET" not in env_text
        assert "FLASK_SECRET_KEY" not in env_text

        # Test that sourcing the staged .env preserves the single-quoted SQL_ROLE_SA_MAP_JSON
        bash_check = (
            f"set -a; source '{env_file}'; set +a; "
            f"python3 -c 'import json, os; m = json.loads(os.environ[\"SQL_ROLE_SA_MAP_JSON\"]); "
            f"assert m.get(\"apac_analyst\") == \"{role_sa}\"'"
        )
        bash_proc = subprocess.run(
            ["bash", "-c", bash_check],
            cwd=tempfile.gettempdir(),
            capture_output=True,
            text=True,
            check=False,
        )
        assert bash_proc.returncode == 0, f"Bash source failed: {bash_proc.stderr}"
    finally:
        shutil.rmtree(temp_stage, ignore_errors=True)


def test_deploy_agents_rejects_adc() -> None:
    deploy_script = PROJECT_ROOT / "advanced" / "scripts" / "deploy_agents.sh"
    temp_stage = tempfile.mkdtemp()
    env = dict(os.environ)
    env["DEPLOY_SQL_AUTH_MODE"] = "adc"

    try:
        stage_result = subprocess.run(
            ["bash", str(deploy_script), "--stage-only", temp_stage],
            cwd=PROJECT_ROOT,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        assert stage_result.returncode != 0
        assert "Shared ADC mode ('adc') cannot be deployed" in stage_result.stderr
    finally:
        import shutil
        shutil.rmtree(temp_stage, ignore_errors=True)


