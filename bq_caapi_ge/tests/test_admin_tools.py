"""Tests for the CA API data agent admin helpers."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts import admin_tools  # noqa: E402


def test_make_client_leaves_the_global_endpoint_unset(monkeypatch):
    """Tests a global agent uses the library default rather than an override.

    Pinning an explicit host for ``global`` would bypass the client library's
    own endpoint resolution, so the override must only appear for regions.
    """
    captured: list[dict] = []

    monkeypatch.setattr(
        admin_tools.geminidataanalytics,
        "DataAgentServiceClient",
        lambda **kwargs: captured.append(kwargs) or "client",
    )

    assert admin_tools.make_client("global") == "client"
    assert captured == [{}]


def test_make_client_targets_the_regional_endpoint(monkeypatch):
    """Tests a regional agent gets an explicit api_endpoint client option.

    A regional data agent is unreachable through the global host, so this
    override is what makes a non-global deployment work at all.
    """
    captured: list[dict] = []

    monkeypatch.setattr(
        admin_tools.geminidataanalytics,
        "DataAgentServiceClient",
        lambda **kwargs: captured.append(kwargs) or "client",
    )

    admin_tools.make_client("asia-southeast1")

    assert captured == [
        {
            "client_options": {
                "api_endpoint": "geminidataanalytics-asia-southeast1.googleapis.com"
            }
        }
    ]
