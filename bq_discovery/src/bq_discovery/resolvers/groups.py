"""Resolve Google Group memberships via Cloud Identity API.

Uses the Cloud Identity Groups API to expand group email addresses
into individual user members. Attempts transitive membership resolution
(nested groups) first, falling back to direct membership listing when
the transitive API is unavailable (requires Cloud Identity Premium or
Google Workspace Enterprise).
"""

from __future__ import annotations

import logging
from urllib.parse import urlencode

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

logger = logging.getLogger(__name__)


class GroupResolver:
    """Resolves Google Group email addresses to individual members.

    Results are cached in memory to avoid redundant API calls when the
    same group appears in multiple permission entries.
    """

    def __init__(self) -> None:
        self._service = build("cloudidentity", "v1", cache_discovery=False)
        self._cache: dict[str, list[dict[str, str]]] = {}

    def resolve_group(self, group_email: str) -> list[dict[str, str]]:
        """Resolve a group email to its individual members.

        Args:
            group_email: The group email address
                (e.g. "data-team@example.com").

        Returns:
            List of dicts with "email" and "type" keys. Type is "user"
            or "serviceAccount". Returns empty list if the group cannot
            be resolved.
        """
        if group_email in self._cache:
            return self._cache[group_email]

        group_name = self._lookup_group_name(group_email)
        if not group_name:
            self._cache[group_email] = []
            return []

        # Try transitive first, fall back to direct
        members = self._search_transitive_memberships(group_name)
        if members is None:
            members = self._list_direct_memberships(group_name)

        self._cache[group_email] = members
        logger.info("Resolved group %s: %s members", group_email, len(members))
        return members

    def _lookup_group_name(self, group_email: str) -> str | None:
        """Look up the Cloud Identity group resource name from an email.

        Args:
            group_email: Group email address.

        Returns:
            Group resource name (e.g. "groups/abc123") or None.
        """
        try:
            request = self._service.groups().lookup()
            request.uri += "&" + urlencode({"groupKey.id": group_email})
            response = request.execute()
            name = response.get("name")
            if name:
                logger.debug("Looked up group %s -> %s", group_email, name)
                return name
        except HttpError as e:
            logger.warning("Failed to look up group %s: %s", group_email, e)
        return None

    def _search_transitive_memberships(
        self, group_name: str
    ) -> list[dict[str, str]] | None:
        """Search transitive memberships (includes nested groups).

        Requires Cloud Identity Premium or Google Workspace Enterprise.

        Args:
            group_name: Group resource name (e.g. "groups/abc123").

        Returns:
            List of member dicts, or None if the API is unavailable
            (triggers fallback to direct listing).
        """
        try:
            members: list[dict[str, str]] = []
            next_page_token = ""

            while True:
                query_params = urlencode(
                    {
                        "page_size": 200,
                        "page_token": next_page_token,
                    }
                )
                request = (
                    self._service.groups()
                    .memberships()
                    .searchTransitiveMemberships(parent=group_name)
                )
                request.uri += "&" + query_params
                response = request.execute()

                for membership in response.get("memberships", []):
                    member = self._parse_transitive_membership(membership)
                    if member:
                        members.append(member)

                next_page_token = response.get("nextPageToken", "")
                if not next_page_token:
                    break

            return members

        except HttpError as e:
            if e.resp.status in (403, 501):
                logger.info(
                    "Transitive membership search unavailable "
                    "(likely requires Premium tier), "
                    "falling back to direct listing"
                )
                return None
            logger.warning(
                "Error searching transitive memberships for %s: %s",
                group_name,
                e,
            )
            return []

    def _list_direct_memberships(self, group_name: str) -> list[dict[str, str]]:
        """List direct memberships only (no nested group resolution).

        Args:
            group_name: Group resource name (e.g. "groups/abc123").

        Returns:
            List of member dicts with "email" and "type" keys.
        """
        try:
            members: list[dict[str, str]] = []
            next_page_token = ""

            while True:
                kwargs: dict = {
                    "parent": group_name,
                    "pageSize": 200,
                }
                if next_page_token:
                    kwargs["pageToken"] = next_page_token

                request = self._service.groups().memberships().list(**kwargs)
                response = request.execute()

                for membership in response.get("memberships", []):
                    member = self._parse_direct_membership(membership)
                    if member:
                        members.append(member)

                next_page_token = response.get("nextPageToken", "")
                if not next_page_token:
                    break

            return members

        except HttpError as e:
            logger.warning("Error listing memberships for %s: %s", group_name, e)
            return []

    @staticmethod
    def _parse_transitive_membership(
        membership: dict,
    ) -> dict[str, str] | None:
        """Parse a transitive membership response into a member dict.

        Filters out sub-group entries (only returns users and service
        accounts).
        """
        member_key = membership.get("preferredMemberKey", {})
        member_id = member_key.get("id", "")

        # Skip sub-group entries
        relation_type = membership.get("relationType", "")
        if not member_id or relation_type == "GROUP":
            return None

        member_type = _classify_member(member_id)
        return {"email": member_id, "type": member_type}

    @staticmethod
    def _parse_direct_membership(
        membership: dict,
    ) -> dict[str, str] | None:
        """Parse a direct membership response into a member dict.

        Filters out sub-group entries.
        """
        member_key = membership.get("preferredMemberKey", {})
        member_id = member_key.get("id", "")
        member_type_raw = membership.get("type", "USER")

        if not member_id or member_type_raw == "GROUP":
            return None

        member_type = _classify_member(member_id)
        return {"email": member_id, "type": member_type}


def _classify_member(email: str) -> str:
    """Classify a member email as user or serviceAccount."""
    if email.endswith(".iam.gserviceaccount.com"):
        return "serviceAccount"
    return "user"
