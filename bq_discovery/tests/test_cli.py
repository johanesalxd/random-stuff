"""Tests for bq_discovery.cli.parse_args."""

from __future__ import annotations

import pytest

from bq_discovery.cli import parse_args

# --- parse_args ---


def test_parse_args_required_org_id():
    """--org-id is required; missing it raises SystemExit."""
    with pytest.raises(SystemExit):
        parse_args([])


def test_parse_args_org_id_only():
    """Minimal valid args set defaults for all other options."""
    args = parse_args(["--org-id", "12345"])
    assert args.org_id == "12345"
    assert args.skip_acls is False
    assert args.expand_groups is False
    assert args.list_projects is False
    assert args.output is None
    assert args.verbose == 0
    assert args.format == "json"
    assert args.resource_types == "project,dataset,table,view"
    assert args.project_ids is None


def test_parse_args_format_invalid():
    """Invalid --format value raises SystemExit."""
    with pytest.raises(SystemExit):
        parse_args(["--org-id", "1", "--format", "xml"])


def test_parse_args_verbose_stacking():
    """-vv increments verbose count to 2."""
    args = parse_args(["--org-id", "1", "-vv"])
    assert args.verbose == 2


def test_parse_args_resource_types_default_excludes_folder():
    """Default --resource-types does not include 'folder'."""
    args = parse_args(["--org-id", "1"])
    assert "folder" not in args.resource_types


def test_parse_args_resource_types_accepts_folder():
    """'folder' is accepted as a valid --resource-types value."""
    args = parse_args(["--org-id", "1", "--resource-types", "folder,dataset"])
    assert args.resource_types == "folder,dataset"
