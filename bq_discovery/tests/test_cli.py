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


def test_parse_args_skip_acls():
    """--skip-acls sets skip_acls=True."""
    args = parse_args(["--org-id", "1", "--skip-acls"])
    assert args.skip_acls is True


def test_parse_args_list_projects():
    """--list-projects sets list_projects=True."""
    args = parse_args(["--org-id", "1", "--list-projects"])
    assert args.list_projects is True


def test_parse_args_expand_groups():
    """--expand-groups sets expand_groups=True."""
    args = parse_args(["--org-id", "1", "--expand-groups"])
    assert args.expand_groups is True


def test_parse_args_resource_types_default():
    """Default resource_types is 'project,dataset,table,view'."""
    args = parse_args(["--org-id", "1"])
    assert args.resource_types == "project,dataset,table,view"


def test_parse_args_resource_types_custom():
    """Custom --resource-types value is stored as-is."""
    args = parse_args(["--org-id", "1", "--resource-types", "dataset"])
    assert args.resource_types == "dataset"


def test_parse_args_project_ids():
    """--project-ids stores the comma-separated string."""
    args = parse_args(["--org-id", "1", "--project-ids", "a,b,c"])
    assert args.project_ids == "a,b,c"


def test_parse_args_format_json():
    """--format json sets format='json'."""
    args = parse_args(["--org-id", "1", "--format", "json"])
    assert args.format == "json"


def test_parse_args_format_jsonl():
    """--format jsonl sets format='jsonl'."""
    args = parse_args(["--org-id", "1", "--format", "jsonl"])
    assert args.format == "jsonl"


def test_parse_args_format_csv():
    """--format csv sets format='csv'."""
    args = parse_args(["--org-id", "1", "--format", "csv"])
    assert args.format == "csv"


def test_parse_args_format_invalid():
    """Invalid --format value raises SystemExit."""
    with pytest.raises(SystemExit):
        parse_args(["--org-id", "1", "--format", "xml"])


def test_parse_args_output_file():
    """--output / -o stores the file path."""
    args = parse_args(["--org-id", "1", "-o", "/tmp/out.json"])
    assert args.output == "/tmp/out.json"


def test_parse_args_verbose_zero():
    """No -v flags sets verbose=0."""
    args = parse_args(["--org-id", "1"])
    assert args.verbose == 0


def test_parse_args_verbose_one():
    """-v sets verbose=1."""
    args = parse_args(["--org-id", "1", "-v"])
    assert args.verbose == 1


def test_parse_args_verbose_two():
    """-vv sets verbose=2."""
    args = parse_args(["--org-id", "1", "-vv"])
    assert args.verbose == 2
