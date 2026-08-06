"""Tests for Conversational Analytics API endpoint resolution."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config.ca_locations import ca_api_endpoint  # noqa: E402


def test_ca_api_endpoint_defaults_to_the_global_host():
    """Tests an unset or global location keeps the plain global hostname."""
    assert ca_api_endpoint("global") == "geminidataanalytics.googleapis.com"
    assert ca_api_endpoint("") == "geminidataanalytics.googleapis.com"
    assert ca_api_endpoint(None) == "geminidataanalytics.googleapis.com"


def test_ca_api_endpoint_uses_the_hyphenated_host_for_regions():
    """Tests a region resolves to the geminidataanalytics-<region> host."""
    assert (
        ca_api_endpoint("asia-southeast1")
        == "geminidataanalytics-asia-southeast1.googleapis.com"
    )
    assert (
        ca_api_endpoint("us-central1")
        == "geminidataanalytics-us-central1.googleapis.com"
    )


def test_ca_api_endpoint_uses_the_rep_host_for_multi_regions():
    """Tests a multi-region resolves to the .rep. host form.

    Regions and multi-regions use different host shapes, and the only signal is
    the hyphen, so this boundary is what keeps regional agents reachable.
    """
    assert ca_api_endpoint("us") == "geminidataanalytics.us.rep.googleapis.com"
    assert ca_api_endpoint("eu") == "geminidataanalytics.eu.rep.googleapis.com"
