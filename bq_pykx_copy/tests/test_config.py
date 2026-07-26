"""Tests for GCP project resolution (no gcloud/GCP runtime required)."""

import subprocess

import pytest

import config


def test_resolve_gcp_project_prefers_env(monkeypatch):
    """An explicit GCP_PROJECT env var wins without shelling out to gcloud."""
    monkeypatch.setenv("GCP_PROJECT", "my-test-project")

    assert config.resolve_gcp_project() == "my-test-project"


def test_resolve_gcp_project_falls_back_to_gcloud(monkeypatch):
    """With no env var, the active gcloud default project is used."""
    monkeypatch.delenv("GCP_PROJECT", raising=False)
    monkeypatch.setattr(
        config.subprocess, "check_output", lambda *a, **k: "gcloud-project\n"
    )

    assert config.resolve_gcp_project() == "gcloud-project"


def test_resolve_gcp_project_raises_when_unset(monkeypatch):
    """No env var and an unset gcloud project is a hard, explicit error."""
    monkeypatch.delenv("GCP_PROJECT", raising=False)
    monkeypatch.setattr(
        config.subprocess, "check_output", lambda *a, **k: "(unset)\n"
    )

    with pytest.raises(RuntimeError):
        config.resolve_gcp_project()


def test_resolve_gcp_project_raises_when_gcloud_missing(monkeypatch):
    """A missing/failing gcloud binary surfaces as the same explicit error."""
    monkeypatch.delenv("GCP_PROJECT", raising=False)

    def _boom(*a, **k):
        raise subprocess.CalledProcessError(1, "gcloud")

    monkeypatch.setattr(config.subprocess, "check_output", _boom)

    with pytest.raises(RuntimeError):
        config.resolve_gcp_project()
