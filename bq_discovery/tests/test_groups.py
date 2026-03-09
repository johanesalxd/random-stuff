"""Tests for bq_discovery.resolvers.groups internal functions."""

from __future__ import annotations

from bq_discovery.resolvers.groups import (
    GroupResolver,
    _classify_member,
)

# --- _classify_member ---


def test_classify_member_service_account():
    """Email ending in .iam.gserviceaccount.com returns 'serviceAccount'."""
    assert _classify_member("sa@proj.iam.gserviceaccount.com") == "serviceAccount"


def test_classify_member_user():
    """Regular email returns 'user'."""
    assert _classify_member("alice@example.com") == "user"


def test_classify_member_user_with_subdomain():
    """Email with subdomain that is not a service account returns 'user'."""
    assert _classify_member("alice@corp.example.com") == "user"


def test_classify_member_gserviceaccount_substring():
    """Email containing 'gserviceaccount' but not the full suffix is a user."""
    assert _classify_member("gserviceaccount@example.com") == "user"


# --- GroupResolver._parse_transitive_membership (static) ---


def test_parse_transitive_membership_user():
    """User membership returns {'email': ..., 'type': 'user'}."""
    data = {
        "preferredMemberKey": {"id": "alice@example.com"},
        "relationType": "DIRECT",
    }
    result = GroupResolver._parse_transitive_membership(data)
    assert result == {"email": "alice@example.com", "type": "user"}


def test_parse_transitive_membership_service_account():
    """Service account email classifies as 'serviceAccount'."""
    data = {
        "preferredMemberKey": {"id": "sa@proj.iam.gserviceaccount.com"},
        "relationType": "DIRECT",
    }
    result = GroupResolver._parse_transitive_membership(data)
    assert result == {
        "email": "sa@proj.iam.gserviceaccount.com",
        "type": "serviceAccount",
    }


def test_parse_transitive_membership_group_skipped():
    """Membership with relationType='GROUP' returns None."""
    data = {
        "preferredMemberKey": {"id": "group@example.com"},
        "relationType": "GROUP",
    }
    assert GroupResolver._parse_transitive_membership(data) is None


def test_parse_transitive_membership_empty_id_skipped():
    """Membership with empty preferredMemberKey.id returns None."""
    data = {"preferredMemberKey": {"id": ""}, "relationType": "DIRECT"}
    assert GroupResolver._parse_transitive_membership(data) is None


def test_parse_transitive_membership_missing_key():
    """Membership with no preferredMemberKey returns None."""
    data = {"relationType": "DIRECT"}
    assert GroupResolver._parse_transitive_membership(data) is None


# --- GroupResolver._parse_direct_membership (static) ---


def test_parse_direct_membership_group_skipped():
    """Membership with type='GROUP' returns None."""
    data = {
        "preferredMemberKey": {"id": "group@example.com"},
        "type": "GROUP",
    }
    assert GroupResolver._parse_direct_membership(data) is None


def test_parse_direct_membership_missing_key():
    """Membership with no preferredMemberKey returns None."""
    data = {"type": "USER"}
    assert GroupResolver._parse_direct_membership(data) is None


def test_parse_direct_membership_default_type():
    """Membership without 'type' key defaults to 'USER' (not skipped)."""
    data = {"preferredMemberKey": {"id": "alice@example.com"}}
    result = GroupResolver._parse_direct_membership(data)
    assert result is not None
    assert result["email"] == "alice@example.com"
