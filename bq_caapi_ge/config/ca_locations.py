"""Conversational Analytics API endpoint resolution by resource location.

The CA API is not a single global service. A data agent created in a region is
only reachable through that region's endpoint, and the host form differs between
regions and multi-regions. Sending a regional agent's request to the global
endpoint returns a confusing "not found" rather than a location error, so both
the REST callers and the generated gRPC client resolve their host here.
"""

from __future__ import annotations

CA_API_GLOBAL_HOST = "geminidataanalytics.googleapis.com"


def ca_api_endpoint(location: str | None) -> str:
    """Return the CA API hostname serving a resource location.

    Args:
        location: CA API resource location. ``global`` or empty selects the
            global endpoint; a region contains a hyphen (``asia-southeast1``);
            anything else is treated as a multi-region (``us``, ``eu``).

    Returns:
        The hostname, without scheme or path, for example
        ``geminidataanalytics-asia-southeast1.googleapis.com``.
    """
    if not location or location == "global":
        return CA_API_GLOBAL_HOST
    if "-" in location:
        return f"geminidataanalytics-{location}.googleapis.com"
    return f"geminidataanalytics.{location}.rep.googleapis.com"
