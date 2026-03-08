"""CLI entry point for bq-discovery."""

from __future__ import annotations

import argparse
import logging
import sys

from bq_discovery.models import ResourceType
from bq_discovery.resolvers.projects import list_org_projects_info
from bq_discovery.scanner import run_scan

logger = logging.getLogger(__name__)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments.

    Args:
        argv: Argument list to parse. Defaults to sys.argv if None.

    Returns:
        Parsed arguments as a Namespace object.
    """
    parser = argparse.ArgumentParser(
        prog="bq-discovery",
        description=(
            "Scan BigQuery permission access across projects in a GCP organization."
        ),
    )
    parser.add_argument(
        "--org-id",
        required=True,
        help="GCP organization ID (numeric).",
    )
    parser.add_argument(
        "--list-projects",
        action="store_true",
        help=(
            "List all active projects in the org (project ID and project number) "
            "and exit. Use this to discover project IDs for --project-ids."
        ),
    )
    parser.add_argument(
        "--skip-acls",
        action="store_true",
        help=(
            "Skip the dataset ACL scan. Only IAM policies from Cloud Asset "
            "Inventory will be returned. Faster but misses legacy ACLs, "
            "specialGroup, domain, and authorized view/dataset/routine entries."
        ),
    )
    parser.add_argument(
        "--resource-types",
        default="project,dataset,table,view",
        help=(
            "Comma-separated list of resource types to scan. "
            "Options: project, dataset, table, view. Default: all."
        ),
    )
    parser.add_argument(
        "--project-ids",
        default=None,
        help=(
            "Comma-separated list of specific project IDs to scan. "
            "If not specified, discovers all projects in the org."
        ),
    )
    parser.add_argument(
        "--expand-groups",
        action="store_true",
        help=(
            "Expand group memberships to individual users. "
            "Requires Cloud Identity API and appropriate permissions."
        ),
    )
    parser.add_argument(
        "--format",
        choices=["json", "jsonl", "csv"],
        default="json",
        help=(
            "Output format. 'json' (default) is pretty-printed with metadata. "
            "'jsonl' is newline-delimited JSON, one entry per line, compatible "
            "with BigQuery JSONL import. 'csv' is comma-separated, compatible "
            "with BigQuery CSV import."
        ),
    )
    parser.add_argument(
        "--output",
        "-o",
        default=None,
        help="Output file path. If not specified, prints to stdout.",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="count",
        default=0,
        help="Increase verbosity. Use -v for INFO, -vv for DEBUG.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Main entry point for bq-discovery CLI.

    Args:
        argv: Argument list to parse. Defaults to sys.argv if None.

    Returns:
        Exit code (0 for success, 1 for error).
    """
    args = parse_args(argv)

    # Configure logging
    log_level = logging.WARNING
    if args.verbose >= 2:
        log_level = logging.DEBUG
    elif args.verbose >= 1:
        log_level = logging.INFO

    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # --list-projects: discover and print all projects, then exit
    if args.list_projects:
        try:
            projects = list_org_projects_info(args.org_id)
        except Exception as e:
            logger.error("Failed to list projects: %s", e)
            print(f"Error: {e}", file=sys.stderr)
            return 1
        if not projects:
            print("No active projects found.", file=sys.stderr)
            return 0
        id_width = max(len(p["project_id"]) for p in projects)
        id_width = max(id_width, len("PROJECT_ID"))
        print(f"{'PROJECT_ID':<{id_width}}  PROJECT_NUMBER")
        print(f"{'-' * id_width}  {'-' * 14}")
        for p in projects:
            print(f"{p['project_id']:<{id_width}}  {p['project_number']}")
        print(f"\n{len(projects)} project(s) found.", file=sys.stderr)
        return 0

    # Parse resource types
    resource_types: set[ResourceType] = set()
    for rt in args.resource_types.split(","):
        rt = rt.strip().lower()
        try:
            resource_types.add(ResourceType(rt))
        except ValueError:
            logger.error("Unknown resource type: %s", rt)
            print(
                f"Error: Unknown resource type '{rt}'. "
                f"Valid types: dataset, table, view",
                file=sys.stderr,
            )
            return 1

    # Parse project IDs
    project_ids = None
    if args.project_ids:
        project_ids = [p.strip() for p in args.project_ids.split(",")]

    # Run scan
    try:
        result = run_scan(
            organization_id=args.org_id,
            resource_types=resource_types,
            project_ids=project_ids,
            skip_acls=args.skip_acls,
            expand_groups=args.expand_groups,
        )
    except Exception as e:
        logger.error("Scan failed: %s", e)
        print(f"Error: {e}", file=sys.stderr)
        return 1

    # Serialize output in requested format
    if args.format == "jsonl":
        output = result.to_jsonl()
    elif args.format == "csv":
        output = result.to_csv()
    else:
        output = result.to_json()

    if args.output:
        with open(args.output, "w", newline="") as f:
            f.write(output)
            if not output.endswith("\n"):
                f.write("\n")
        logger.info("Results written to %s", args.output)
    else:
        print(output, end="" if output.endswith("\n") else "\n")

    # Summary to stderr
    print(
        f"\nScan complete: "
        f"{len(result.entries)} permission entries, "
        f"{result.projects_scanned} projects, "
        f"{result.datasets_scanned} datasets, "
        f"{result.resources_scanned} resources, "
        f"{len(result.errors)} errors",
        file=sys.stderr,
    )

    if result.errors:
        print(
            f"\nErrors ({len(result.errors)}):",
            file=sys.stderr,
        )
        for error in result.errors[:10]:
            print(f"  - {error}", file=sys.stderr)
        if len(result.errors) > 10:
            print(
                f"  ... and {len(result.errors) - 10} more",
                file=sys.stderr,
            )

    return 0


if __name__ == "__main__":
    sys.exit(main())
